import { useRef, useState } from "react";
import type { FormEvent } from "react";

import { streamChat } from "./chat/stream";

type ChatError = { kind: string; message: string; retryable: boolean };

export function ChatPage() {
  const [input, setInput] = useState("");
  const [reply, setReply] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [stopReason, setStopReason] = useState<string | null>(null);
  const [error, setError] = useState<ChatError | null>(null);
  const controllerRef = useRef<AbortController | null>(null);

  async function send(e: FormEvent) {
    e.preventDefault();
    const message = input.trim();
    if (!message || streaming) return;

    const controller = new AbortController();
    controllerRef.current = controller;
    setReply("");
    setStopReason(null);
    setError(null);
    setStreaming(true);

    let finished = false;
    try {
      for await (const event of streamChat(message, controller.signal)) {
        if (event.type === "text_delta") {
          setReply((prev) => prev + event.text);
        } else if (event.type === "message_end") {
          finished = true;
          setStopReason(event.stop_reason);
        } else {
          finished = true;
          setError({ kind: event.kind, message: event.message, retryable: event.retryable });
        }
      }
      if (!finished) setError({ kind: "unexpected", message: "Stream ended unexpectedly", retryable: true });
    } catch (err) {
      // A user-initiated Stop is not an error; keep the partial reply.
      if (!controller.signal.aborted) {
        setError({ kind: "unexpected", message: err instanceof Error ? err.message : String(err), retryable: true });
      }
    } finally {
      setStreaming(false);
      controllerRef.current = null;
    }
  }

  return (
    <section>
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
      <p data-testid="reply" style={{ whiteSpace: "pre-wrap" }}>
        {reply}
      </p>
      {stopReason && stopReason !== "complete" && <p role="status">Stopped: {stopReason}</p>}
      {error && (
        <p role="alert">
          Error ({error.kind}): {error.message}
          {error.retryable ? " — you can try again." : ""}
        </p>
      )}
    </section>
  );
}
