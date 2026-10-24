import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";

import { api } from "./api/client";
import type { components } from "./api/schema";
import { GenerationInProgressError } from "./chat/errors";
import { streamChat } from "./chat/stream";

type Message = components["schemas"]["MessageOut"];
type ChatError = { kind: string; message: string; retryable: boolean };

/** null means the conversation does not exist (any more). */
async function fetchMessages(id: string): Promise<Message[] | null> {
  const { data, response } = await api.GET("/conversations/{conversation_id}", {
    params: { path: { conversation_id: id } },
  });
  if (data) return data.messages;
  if (response.status === 404) return null;
  throw new Error(`Could not load conversation (HTTP ${response.status})`);
}

/**
 * Load history once the turn's reply is finalized. After a normal end the server finalizes
 * before closing the stream, so the first fetch is enough. After Stop the finalize runs just
 * after the disconnect, so retry briefly while that reply is still 'streaming'.
 */
async function fetchMessagesAfterReply(id: string, replyId: string | null): Promise<Message[] | null> {
  const pending = (messages: Message[] | null) =>
    replyId !== null && messages?.find((m) => m.id === replyId)?.status === "streaming";
  let messages = await fetchMessages(id);
  for (let attempt = 0; attempt < 5 && pending(messages); attempt++) {
    await new Promise((resolve) => setTimeout(resolve, 200));
    messages = await fetchMessages(id);
  }
  return messages;
}

function textOf(message: Message): string {
  return message.content.map((block) => block.text).join("");
}

function marker(message: Message): string | null {
  if (message.role !== "assistant") return null;
  if (message.status === "streaming") return "generating…";
  if (message.status === "cancelled") return "cancelled";
  if (message.status === "error") return `failed: ${message.error_kind}`;
  if (message.stop_reason && message.stop_reason !== "complete") return `stopped: ${message.stop_reason}`;
  return null;
}

type Props = {
  /** Read once on mount; App remounts ChatPage (via `key`) to open another conversation. */
  conversationId: string | null;
  /** First send with no conversation open created an (untitled) one. */
  onCreated: (id: string) => void;
  /** The conversation to open no longer exists. */
  onMissing: () => void;
  /** A turn ended, so the conversation's position in the list may have changed. */
  onTurnFinished: () => void;
};

export function ChatPage({ conversationId: initialId, onCreated, onMissing, onTurnFinished }: Props) {
  const [conversationId, setConversationId] = useState<string | null>(initialId);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [pendingUser, setPendingUser] = useState<string | null>(null);
  const [reply, setReply] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<ChatError | null>(null);
  const controllerRef = useRef<AbortController | null>(null);

  // Switching conversations unmounts this page: stop the reply instead of leaking the stream.
  useEffect(() => () => controllerRef.current?.abort(), []);

  // Mount-only on purpose: a new id arrives as a remount, and the callbacks are not inputs.
  useEffect(() => {
    const id = initialId;
    if (!id) return;
    let stale = false;
    fetchMessages(id)
      .then((loaded) => {
        if (stale) return;
        if (loaded) setMessages(loaded);
        else {
          setConversationId(null);
          onMissing();
        }
      })
      .catch((err: unknown) => {
        if (!stale) setError({ kind: "unexpected", message: String(err), retryable: true });
      });
    return () => {
      stale = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function ensureConversation(): Promise<string> {
    if (conversationId) return conversationId;
    const { data } = await api.POST("/conversations");
    if (!data) throw new Error("Could not create a conversation");
    setConversationId(data.id);
    onCreated(data.id);
    return data.id;
  }

  async function send(e: FormEvent) {
    e.preventDefault();
    const message = input.trim();
    if (!message || streaming) return;

    const controller = new AbortController();
    controllerRef.current = controller;
    setReply("");
    setError(null);
    setStreaming(true);

    let id: string | null = null;
    let replyId: string | null = null;
    let finished = false;
    try {
      id = await ensureConversation();
      setPendingUser(message);
      for await (const event of streamChat(id, message, controller.signal)) {
        if (event.type === "turn_started") {
          replyId = event.assistant_message_id;
        } else if (event.type === "text_delta") {
          setReply((prev) => prev + event.text);
        } else {
          finished = true;
          if (event.type === "error") {
            setError({ kind: event.kind, message: event.message, retryable: event.retryable });
          }
        }
      }
      if (!finished) setError({ kind: "unexpected", message: "Stream ended unexpectedly", retryable: true });
    } catch (err) {
      if (err instanceof GenerationInProgressError) {
        setError({ kind: "conflict", message: "A reply is still generating.", retryable: true });
      } else if (!controller.signal.aborted) {
        // A user-initiated Stop is not an error; the cancelled reply is loaded below.
        setError({ kind: "unexpected", message: err instanceof Error ? err.message : String(err), retryable: true });
      }
    } finally {
      controllerRef.current = null;
      if (id) {
        try {
          const loaded = await fetchMessagesAfterReply(id, replyId);
          if (loaded) setMessages(loaded);
        } catch {
          // Keep what we have; a reload will fetch the stored history.
        }
      }
      setPendingUser(null);
      setReply("");
      setStreaming(false);
      if (id) onTurnFinished();
    }
  }

  return (
    <section>
      <ul aria-label="Conversation">
        {messages.map((m) => {
          const note = marker(m);
          return (
            <li key={m.id} data-role={m.role}>
              <strong>{m.role === "user" ? "You" : "Loom"}:</strong>{" "}
              <span style={{ whiteSpace: "pre-wrap" }}>{textOf(m)}</span>
              {note && <em data-testid="status-marker"> [{note}]</em>}
            </li>
          );
        })}
        {pendingUser !== null && (
          <li data-role="user">
            <strong>You:</strong> <span style={{ whiteSpace: "pre-wrap" }}>{pendingUser}</span>
          </li>
        )}
        {streaming && (
          <li data-role="assistant">
            <strong>Loom:</strong>{" "}
            <span data-testid="reply" style={{ whiteSpace: "pre-wrap" }}>
              {reply}
            </span>
          </li>
        )}
      </ul>
      <form onSubmit={(e) => void send(e)}>
        <input
          aria-label="Message"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={streaming}
        />
        {streaming ? (
          <button type="button" onClick={() => controllerRef.current?.abort()}>
            Stop
          </button>
        ) : (
          <button type="submit" disabled={!input.trim()}>
            Send
          </button>
        )}
      </form>
      {error && (
        <p role="alert">
          {error.kind === "conflict"
            ? error.message
            : `Error (${error.kind}): ${error.message}${error.retryable ? " — you can try again." : ""}`}
        </p>
      )}
    </section>
  );
}
