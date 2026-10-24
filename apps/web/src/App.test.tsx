import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, vi } from "vitest";

import { App } from "./App";
import type { Conversation } from "./Conversations";

const GET = vi.fn();
const POST = vi.fn();
vi.mock("./api/client", () => ({
  api: { GET: (...args: unknown[]) => GET(...args), POST: (...args: unknown[]) => POST(...args) },
}));

function conversation(id: string, title: string | null): Conversation {
  return {
    id,
    title,
    current_leaf_id: null,
    created_at: "2026-10-24T00:00:00Z",
    updated_at: "2026-10-24T00:00:00Z",
  };
}

let list: Conversation[];
const historyById: Record<string, string> = {};

beforeEach(() => {
  localStorage.clear();
  list = [conversation("c1", "Trip plans"), conversation("c2", null)];
  GET.mockReset();
  POST.mockReset();
  GET.mockImplementation((path: string, init?: { params: { path: { conversation_id: string } } }) => {
    if (path === "/health") return Promise.resolve({ data: { status: "ok" } });
    if (path === "/conversations") return Promise.resolve({ data: list });
    const id = init!.params.path.conversation_id;
    const text = historyById[id];
    const messages = text
      ? [
          {
            id: `${id}-m1`,
            parent_id: null,
            role: "user",
            status: "complete",
            content: [{ type: "text", text }],
            stop_reason: null,
            error_kind: null,
            model: null,
            usage: null,
            created_at: "2026-10-24T00:00:00Z",
            finished_at: "2026-10-24T00:00:00Z",
          },
        ]
      : [];
    return Promise.resolve({ data: { ...conversation(id, null), messages }, response: { status: 200 } });
  });
});

test("shows API health from the generated client", async () => {
  render(<App />);
  expect(await screen.findByText(/API health: ok/)).toBeInTheDocument();
});

test("lists conversations, untitled ones as 'Untitled'", async () => {
  render(<App />);
  const nav = screen.getByRole("navigation", { name: "Conversations" });

  expect(await within(nav).findByRole("button", { name: "Trip plans" })).toBeInTheDocument();
  expect(within(nav).getByRole("button", { name: "Untitled" })).toBeInTheDocument();
});

test("clicking a conversation opens it and remembers it", async () => {
  historyById.c1 = "about the trip";
  historyById.c2 = "something else";
  render(<App />);

  await userEvent.click(await screen.findByRole("button", { name: "Untitled" }));
  expect(await screen.findByText("something else")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Trip plans" }));

  expect(await screen.findByText("about the trip")).toBeInTheDocument();
  expect(screen.queryByText("something else")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Trip plans" })).toHaveAttribute("aria-current", "true");
  expect(localStorage.getItem("loom.conversationId")).toBe("c1");
});

test("New conversation asks for a title, creates it, and opens it", async () => {
  POST.mockImplementation(() => {
    const created = conversation("c3", "Recipes");
    list = [created, ...list];
    return Promise.resolve({ data: created });
  });
  render(<App />);

  await userEvent.click(screen.getByRole("button", { name: "New conversation" }));
  await userEvent.type(screen.getByLabelText("Title"), "  Recipes  ");
  await userEvent.click(screen.getByRole("button", { name: "Create" }));

  expect(POST).toHaveBeenCalledWith("/conversations", { body: { title: "Recipes" } });
  expect(await screen.findByRole("button", { name: "Recipes" })).toHaveAttribute("aria-current", "true");
  expect(screen.queryByLabelText("Title")).not.toBeInTheDocument();
  expect(localStorage.getItem("loom.conversationId")).toBe("c3");
});

test("an empty title creates an untitled conversation", async () => {
  POST.mockResolvedValue({ data: conversation("c3", null) });
  render(<App />);

  await userEvent.click(screen.getByRole("button", { name: "New conversation" }));
  await userEvent.click(screen.getByRole("button", { name: "Create" }));

  expect(POST).toHaveBeenCalledWith("/conversations", { body: { title: null } });
});
