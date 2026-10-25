import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";

import {
  createConversation,
  fetchMessages,
  fetchMessagesAfterReply,
  switchLeaf,
} from "./api/messages";
import { GenerationInProgressError } from "./api/errors";
import { streamChat, streamRegenerate } from "./api/stream";
import type { ChatEvent } from "./api/stream";
import { Composer } from "./components/Composer";
import { ErrorNotice } from "./components/ErrorNotice";
import { MessageList } from "./components/MessageList";
import type { Editing } from "./components/MessageList";
import type { ChatError, Message } from "./types";
import { formatCount, pathTokens } from "./utils/message";
import "./chat.css";

/** One streamed turn: what to show above it while it streams, and how to start it. */
type Turn = {
  shown: Message[];
  pendingUser: string | null;
  events: (signal: AbortSignal) => AsyncGenerator<ChatEvent>;
};

type Props = {
  /** Read once on mount; App remounts ChatPage (via `key`) to open another conversation. */
  conversationId: string | null;
  /** Heading for the open conversation. */
  title: string;
  /** Slot at the start of the header (the sidebar toggle on narrow screens). */
  navToggle?: ReactNode;
  /** Brand mark shown on the empty state (the app owns the brand assets). */
  emptyMark?: ReactNode;
  /** First send with no conversation open created an (untitled) one. */
  onCreated: (id: string) => void;
  /** The conversation to open no longer exists. */
  onMissing: () => void;
  /** A turn ended, so the conversation's position in the list may have changed. */
  onTurnFinished: () => void;
};

export function ChatPage({
  conversationId: initialId,
  title,
  navToggle,
  emptyMark,
  onCreated,
  onMissing,
  onTurnFinished,
}: Props) {
  const [conversationId, setConversationId] = useState<string | null>(
    initialId,
  );
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [pendingUser, setPendingUser] = useState<string | null>(null);
  const [reply, setReply] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<ChatError | null>(null);
  const [editing, setEditing] = useState<Editing | null>(null);
  const controllerRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  // Follow the reply as it streams, unless the user has scrolled up to read something.
  const pinnedRef = useRef(true);

  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (el && pinnedRef.current) el.scrollTop = el.scrollHeight;
  }, [messages, pendingUser, reply]);

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
        if (!stale)
          setError({
            kind: "unexpected",
            message: String(err),
            retryable: true,
          });
      });
    return () => {
      stale = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function ensureConversation(): Promise<string> {
    if (conversationId) return conversationId;
    const id = await createConversation();
    setConversationId(id);
    onCreated(id);
    return id;
  }

  /** Stream one turn, then load the stored path (the server's view wins over ours). */
  async function runTurn(makeTurn: (conversationId: string) => Turn) {
    if (streaming) return;
    const controller = new AbortController();
    controllerRef.current = controller;
    pinnedRef.current = true;
    setReply("");
    setError(null);
    setEditing(null);
    setStreaming(true);

    let id: string | null = null;
    let replyId: string | null = null;
    let finished = false;
    try {
      id = await ensureConversation();
      const turn = makeTurn(id);
      setMessages(turn.shown);
      setPendingUser(turn.pendingUser);
      for await (const event of turn.events(controller.signal)) {
        if (event.type === "turn_started") {
          replyId = event.assistant_message_id;
        } else if (event.type === "text_delta") {
          setReply((prev) => prev + event.text);
        } else {
          finished = true;
          if (event.type === "error") {
            setError({
              kind: event.kind,
              message: event.message,
              retryable: event.retryable,
            });
          }
        }
      }
      if (!finished)
        setError({
          kind: "unexpected",
          message: "Stream ended unexpectedly",
          retryable: true,
        });
    } catch (err) {
      if (err instanceof GenerationInProgressError) {
        setError({
          kind: "conflict",
          message: "A reply is still generating.",
          retryable: true,
        });
      } else if (!controller.signal.aborted) {
        // A user-initiated Stop is not an error; the cancelled reply is loaded below.
        setError({
          kind: "unexpected",
          message: err instanceof Error ? err.message : String(err),
          retryable: true,
        });
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

  function send(e: FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || streaming) return;
    setInput("");
    void runTurn((id) => ({
      shown: messages,
      pendingUser: text,
      events: (signal) => streamChat(id, text, signal),
    }));
  }

  /** An edit is a new user message beside the old one, under the same parent. */
  function submitEdit(e: FormEvent, message: Message) {
    e.preventDefault();
    const text = editing?.text.trim();
    if (!text) return;
    const at = messages.findIndex((m) => m.id === message.id);
    void runTurn((id) => ({
      shown: messages.slice(0, at),
      pendingUser: text,
      events: (signal) =>
        streamChat(id, text, signal, { parentId: message.parent_id }),
    }));
  }

  function regenerate(reply: Message) {
    const userMessageId = reply.parent_id;
    if (!userMessageId) return;
    const at = messages.findIndex((m) => m.id === reply.id);
    void runTurn((id) => ({
      shown: messages.slice(0, at),
      pendingUser: null,
      events: (signal) => streamRegenerate(id, userMessageId, signal),
    }));
  }

  async function switchTo(messageId: string) {
    if (!conversationId) return;
    setError(null);
    const result = await switchLeaf(conversationId, messageId);
    if ("messages" in result) setMessages(result.messages);
    else
      setError({ kind: "unexpected", message: result.error, retryable: true });
  }

  const turns = messages.filter((m) => m.role === "user").length;
  const empty = messages.length === 0 && pendingUser === null && !streaming;

  return (
    <section className="chat">
      <header className="chat-head">
        {navToggle}
        <h1>{title}</h1>
        {turns > 0 && (
          <p className="chat-stats">
            {turns} {turns === 1 ? "turn" : "turns"} ·{" "}
            {formatCount(pathTokens(messages))} tokens on this path
          </p>
        )}
      </header>
      <div
        className="chat-scroll"
        ref={scrollRef}
        onScroll={(e) => {
          const el = e.currentTarget;
          pinnedRef.current =
            el.scrollHeight - el.scrollTop - el.clientHeight < 80;
        }}
      >
        <div className="chat-col">
          {empty ? (
            <div className="chat-empty">
              {emptyMark}
              <h2>What should we work on?</h2>
              <p>
                Send a message to start. Edit any prompt later to branch the
                conversation into versions.
              </p>
            </div>
          ) : (
            <MessageList
              messages={messages}
              streaming={streaming}
              pendingUser={pendingUser}
              reply={reply}
              editing={editing}
              onEditChange={setEditing}
              onEditSubmit={submitEdit}
              onRegenerate={regenerate}
              onSwitch={(id) => void switchTo(id)}
            />
          )}
        </div>
      </div>
      <div className="chat-dock">
        <div className="chat-col">
          {error && <ErrorNotice error={error} />}
          <Composer
            value={input}
            streaming={streaming}
            onChange={setInput}
            onSubmit={send}
            onStop={() => controllerRef.current?.abort()}
          />
          <p className="chat-hint">
            Enter to send · Shift+Enter for a new line
          </p>
        </div>
      </div>
    </section>
  );
}
