import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { apiMock, setAccessTokenMock, clearAccessTokenMock } = vi.hoisted(() => ({
  apiMock: vi.fn(),
  setAccessTokenMock: vi.fn(),
  clearAccessTokenMock: vi.fn(),
}));

vi.mock("./api", () => ({
  api: apiMock,
  setAccessToken: setAccessTokenMock,
  clearAccessToken: clearAccessTokenMock,
}));

import App from "./App";

const user = {
  id: 1,
  username: "support-agent",
  role: "Agent",
  roles: [{ name: "Agent" }],
  permissions: ["tickets.view_ticket", "tickets.add_ticket", "tickets.change_ticket"].map((code) => ({ code, name: code })),
};

const ticket = {
  id: 7,
  title: "Printer queue is delayed",
  description: "The front office printer is not responding.",
  status: "open",
  priority: "medium",
  created_at: "2026-10-12T08:00:00Z",
  updated_at: "2026-10-12T08:00:00Z",
};

function setupSignedInApp() {
  let tickets = [ticket];
  apiMock.mockImplementation(async (path, options = {}) => {
    if (path === "/auth/token/refresh") return { access: "test-access", user };
    if (path === "/auth/logout") return {};
    if (path.startsWith("/tickets/stats")) {
      return Object.fromEntries(["open", "in_progress", "closed"].map((status) => [
        status,
        tickets.filter((item) => item.status === status).length,
      ]));
    }
    if (path.startsWith("/tickets?") || path === "/tickets") {
      if (options.method === "POST") {
        const created = { ...JSON.parse(options.body), id: 8, status: "open", created_at: ticket.created_at };
        tickets = [created, ...tickets];
        return created;
      }
      const query = new URL(path, "http://localhost").searchParams;
      const search = (query.get("search") || "").toLowerCase();
      const status = query.get("status");
      const filtered = tickets.filter((item) =>
        (!status || item.status === status) && `${item.title} ${item.description} TKT-${String(item.id).padStart(4, "0")}`.toLowerCase().includes(search));
      return { count: filtered.length, next: null, previous: null, results: filtered };
    }
    if (path.startsWith("/tickets/")) {
      const id = Number(path.split("/").at(-1));
      const changes = JSON.parse(options.body);
      tickets = tickets.map((item) => item.id === id ? { ...item, ...changes } : item);
      return tickets.find((item) => item.id === id);
    }
    throw new Error(`Unexpected API request: ${path}`);
  });
  return render(<App />);
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("Ticket Desk UI workflow", () => {
  it("switches between board and list views", async () => {
    const userActions = userEvent.setup();
    setupSignedInApp();

    await screen.findByText(ticket.title);
    expect(screen.queryByText("Lodwar Services")).toBeNull();
    expect(screen.getByText(/Updated/)).toBeTruthy();
    expect(screen.getByLabelText("Assigned to support-agent").textContent).toBe("SA");
    await userActions.click(screen.getByRole("button", { name: "List view" }));
    expect(screen.getByRole("button", { name: "List view" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: "Board view" }).getAttribute("aria-pressed")).toBe("false");
    await userActions.click(screen.getByRole("button", { name: "Board view" }));
    expect(screen.getByRole("button", { name: "Board view" }).getAttribute("aria-pressed")).toBe("true");
  });

  it("toggles the sidebar and sends a debounced global search to the API", async () => {
    const userActions = userEvent.setup();
    setupSignedInApp();

    await screen.findByText(ticket.title);
    const sidebarToggle = screen.getByRole("button", { name: "Hide sidebar" });
    await userActions.click(sidebarToggle);
    expect(screen.getByRole("button", { name: "Show sidebar" }).getAttribute("aria-expanded")).toBe("false");

    await userActions.type(screen.getByRole("searchbox", { name: "Search tickets" }), "printer");
    await waitFor(() => {
      expect(apiMock).toHaveBeenCalledWith(expect.stringContaining("search=printer"));
    });
    expect(await screen.findByText(ticket.title)).toBeTruthy();
  });

  it("searches for the ticket code shown on the card", async () => {
    const userActions = userEvent.setup();
    setupSignedInApp();

    await screen.findByText(ticket.title);
    await userActions.type(screen.getByRole("searchbox", { name: "Search tickets" }), "TKT-0007");
    await waitFor(() => expect(apiMock).toHaveBeenCalledWith(expect.stringContaining("search=TKT-0007")));
    expect(await screen.findByText(ticket.title)).toBeTruthy();
  });

  it("moves a ticket by dragging it to another status lane and persists the change", async () => {
    setupSignedInApp();
    const title = await screen.findByText(ticket.title);
    const card = title.closest("article");
    const dataTransfer = {
      effectAllowed: "",
      dropEffect: "",
      setData: vi.fn(),
      getData: vi.fn(() => "7"),
    };

    fireEvent.dragStart(card, { dataTransfer });
    fireEvent.drop(screen.getByRole("region", { name: /In progress/ }), { dataTransfer });

    await waitFor(() => {
      expect(apiMock).toHaveBeenCalledWith("/tickets/7", expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ status: "in_progress" }),
      }));
    });
    expect(await screen.findByText("Ticket updated.")).toBeTruthy();
    expect(await screen.findByText(ticket.title)).toBeTruthy();
  });

  it("updates ticket priority and filters the queue by status", async () => {
    const userActions = userEvent.setup();
    setupSignedInApp();
    await screen.findByText(ticket.title);

    await userActions.click(screen.getByText(ticket.title).closest("article").querySelector("summary"));
    await userActions.selectOptions(screen.getByLabelText("Priority"), "high");
    await waitFor(() => {
      expect(apiMock).toHaveBeenCalledWith("/tickets/7", expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ priority: "high" }),
      }));
    });
    await waitFor(() => {
      const ticketCard = screen.getByText(ticket.title).closest("article");
      expect(ticketCard.querySelector(".ticket-priority-label").textContent).toBe("high");
    });

    await userActions.click(screen.getAllByRole("button", { name: /In progress/ })[0]);
    await waitFor(() => expect(apiMock).toHaveBeenCalledWith(expect.stringContaining("status=in_progress")));
    expect(await screen.findByText("No in progress tickets")).toBeTruthy();
    await userActions.click(screen.getAllByRole("button", { name: /All tickets/ })[0]);
    expect(await screen.findByText(ticket.title)).toBeTruthy();
  });

  it("creates a ticket and signs out back to the login screen", async () => {
    const userActions = userEvent.setup();
    setupSignedInApp();

    await screen.findByText(ticket.title);
    await userActions.click(screen.getAllByRole("button", { name: "New ticket" })[0]);
    await userActions.type(screen.getByLabelText(/Title/), "Cannot reach billing dashboard");
    await userActions.type(screen.getByLabelText(/Description/), "The billing page returns an error.");
    await userActions.click(screen.getByRole("button", { name: "Create ticket" }));

    expect(await screen.findByText("Ticket added to the queue.")).toBeTruthy();
    expect(apiMock).toHaveBeenCalledWith("/tickets", expect.objectContaining({ method: "POST" }));

    await userActions.click(screen.getByRole("button", { name: "Sign out" }));
    expect(await screen.findByLabelText("Username")).toBeTruthy();
    expect(apiMock).toHaveBeenCalledWith("/auth/logout", expect.objectContaining({ method: "POST" }));
    expect(clearAccessTokenMock).toHaveBeenCalled();
  });

  it("authenticates through the login form and opens the ticket board", async () => {
    const userActions = userEvent.setup();
    apiMock.mockImplementation(async (path) => {
      if (path === "/auth/token/refresh") throw new Error("No saved session");
      if (path === "/auth/token") return { access: "new-access", user };
      if (path.startsWith("/tickets/stats")) return { open: 0, in_progress: 0, closed: 0 };
      if (path.startsWith("/tickets?")) return { count: 0, next: null, previous: null, results: [] };
      throw new Error(`Unexpected API request: ${path}`);
    });
    render(<App />);

    await userActions.type(await screen.findByLabelText("Username"), "support-agent");
    await userActions.type(screen.getByLabelText("Password"), "demo-password");
    await userActions.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("heading", { name: "Tickets" })).toBeTruthy();
    expect(apiMock).toHaveBeenCalledWith("/auth/token", expect.objectContaining({ method: "POST" }));
    expect(setAccessTokenMock).toHaveBeenCalledWith("new-access");
  });
});
