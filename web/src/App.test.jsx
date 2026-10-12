import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
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
  roles: ["Agent"],
  permissions: ["tickets.view_ticket", "tickets.add_ticket", "tickets.change_ticket"],
};

const ticket = {
  id: 7,
  title: "Printer queue is delayed",
  description: "The front office printer is not responding.",
  status: "open",
  priority: "medium",
  created_at: "2026-10-12T08:00:00Z",
};

function setupSignedInApp() {
  let tickets = [ticket];
  apiMock.mockImplementation(async (path, options = {}) => {
    if (path === "/auth/token/refresh") return { access: "test-access" };
    if (path === "/auth/me") return user;
    if (path === "/auth/logout") return {};
    if (path.startsWith("/tickets/stats")) return { open: 1, in_progress: 0, closed: 0 };
    if (path.startsWith("/tickets?") || path === "/tickets") {
      if (options.method === "POST") {
        const created = { ...JSON.parse(options.body), id: 8, status: "open", created_at: ticket.created_at };
        tickets = [created, ...tickets];
        return created;
      }
      const query = new URL(path, "http://localhost").searchParams;
      const search = (query.get("search") || "").toLowerCase();
      const filtered = tickets.filter((item) => `${item.title} ${item.description}`.toLowerCase().includes(search));
      return { tickets: filtered, total: filtered.length };
    }
    if (path.startsWith("/tickets/")) return { ...ticket, ...JSON.parse(options.body) };
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
      if (path === "/auth/token") return { access: "new-access" };
      if (path === "/auth/me") return user;
      if (path.startsWith("/tickets/stats")) return { open: 0, in_progress: 0, closed: 0 };
      if (path.startsWith("/tickets?")) return { tickets: [], total: 0 };
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
