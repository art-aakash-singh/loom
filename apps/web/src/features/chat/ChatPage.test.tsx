import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, vi } from "vitest";

import { ChatPage } from "./ChatPage";
import type { components } from "../../api/generated/schema";
import { GenerationInProgressError } from "./api/errors";
import type { ChatEvent } from "./api/stream";

type Message = components["schemas"]["MessageOut"];

const GET = vi.fn();
const POST = vi.fn();
const PUT = vi.fn();
vi.mock("../../lib/api-client", () => ({
  api: {
    GET: (...args: unknown[]) => GET(...args),
    POST: (...args: unknown[]) => POST(...args),
    PUT: (...args: unknown[]) => PUT(...args),
  },
}));

const streamChat = vi.fn();
const streamRegenerate = vi.fn();
vi.mock("./api/stream", () => ({
  streamChat: (...args: unknown[]) => streamChat(...args),
  streamRegenerate: (...args: unknown[]) => streamRegenerate(...args),
}));

async function* events(...items: ChatEvent[]) {
  for (const item of items) yield item;
}

const end = (
  stop_reason: "complete" | "max_tokens" | "refusal",
): ChatEvent => ({
  type: "message_end",
  stop_reason,
  usage: { input_tokens: 1, output_tokens: 1 },
});

let counter = 0;
function message(
  role: "user" | "assistant",
  text: string,
  extra: Partial<Message> = {},
): Message {
  const id = extra.id ?? `m${++counter}`;
  return {
    id,
    sibling_ids: [id],
    token_count: 1,
    parent_id: null,
    role,
    status: "complete",
    content: text ? [{ type: "text", text }] : [],
    stop_reason: role === "assistant" ? "complete" : null,
    error_kind: null,
    model: null,
    usage: null,
    created_at: "2026-10-22T00:00:00Z",
    finished_at: "2026-10-22T00:00:01Z",
    ...extra,
  };
}

const history = (...messages: Message[]) => ({
  data: { id: "c1", current_leaf_id: messages.at(-1)?.id ?? null, messages },
  response: { status: 200 },
});

const started = (assistant_message_id = "a1"): ChatEvent => ({
  type: "turn_started",
  user_message_id: "u1",
  assistant_message_id,
});

const onCreated = vi.fn();
const onMissing = vi.fn();
const onTurnFinished = vi.fn();

function renderChat(conversationId: string | null = null) {
  render(
    <ChatPage
      conversationId={conversationId}
      title="Test conversation"
      onCreated={onCreated}
      onMissing={onMissing}
      onTurnFinished={onTurnFinished}
    />,
  );
}

async function send() {
  await userEvent.type(screen.getByLabelText("Message"), "hi");
  await userEvent.click(screen.getByRole("button", { name: "Send" }));
}

beforeEach(() => {
  onCreated.mockReset();
  onMissing.mockReset();
  onTurnFinished.mockReset();
  GET.mockReset();
  POST.mockReset();
  PUT.mockReset();
  streamChat.mockReset();
  streamRegenerate.mockReset();
  POST.mockResolvedValue({ data: { id: "c1" }, response: { status: 201 } });
  GET.mockResolvedValue(history());
});

test("streams a reply, then shows the stored history", async () => {
  streamChat.mockReturnValue(
    events(
      started(),
      { type: "text_delta", text: "Hel" },
      { type: "text_delta", text: "lo" },
      end("complete"),
    ),
  );
  GET.mockResolvedValue(
    history(message("user", "hi"), message("assistant", "Hello")),
  );
  renderChat();
  await send();

  expect(await screen.findByText("Hello")).toBeInTheDocument();
  expect(streamChat).toHaveBeenCalledWith("c1", "hi", expect.anything());
  expect(screen.queryByTestId("status-marker")).not.toBeInTheDocument();
  expect(onCreated).toHaveBeenCalledWith("c1");
  expect(onTurnFinished).toHaveBeenCalled();
});

test("loads the given conversation and marks failed and cancelled replies", async () => {
  GET.mockResolvedValue(
    history(
      message("user", "one"),
      message("assistant", "", {
        status: "error",
        error_kind: "rate_limited",
        stop_reason: null,
      }),
      message("user", "two"),
      message("assistant", "half an ans", {
        status: "cancelled",
        stop_reason: null,
      }),
    ),
  );
  renderChat("c1");

  expect(await screen.findByText("half an ans")).toBeInTheDocument();
  const markers = screen
    .getAllByTestId("status-marker")
    .map((el) => el.textContent);
  expect(markers).toEqual(["failed: rate_limited", "cancelled"]);
  expect(POST).not.toHaveBeenCalled();
});

