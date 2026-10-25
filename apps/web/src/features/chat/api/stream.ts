import type { components } from "../../../api/generated/schema";
import { env } from "../../../config/env";
import { GenerationInProgressError } from "./errors";

export type SendMessageRequest = components["schemas"]["SendMessageRequest"];

// SSE events aren't described by OpenAPI, so these mirror chat/schemas.py by hand.
export type ChatEvent =
  | {
      type: "turn_started";
      user_message_id: string;
      assistant_message_id: string;
    }
  | { type: "text_delta"; text: string }
  | {
      type: "message_end";
      stop_reason: "complete" | "max_tokens" | "refusal";
      usage: { input_tokens: number; output_tokens: number };
    }
  | {
      type: "error";
      kind:
        | "rate_limited"
        | "invalid_request"
        | "auth_failed"
        | "overloaded"
        | "unexpected"
        | "refusal";
      message: string;
      retryable: boolean;
    };

/**
 * Send a user message. Omit `parentId` to continue from the current leaf; pass the edited
 * message's parent_id (null for the first message) to edit, which starts a new branch.
 */
export function streamChat(
  conversationId: string,
  text: string,
  signal: AbortSignal,
  options: { parentId?: string | null } = {},
): AsyncGenerator<ChatEvent> {
  const body: SendMessageRequest =
    options.parentId === undefined
      ? { text }
      : { text, parent_id: options.parentId };
  return streamEvents(
    `/conversations/${conversationId}/messages`,
    body,
    signal,
  );
}

/** Answer `userMessageId` again; the new reply becomes a sibling of the earlier ones. */
export function streamRegenerate(
  conversationId: string,
  userMessageId: string,
  signal: AbortSignal,
): AsyncGenerator<ChatEvent> {
  return streamEvents(
    `/conversations/${conversationId}/messages/${userMessageId}/regenerate`,
    undefined,
    signal,
  );
}

async function errorDetail(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
  } catch {
    // Not JSON; fall back to the status code.
  }
  return `Request failed (HTTP ${response.status})`;
}

/** Parse `data: <json>\n\n` frames; chunk boundaries can fall anywhere, so buffer. */
async function* streamEvents(
  path: string,
  body: unknown,
  signal: AbortSignal,
): AsyncGenerator<ChatEvent> {
  const response = await fetch(`${env.apiUrl}${path}`, {
    method: "POST",
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });
  if (response.status === 409) throw new GenerationInProgressError();
  if (!response.ok || !response.body)
    throw new Error(await errorDetail(response));

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
