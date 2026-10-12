import { useCallback, useEffect, useRef, useState } from "react";
import Login from "./Login";
import { api, clearAccessToken, setAccessToken } from "./api";

const STATUSES = [
  { value: "open", label: "Open" },
  { value: "in_progress", label: "In progress" },
  { value: "closed", label: "Closed" },
];
const PRIORITIES = ["low", "medium", "high"];
const PAGE_SIZE = 8;

function formatDate(value) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(value));
}

function userInitials(user) {
  const name = [user?.first_name, user?.last_name].filter(Boolean).join(" ").trim() || user?.username || "?";
  return name.split(/[\s._-]+/).filter(Boolean).slice(0, 2).map((part) => part[0].toUpperCase()).join("");
}

function ChromeIcon({ name }) {
  const shapes = {
    sidebar: <><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M10 4v16"/></>,
    back: <path d="m14.5 5-7 7 7 7"/>,
    forward: <path d="m9.5 5 7 7-7 7"/>,
    download: <><circle cx="12" cy="12" r="9"/><path d="M12 6v10m-4-4 4 4 4-4"/></>,
    share: <><path d="M12 15V3m-4 4 4-4 4 4"/><path d="M6 10H5a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7a2 2 0 0 0-2-2h-1"/></>,
    plus: <path d="M12 4v16M4 12h16"/>,
    tabs: <><rect x="7" y="7" width="14" height="14" rx="2"/><path d="M17 7V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h2"/></>,
    search: <><circle cx="11" cy="11" r="7"/><path d="m16 16 5 5"/></>,
  };
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{shapes[name]}</svg>;
}