test("starts a fresh conversation when the given one no longer exists", async () => {
  GET.mockResolvedValue({ data: undefined, response: { status: 404 } });
  renderChat("gone");

  await vi.waitFor(() => expect(onMissing).toHaveBeenCalled());
  streamChat.mockReturnValue(events(end("complete")));
  await send();

  await vi.waitFor(() => expect(POST).toHaveBeenCalledWith("/conversations"));
});

test("marks a reply that stopped for a reason other than complete", async () => {
  streamChat.mockReturnValue(
    events({ type: "text_delta", text: "cut" }, end("max_tokens")),
  );
  GET.mockResolvedValue(
    history(
      message("user", "hi"),
      message("assistant", "cut", { stop_reason: "max_tokens" }),
    ),
  );
  renderChat();
  await send();

  expect(await screen.findByTestId("status-marker")).toHaveTextContent(
    "stopped: max_tokens",
  );
});

test("shows stream errors cleanly", async () => {
  streamChat.mockReturnValue(
    events({
      type: "error",
      kind: "rate_limited",
      message: "slow down",
      retryable: true,
    }),
  );
  GET.mockResolvedValue(
    history(
      message("user", "hi"),
      message("assistant", "", {
        status: "error",
        error_kind: "rate_limited",
        stop_reason: null,
      }),
    ),
  );
  renderChat();
  await send();

  expect(await screen.findByRole("alert")).toHaveTextContent("rate_limited");
  expect(await screen.findByTestId("status-marker")).toHaveTextContent(
    "failed: rate_limited",
  );
});

test("a 409 reads 'a reply is still generating' and lets the user try again", async () => {
  // eslint-disable-next-line require-yield
  streamChat.mockImplementation(async function* () {
    throw new GenerationInProgressError();
  });
  renderChat();
  await send();

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "A reply is still generating.",
  );
  expect(
    await screen.findByRole("button", { name: "Send" }),
  ).toBeInTheDocument();
});

test("Send is unavailable while a reply is streaming", async () => {
  let release: () => void = () => undefined;
  streamChat.mockImplementation(async function* () {
    yield { type: "text_delta", text: "typing" } satisfies ChatEvent;
    await new Promise<void>((resolve) => (release = resolve));
    yield end("complete");
  });
  renderChat();
  await send();

  expect(
    await screen.findByRole("button", { name: "Stop" }),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Send" }),
  ).not.toBeInTheDocument();
  expect(screen.getByLabelText("Message")).toBeDisabled();

  release();
  expect(
    await screen.findByRole("button", { name: "Send" }),
  ).toBeInTheDocument();
});

