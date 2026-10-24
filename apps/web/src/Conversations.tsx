import { useState } from "react";
import type { FormEvent } from "react";

import type { components } from "./api/schema";

export type Conversation = components["schemas"]["ConversationOut"];

type Props = {
  conversations: Conversation[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onCreate: (title: string) => Promise<void>;
};

export function Conversations({ conversations, selectedId, onSelect, onCreate }: Props) {
  const [creating, setCreating] = useState(false);
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function close() {
    setCreating(false);
    setTitle("");
    setError(null);
  }

  async function create(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onCreate(title.trim());
      close();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <nav aria-label="Conversations" style={{ width: 240, flexShrink: 0 }}>
      {creating ? (
        <form onSubmit={(e) => void create(e)} onKeyDown={(e) => e.key === "Escape" && close()}>
          <input
            aria-label="Title"
            placeholder="Title (optional)"
            maxLength={200}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            disabled={busy}
            autoFocus
          />
          <button type="submit" disabled={busy}>
            Create
          </button>
          <button type="button" onClick={close} disabled={busy}>
            Cancel
          </button>
          {error && <p role="alert">{error}</p>}
        </form>
      ) : (
        <button type="button" onClick={() => setCreating(true)}>
          New conversation
        </button>
      )}
      <ul style={{ listStyle: "none", padding: 0 }}>
        {conversations.map((c) => (
          <li key={c.id}>
            <button
              type="button"
              aria-current={c.id === selectedId ? "true" : undefined}
              style={{ fontWeight: c.id === selectedId ? "bold" : "normal" }}
              onClick={() => onSelect(c.id)}
            >
              {c.title ?? "Untitled"}
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}
