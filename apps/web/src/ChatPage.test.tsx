import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { ChatPage } from "./ChatPage";
import type { ChatEvent } from "./chat/stream";

const streamChat = vi.fn();
vi.mock("./chat/stream", () => ({ streamChat: (...args: unknown[]) => streamChat(...args) }));

async function* events(...items: ChatEvent[]) {
  for (const item of items) yield item;
}

const end = (stop_reason: "complete" | "max_tokens" | "refusal"): ChatEvent => ({
  type: "message_end",
  stop_reason,
  usage: { input_tokens: 1, output_tokens: 1 },
});

async function send() {
  await userEvent.type(screen.getByLabelText("Message"), "hi");
  await userEvent.click(screen.getByRole("button", { name: "Send" }));
}

test("appends deltas of arbitrary size and hides stop_reason when complete", async () => {
  streamChat.mockReturnValue(
    events({ type: "text_delta", text: "Hel" }, { type: "text_delta", text: "lo wor" }, { type: "text_delta", text: "ld" }, end("complete")),
  );
  render(<ChatPage />);
  await send();

  expect(await screen.findByText("Hello world")).toBeInTheDocument();
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
});

test("shows stop_reason when not complete", async () => {
  streamChat.mockReturnValue(events({ type: "text_delta", text: "cut" }, end("max_tokens")));
  render(<ChatPage />);
  await send();

  expect(await screen.findByRole("status")).toHaveTextContent("max_tokens");
});

test("shows stream errors cleanly", async () => {
  streamChat.mockReturnValue(
    events({ type: "error", kind: "rate_limited", message: "slow down", retryable: true }),
  );
  render(<ChatPage />);
  await send();

  expect(await screen.findByRole("alert")).toHaveTextContent("rate_limited");
});

test("Stop aborts the request and keeps the partial reply", async () => {
  streamChat.mockImplementation(async function* (_msg: string, signal: AbortSignal) {
    yield { type: "text_delta", text: "partial" } satisfies ChatEvent;
    await new Promise((_, reject) => signal.addEventListener("abort", () => reject(new DOMException("x", "AbortError"))));
  });
  render(<ChatPage />);
  await send();

  await userEvent.click(await screen.findByRole("button", { name: "Stop" }));

  expect(await screen.findByRole("button", { name: "Send" })).toBeInTheDocument();
  expect(screen.getByTestId("reply")).toHaveTextContent("partial");
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});
