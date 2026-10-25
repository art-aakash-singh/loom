import type { FormEvent } from "react";
import { Pencil, RotateCcw } from "lucide-react";

import type { Message } from "../types";
import { marker, replyFacts, textOf } from "../utils/message";
import { submitOnEnter, useAutosize } from "./Composer";
import { Markdown } from "./Markdown";
import { VersionTabs } from "./VersionTabs";

export type Editing = { id: string; text: string };

type Props = {
  messages: Message[];
  streaming: boolean;
  /** The user message shown optimistically while its turn streams. */
  pendingUser: string | null;
  /** Reply text received so far. */
  reply: string;
  editing: Editing | null;
  onEditChange: (editing: Editing | null) => void;
  onEditSubmit: (e: FormEvent, message: Message) => void;
  onRegenerate: (reply: Message) => void;
  onSwitch: (messageId: string) => void;
};

export function MessageList({
  messages,
  streaming,
  pendingUser,
  reply,
  editing,
  onEditChange,
  onEditSubmit,
  onRegenerate,
  onSwitch,
}: Props) {
  return (
    <ul aria-label="Conversation" className="msgs">
      {messages.map((m, i) => {
        const tabs = (
          <VersionTabs message={m} disabled={streaming} onSwitch={onSwitch} />
        );
        if (m.role === "user") {
          return (
            <li key={m.id} data-role="user" className="msg msg-user">
              {tabs}
              {editing?.id === m.id ? (
                <EditForm
                  editing={editing}
                  onChange={(text) => onEditChange({ id: m.id, text })}
                  onCancel={() => onEditChange(null)}
                  onSubmit={(e) => onEditSubmit(e, m)}
                />
              ) : (
                <div className="msg-user-row">
                  {/* The slot always renders so the bubble keeps one width while a turn streams. */}
                  <div className="msg-actions">
                    {!streaming && (
                      <button
                        type="button"
                        className="btn btn-quiet btn-icon"
                        aria-label="Edit"
                        title="Edit this prompt (creates a new version)"
                        onClick={() =>
                          onEditChange({ id: m.id, text: textOf(m) })
                        }
                      >
                        <Pencil size={15} aria-hidden="true" />
                      </button>
                    )}
                  </div>
                  <div className="msg-bubble">{textOf(m)}</div>
                </div>
              )}
            </li>
          );
        }
        const note = marker(m);
        const text = textOf(m);
        const isLastReply = i === messages.length - 1;
        return (
          <li key={m.id} data-role="assistant" className="msg msg-reply">
            {tabs}
            {text ? (
              <Markdown text={text} />
            ) : (
              <p className="msg-empty">No text was generated.</p>
            )}
            <div className="msg-meta">
              {replyFacts(m).map((fact) => (
                <span key={fact}>{fact}</span>
              ))}
              {note && (
                <span
                  className="msg-flag"
                  data-testid="status-marker"
                  data-tone={m.status === "error" ? "danger" : "warn"}
                >
                  {note}
                </span>
              )}
              {isLastReply && !streaming && (
                <button
                  type="button"
                  className="btn btn-quiet msg-regenerate"
                  onClick={() => onRegenerate(m)}
                >
                  <RotateCcw size={14} aria-hidden="true" />
                  Regenerate
                </button>
              )}
            </div>
          </li>
        );
      })}
      {pendingUser !== null && (
        <li data-role="user" className="msg msg-user">
          <div className="msg-user-row">
            <div className="msg-actions" />
            <div className="msg-bubble">{pendingUser}</div>
          </div>
        </li>
      )}
      {streaming && (
        <li data-role="assistant" className="msg msg-reply" aria-busy="true">
          <div data-testid="reply" className="msg-streaming">
            {reply ? (
              <Markdown text={reply} />
            ) : (
              <span className="msg-thinking">Thinking</span>
            )}
          </div>
        </li>
      )}
    </ul>
  );
}

type EditFormProps = {
  editing: Editing;
  onChange: (text: string) => void;
  onCancel: () => void;
  onSubmit: (e: FormEvent) => void;
};

function EditForm({ editing, onChange, onCancel, onSubmit }: EditFormProps) {
  const ref = useAutosize(editing.text);
  return (
    <form
      className="msg-edit"
      onSubmit={onSubmit}
      onKeyDown={(e) => e.key === "Escape" && onCancel()}
    >
      <textarea
        ref={ref}
        aria-label="Edited message"
        rows={1}
        value={editing.text}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={submitOnEnter}
        autoFocus
      />
      <div className="msg-edit-actions">
        <span className="msg-edit-hint">
          Saving keeps the original as another version.
        </span>
        <button type="button" className="btn btn-quiet" onClick={onCancel}>
          Cancel
        </button>
        <button
          type="submit"
          className="btn btn-primary"
          disabled={!editing.text.trim()}
        >
          Save and send
        </button>
      </div>
    </form>
  );
}
