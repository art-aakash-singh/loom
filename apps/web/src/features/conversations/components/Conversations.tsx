import { useState } from "react";
import type { FormEvent } from "react";
import { SquarePen } from "lucide-react";

import type { Conversation } from "../types";
import { groupByActivity } from "../utils/group";
import "./conversations.css";

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
    <nav aria-label="Conversations" className="convs">
      <div className="convs-top">
        {creating ? (
          <form className="convs-create" onSubmit={(e) => void create(e)} onKeyDown={(e) => e.key === "Escape" && close()}>
            <input
              aria-label="Title"
              placeholder="Title (optional)"
              maxLength={200}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              disabled={busy}
              autoFocus
            />
            <div className="convs-create-actions">
              <button type="button" className="convs-btn" onClick={close} disabled={busy}>
                Cancel
              </button>
              <button type="submit" className="convs-btn convs-btn-solid" disabled={busy}>
                Create
              </button>
            </div>
            {error && (
              <p role="alert" className="convs-error">
                {error}
              </p>
            )}
          </form>
        ) : (
          <button type="button" className="convs-new" onClick={() => setCreating(true)}>
            <SquarePen size={16} aria-hidden="true" />
            New conversation
          </button>
        )}
      </div>
      <div className="convs-scroll">
        {conversations.length === 0 ? (
          <p className="convs-empty">No conversations yet. Send a message and it will appear here.</p>
        ) : (
          groupByActivity(conversations).map((group) => (
            <section key={group.label} className="convs-group">
              <h2>{group.label}</h2>
              <ul>
                {group.items.map((c) => (
                  <li key={c.id}>
                    <button
                      type="button"
                      className="convs-item"
                      aria-current={c.id === selectedId ? "true" : undefined}
                      title={c.title ?? "Untitled"}
                      onClick={() => onSelect(c.id)}
                    >
                      {c.title ?? "Untitled"}
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          ))
        )}
      </div>
    </nav>
  );
}