test("Stop aborts the request and shows the cancelled partial reply", async () => {
  streamChat.mockImplementation(async function* (
    _id: string,
    _msg: string,
    signal: AbortSignal,
  ) {
    yield started("a1");
    yield { type: "text_delta", text: "partial" } satisfies ChatEvent;
    await new Promise((_, reject) =>
      signal.addEventListener("abort", () =>
        reject(new DOMException("x", "AbortError")),
      ),
    );
  });
  // The server finalizes just after the disconnect, so the first fetch can still see it streaming.
  GET.mockResolvedValueOnce(
    history(
      message("user", "hi"),
      message("assistant", "", {
        id: "a1",
        status: "streaming",
        stop_reason: null,
      }),
    ),
  );
  GET.mockResolvedValue(
    history(
      message("user", "hi"),
      message("assistant", "partial", {
        id: "a1",
        status: "cancelled",
        stop_reason: null,
      }),
    ),
  );
  renderChat();
  await send();

  await userEvent.click(await screen.findByRole("button", { name: "Stop" }));

  expect(
    await screen.findByRole("button", { name: "Send" }),
  ).toBeInTheDocument();
  expect(screen.getByText("partial")).toBeInTheDocument();
  expect(screen.getByTestId("status-marker")).toHaveTextContent("cancelled");
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

test("Edit sends the new text under the edited message's parent, hiding the old branch", async () => {
  const u1 = message("user", "one", { id: "u1" });
  const a1 = message("assistant", "first answer", {
    id: "a1",
    parent_id: "u1",
  });
  const u2 = message("user", "two", { id: "u2", parent_id: "a1" });
  const a2 = message("assistant", "second answer", {
    id: "a2",
    parent_id: "u2",
  });
  GET.mockResolvedValueOnce(history(u1, a1, u2, a2));
  let release: () => void = () => undefined;
  streamChat.mockImplementation(async function* () {
    yield started("a3");
    await new Promise<void>((resolve) => (release = resolve));
    yield end("complete");
  });
  renderChat("c1");
  await screen.findByText("second answer");

  const edits = screen.getAllByRole("button", { name: "Edit" });
  await userEvent.click(edits[1]!);
  const box = screen.getByLabelText("Edited message");
  expect(box).toHaveValue("two");
  await userEvent.clear(box);
  await userEvent.type(box, "two, edited");
  await userEvent.click(screen.getByRole("button", { name: "Save and send" }));

  expect(streamChat).toHaveBeenCalledWith(
    "c1",
    "two, edited",
    expect.anything(),
    { parentId: "a1" },
  );
  // While it streams, the old "two" branch is gone and the edit shows as the pending turn.
  expect(await screen.findByText("two, edited")).toBeInTheDocument();
  expect(screen.queryByText("second answer")).not.toBeInTheDocument();
  expect(screen.getByText("first answer")).toBeInTheDocument();
  release();
});

test("editing the first message sends parent_id null", async () => {
  GET.mockResolvedValueOnce(
    history(
      message("user", "one", { id: "u1" }),
      message("assistant", "a", { parent_id: "u1" }),
    ),
  );
  streamChat.mockReturnValue(events(started(), end("complete")));
  renderChat("c1");

  await userEvent.click(await screen.findByRole("button", { name: "Edit" }));
  await userEvent.type(screen.getByLabelText("Edited message"), "!");
  await userEvent.click(screen.getByRole("button", { name: "Save and send" }));

  expect(streamChat).toHaveBeenCalledWith("c1", "one!", expect.anything(), {
    parentId: null,
  });
});

test("Regenerate is offered on the last reply only and streams a new answer to its question", async () => {
  GET.mockResolvedValueOnce(
    history(
      message("user", "one", { id: "u1" }),
      message("assistant", "old answer 1", { id: "a1", parent_id: "u1" }),
      message("user", "two", { id: "u2", parent_id: "a1" }),
      message("assistant", "old answer 2", { id: "a2", parent_id: "u2" }),
    ),
  );
  streamRegenerate.mockReturnValue(
    events(started("a3"), { type: "text_delta", text: "new" }, end("complete")),
  );
  renderChat("c1");

  const regenerate = await screen.findAllByRole("button", {
    name: "Regenerate",
  });
  expect(regenerate).toHaveLength(1);
  await userEvent.click(regenerate[0]!);

  expect(streamRegenerate).toHaveBeenCalledWith("c1", "u2", expect.anything());
});

test("version tabs mark the current branch and switch through the API", async () => {
  const u2 = message("user", "two", {
    id: "u2",
    parent_id: "a1",
    sibling_ids: ["u2", "u2b", "u2c"],
  });
  GET.mockResolvedValueOnce(
    history(
      message("user", "one", { id: "u1" }),
      message("assistant", "a", { id: "a1", parent_id: "u1" }),
      u2,
    ),
  );
  PUT.mockResolvedValue({
    data: {
      id: "c1",
      messages: [
        message("user", "one", { id: "u1" }),
        message("assistant", "a", { id: "a1", parent_id: "u1" }),
        message("user", "two (v2)", {
          id: "u2b",
          parent_id: "a1",
          sibling_ids: ["u2", "u2b", "u2c"],
        }),
      ],
    },
    response: { status: 200 },
  });
  renderChat("c1");

  const versions = await screen.findByRole("group", {
    name: "Versions of this prompt",
  });
  expect(within(versions).getAllByRole("button")).toHaveLength(3);
  expect(
    within(versions).getByRole("button", { name: "Version 1" }),
  ).toHaveAttribute("aria-current", "true");
  await userEvent.click(
    within(versions).getByRole("button", { name: "Version 2" }),
  );

  expect(PUT).toHaveBeenCalledWith("/conversations/{conversation_id}/leaf", {
    params: { path: { conversation_id: "c1" } },
    body: { message_id: "u2b" },
  });
  expect(await screen.findByText("two (v2)")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Version 2" })).toHaveAttribute(
    "aria-current",
    "true",
  );
});
