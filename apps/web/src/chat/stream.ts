import type { components } from "../api/schema";
import { GenerationInProgressError } from "./errors";

export type SendMessageRequest = components["schemas"]["SendMessageRequest"];

// SSE events aren't described by OpenAPI, so these mirror chat/schemas.py by hand.
export type ChatEvent =
  | { type: "turn_started"; user_message_id: string; assistant_message_id: string }
  | { type: "text_delta"; text: string }
  | {
      type: "message_end";
      stop_reason: "complete" | "max_tokens" | "refusal";
      usage: { input_tokens: number; output_tokens: number };
    }
  | {
      type: "error";
      kind: "rate_limited" | "invalid_request" | "auth_failed" | "overloaded" | "unexpected" | "refusal";
      message: string;
      retryable: boolean;
    };

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

/** Parse `data: <json>\n\n` frames; chunk boundaries can fall anywhere, so buffer. */
export async function* streamChat(
  conversationId: string,
  text: string,
  signal: AbortSignal,
): AsyncGenerator<ChatEvent> {
  const body: SendMessageRequest = { text };
  const response = await fetch(`${API_URL}/conversations/${conversationId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (response.status === 409) throw new GenerationInProgressError();
  if (!response.ok || !response.body) {
    throw new Error(`Request failed (HTTP ${response.status})`);
  }

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) return;
      buffer += value.replaceAll("\r\n", "\n");
      let end: number;
      while ((end = buffer.indexOf("\n\n")) !== -1) {
        const frame = buffer.slice(0, end);
        buffer = buffer.slice(end + 2);
        const data = frame
          .split("\n")
          .filter((line) => line.startsWith("data:"))
          .map((line) => line.slice(5).trimStart())
          .join("\n");
        if (data) yield JSON.parse(data) as ChatEvent;
      }
    }
  } finally {
    await reader.cancel().catch(() => undefined);
  }
}