export default function App() {
  const [authUser, setAuthUser] = useState(null);
  const [authChecking, setAuthChecking] = useState(true);
  const [tickets, setTickets] = useState([]);
  const [stats, setStats] = useState({ open: 0, in_progress: 0, closed: 0 });
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [form, setForm] = useState({ title: "", description: "", priority: "medium" });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [draggingTicketId, setDraggingTicketId] = useState(null);
  const [dragOverStatus, setDragOverStatus] = useState("");
  const [viewMode, setViewMode] = useState("board");
  const [searchInput, setSearchInput] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const filterRef = useRef(null);
  const hasPermission = (code) => authUser?.permissions?.some((permission) => permission.code === code) ?? false;
  const canCreateTickets = hasPermission("tickets.add_ticket");
  const canEditTickets = hasPermission("tickets.change_ticket");
  const canViewTickets = hasPermission("tickets.view_ticket");

  useEffect(() => {
    api("/auth/token/refresh", { method: "POST" })
      .then((tokens) => {
        setAccessToken(tokens.access);
        return tokens.user;
      })
      .then(setAuthUser)
      .catch(() => clearAccessToken())
      .finally(() => setAuthChecking(false));
  }, []);

  useEffect(() => {
    function expireSession() {
      clearAccessToken();
      setAuthUser(null);
      setTickets([]);
      setStats({ open: 0, in_progress: 0, closed: 0 });
      setTotal(0);
    }
    window.addEventListener("ticket-desk:session-expired", expireSession);
    return () => window.removeEventListener("ticket-desk:session-expired", expireSession);
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => setSearchTerm(searchInput.trim()), 250);
    return () => clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    function closeFilter(event) {
      if (filterRef.current && !filterRef.current.contains(event.target)) filterRef.current.open = false;
    }
    document.addEventListener("pointerdown", closeFilter);
    return () => document.removeEventListener("pointerdown", closeFilter);
  }, []);

  const refresh = useCallback(async () => {
    if (!authUser || !authUser.permissions?.some((permission) => permission.code === "tickets.view_ticket")) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    const query = new URLSearchParams({ page: String(page), limit: String(PAGE_SIZE) });
    if (statusFilter) query.set("status", statusFilter);
    if (searchTerm) query.set("search", searchTerm);
    try {
      const [list, counts] = await Promise.all([
        api(`/tickets?${query}`),
        api(`/tickets/stats${searchTerm ? `?search=${encodeURIComponent(searchTerm)}` : ""}`),
      ]);
      setTickets(list.results);
      setTotal(list.count);
      setStats(counts);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [authUser, page, statusFilter, searchTerm]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function createTicket(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setNotice("");
    try {
      await api("/tickets", { method: "POST", body: JSON.stringify(form) });
      setForm({ title: "", description: "", priority: "medium" });
      setShowCreate(false);
      setPage(1);
      setStatusFilter("");
      setSearchInput("");
      setSearchTerm("");
      setNotice("Ticket added to the queue.");
      if (page === 1 && !statusFilter && !searchTerm) await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function updateTicket(ticket, field, value) {
    const previous = ticket[field];
    setTickets((current) => current.map((item) => item.id === ticket.id ? { ...item, [field]: value } : item));
    setError("");
    try {
      await api(`/tickets/${ticket.id}`, {
        method: "PATCH",
        body: JSON.stringify({ [field]: value }),
      });
      setNotice("Ticket updated.");
      await refresh();
    } catch (err) {
      setTickets((current) => current.map((item) => item.id === ticket.id ? { ...item, [field]: previous } : item));
      setError(err.message);
    }
  }

  async function signOut() {
    try {
      await api("/auth/logout", { method: "POST" });
    } catch {
      // Clear local credentials even if the API is unavailable during sign-out.
    }
    clearAccessToken();
    setAuthUser(null);
    setTickets([]);
    setStats({ open: 0, in_progress: 0, closed: 0 });
    setTotal(0);
  }

  function startTicketDrag(event, ticket) {
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", String(ticket.id));
    setDraggingTicketId(ticket.id);
  }

  function allowTicketDrop(event, status) {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    setDragOverStatus(status);
  }

  async function dropTicket(event, status) {
    event.preventDefault();
    const ticketId = Number(event.dataTransfer.getData("text/plain"));
    const ticket = tickets.find((item) => item.id === ticketId);
    setDraggingTicketId(null);
    setDragOverStatus("");
    if (ticket && ticket.status !== status) await updateTicket(ticket, "status", status);
  }

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const boardStatuses = statusFilter ? STATUSES.filter((item) => item.value === statusFilter) : STATUSES;

  function chooseStatusFilter(value) {
    setPage(1);
    setStatusFilter(value);
    filterRef.current.open = false;
    filterRef.current.querySelector("summary")?.focus();
  }

  function exportTickets() {
    const columns = ["id", "title", "description", "status", "priority", "created_at"];
    const escape = (value) => `"${String(value ?? "").replaceAll('"', '""')}"`;
    const csv = [columns.join(","), ...tickets.map((ticket) => columns.map((column) => escape(ticket[column])).join(","))].join("\n");
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    link.download = "tickets.csv";
    link.click();
    URL.revokeObjectURL(link.href);
  }

  if (authChecking) {
    return <main className="login-screen"><div className="login-loading">Loading your workspace…</div></main>;
  }
  if (!authUser) return <Login onAuthenticated={setAuthUser} />;
  if (!canViewTickets) {
    return <main className="login-screen"><section className="login-card" aria-labelledby="access-title"><p className="login-eyebrow">ACCOUNT ACCESS</p><h1 id="access-title">No ticket access</h1><p className="login-description">Your account does not have a ticket role yet. Ask an administrator to assign one.</p><button className="login-submit" type="button" onClick={signOut}>Sign out</button></section></main>;
  }

  return (
    <main className={`app-layout ${sidebarOpen ? "sidebar-open" : "sidebar-closed"}`}>
      <div className="app-chrome">
        <div className="chrome-side chrome-left"><button type="button" className="chrome-glyph sidebar-toggle" aria-label={sidebarOpen ? "Hide sidebar" : "Show sidebar"} aria-expanded={sidebarOpen} onClick={() => setSidebarOpen((open) => !open)}><ChromeIcon name="sidebar"/></button><span className="chrome-glyph" aria-hidden="true"><ChromeIcon name="back"/></span><span className="chrome-glyph chrome-muted" aria-hidden="true"><ChromeIcon name="forward"/></span></div>
        <label className="chrome-address"><ChromeIcon name="search"/><input type="search" value={searchInput} onChange={(event) => { setPage(1); setSearchInput(event.target.value); }} placeholder="Search tickets..." aria-label="Search tickets"/></label>
        <div className="chrome-side chrome-right" aria-hidden="true"><span className="chrome-glyph"><ChromeIcon name="download"/></span><span className="chrome-glyph"><ChromeIcon name="share"/></span><span className="chrome-glyph"><ChromeIcon name="plus"/></span><span className="chrome-glyph"><ChromeIcon name="tabs"/></span></div>
      </div>
      {sidebarOpen && <button type="button" className="sidebar-scrim" aria-label="Close sidebar" onClick={() => setSidebarOpen(false)} />}
      <aside className="sidebar" aria-label="Ticket navigation">
        <a className="brand" href="#top" aria-label="Ticket Desk home">TICKET · DESK</a>
        {canCreateTickets && <div className="sidebar-create-row"><button type="button" className="sidebar-create" onClick={() => setShowCreate(true)}>New ticket</button><button type="button" className="sidebar-create-plus" onClick={() => setShowCreate(true)} aria-label="New ticket">＋</button></div>}
        <nav className="side-nav" aria-label="Ticket views">
          <button className={!statusFilter ? "active" : ""} onClick={() => { setPage(1); setStatusFilter(""); }}><span className="nav-icon">▦</span>All tickets <span className="nav-count">{stats.open + stats.in_progress + stats.closed}</span></button>
          <button className={statusFilter === "open" ? "active" : ""} onClick={() => { setPage(1); setStatusFilter("open"); }}><span className="nav-icon open-icon">○</span>Open <span className="nav-count">{stats.open}</span></button>
          <button className={statusFilter === "in_progress" ? "active" : ""} onClick={() => { setPage(1); setStatusFilter("in_progress"); }}><span className="nav-icon progress-icon">◷</span>In progress <span className="nav-count">{stats.in_progress}</span></button>
          <button className={statusFilter === "closed" ? "active" : ""} onClick={() => { setPage(1); setStatusFilter("closed"); }}><span className="nav-icon closed-icon">✓</span>Resolved <span className="nav-count">{stats.closed}</span></button>
        </nav>
        <div className="sidebar-bottom"><div className="sidebar-status"><span className="live-dot"/><span>Support queue</span></div><div className="sidebar-account"><span className="account-details"><small>{authUser.username} · {authUser.role}</small></span><button type="button" className="signout-button" onClick={signOut} aria-label="Sign out" title="Sign out">↗</button></div></div>
      </aside>

      <section className="workspace" id="top">
        <header className="workspace-topbar"><div className="breadcrumb"><span className="crumb-home">⌂</span><span>Workspace</span><span className="crumb-chevron">›</span><strong>Tickets</strong></div></header>
        <div className="content-wrap">
          <section className="intro">
            <h1>{statusFilter ? STATUSES.find((item) => item.value === statusFilter)?.label : "Tickets"}</h1>
            <div className="header-actions">
              <div className="board-view" role="group" aria-label="Ticket display"><button type="button" className={`view-button ${viewMode === "list" ? "selected" : ""}`} aria-label="List view" aria-pressed={viewMode === "list"} onClick={() => setViewMode("list")}>☷</button><button type="button" className={`view-button ${viewMode === "board" ? "selected" : ""}`} aria-label="Board view" aria-pressed={viewMode === "board"} onClick={() => setViewMode("board")}>▦</button></div>
              <button type="button" className="export-button" onClick={exportTickets}>Export</button>
              <button type="button" className="download-button" onClick={exportTickets} aria-label="Download tickets">↓</button>
            </div>
          </section>

          <div className="board-toolbar">
            <div className="board-context"><span className="context-chip"><span className="context-icon">♧</span> Team</span><span className="context-join">is</span><span className="context-chip"><span className="context-icon">♧</span> Support team</span><span className="context-chip context-selection">{statusFilter ? STATUSES.find((item) => item.value === statusFilter)?.label : "All tickets"}</span><details className="filter-control" ref={filterRef} onKeyDown={(event) => { if (event.key === "Escape") { event.currentTarget.open = false; event.currentTarget.querySelector("summary")?.focus(); } }}><summary aria-label="Filter tickets by status"><span aria-hidden="true">☷</span></summary><div className="filter-menu" aria-label="Status filters">{[{ value: "", label: "All tickets" }, ...STATUSES].map((item) => <button type="button" key={item.value} className={statusFilter === item.value ? "selected" : ""} aria-pressed={statusFilter === item.value} onClick={() => chooseStatusFilter(item.value)}><span>{item.label}</span>{statusFilter === item.value && <span className="filter-check" aria-hidden="true">✓</span>}</button>)}</div></details></div>
          </div>

          {(error || notice) && <div className={`feedback ${error ? "feedback-error" : ""}`} role="status">{error || notice}</div>}

          <section className={`ticket-board ${boardStatuses.length === 1 ? "single-column" : ""} ${viewMode === "list" ? "list-view" : ""}`} aria-label="Tickets by status" aria-live="polite">
            {boardStatuses.map(({ value, label }) => {
              const laneTickets = tickets.filter((ticket) => ticket.status === value);
              const symbol = value === "open" ? "○" : value === "in_progress" ? "◷" : "✓";
              return <section className={`board-column column-${value} ${dragOverStatus === value ? "drag-over" : ""}`} key={value} aria-labelledby={`lane-${value}`} onDragOver={canEditTickets ? (event) => allowTicketDrop(event, value) : undefined} onDragLeave={canEditTickets ? () => setDragOverStatus("") : undefined} onDrop={canEditTickets ? (event) => dropTicket(event, value) : undefined}>
                <header className="column-heading"><span className={`column-symbol symbol-${value}`}>{symbol}</span><h2 id={`lane-${value}`}>{label}</h2><span className="column-count">{stats[value]}</span></header>
                <div className="column-cards">
                  {loading ? <div className="lane-empty">Loading…</div> : laneTickets.length === 0 ? <div className="lane-empty">No {label.toLowerCase()} tickets</div> : laneTickets.map((ticket) => (
                    <article className={`ticket-card ${draggingTicketId === ticket.id ? "dragging" : ""}`} key={ticket.id} draggable={canEditTickets && viewMode === "board"} onDragStart={canEditTickets ? (event) => startTicketDrag(event, ticket) : undefined} onDragEnd={canEditTickets ? () => { setDraggingTicketId(null); setDragOverStatus(""); } : undefined}>
                      <div className="ticket-card-heading"><span className={`priority-marker priority-${ticket.priority}`} aria-hidden="true"/><span className="ticket-code">TKT-{String(ticket.id).padStart(4, "0")}</span>{canEditTickets && <details className="ticket-actions"><summary className="ticket-card-menu" aria-label={`Edit ${ticket.title}`}>•••</summary><div className="ticket-actions-menu"><label htmlFor={`priority-${ticket.id}`}>Priority</label><select id={`priority-${ticket.id}`} value={ticket.priority} onChange={(event) => updateTicket(ticket, "priority", event.target.value)}>{PRIORITIES.map((priority) => <option key={priority} value={priority}>{priority}</option>)}</select><label htmlFor={`status-${ticket.id}`}>Status</label><select id={`status-${ticket.id}`} value={ticket.status} onChange={(event) => updateTicket(ticket, "status", event.target.value)}>{STATUSES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></div></details>}</div>
                      <h3 title={ticket.title}>{ticket.title}</h3>
                      {ticket.description && <p className="ticket-description">{ticket.description}</p>}
                      <div className="ticket-card-footer"><span className="ticket-card-date"><span aria-hidden="true">▣</span>{formatDate(ticket.created_at)}</span><span className={`ticket-priority-label priority-${ticket.priority}`}>{ticket.priority}</span><span className="card-team-avatar" title={authUser.username} aria-label={`Assigned to ${authUser.username}`}>{userInitials(authUser)}</span></div>
                    </article>
                  ))}
                </div>
              </section>;
            })}
          </section>

          <div className="pagination">
            <span className="ticket-total">{total} {total === 1 ? "ticket" : "tickets"}</span>
            <div className="pagination-controls"><button type="button" className="page-button" disabled={page <= 1 || loading} onClick={() => setPage((current) => current - 1)}>← Previous</button><span>Page {page} of {pageCount}</span><button type="button" className="page-button" disabled={page >= pageCount || loading} onClick={() => setPage((current) => current + 1)}>Next →</button></div>
          </div>
        </div>
      </section>

      {showCreate && <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setShowCreate(false); }}>
        <aside className="panel create-panel" role="dialog" aria-modal="true" aria-labelledby="create-heading">
          <button type="button" className="modal-close" aria-label="Close" onClick={() => setShowCreate(false)}>×</button>
          <p className="eyebrow">NEW REQUEST</p><h2 id="create-heading">Create a ticket</h2><p className="form-intro">Capture the issue and add it to the team queue.</p>
          <form onSubmit={createTicket}>
            <label htmlFor="ticket-title">Title <span className="required">*</span></label><input id="ticket-title" name="title" maxLength="200" required placeholder="e.g. Unable to access dashboard" value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} />
            <label htmlFor="ticket-description">Description <span className="optional">OPTIONAL</span></label><textarea id="ticket-description" name="description" rows="4" placeholder="Add a few details to help your team…" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} />
            <label htmlFor="ticket-priority">Priority</label><select id="ticket-priority" name="priority" value={form.priority} onChange={(event) => setForm({ ...form, priority: event.target.value })}>{PRIORITIES.map((priority) => <option value={priority} key={priority}>{priority[0].toUpperCase() + priority.slice(1)}</option>)}</select>
            <button className="submit-button" type="submit" disabled={saving}><span aria-hidden="true">+</span>{saving ? "Adding…" : "Create ticket"}</button>
          </form>
          <p className="helper-note">New tickets start with open status.</p>
        </aside>
      </div>}
    </main>
  );
}
