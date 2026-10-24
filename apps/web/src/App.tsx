import { useEffect, useState } from "react";

import { api } from "./api/client";
import { ChatPage } from "./ChatPage";
import { readStoredId, storeId } from "./chat/selection";
import { Conversations } from "./Conversations";
import type { Conversation } from "./Conversations";

async function fetchConversations(): Promise<Conversation[]> {
  const { data } = await api.GET("/conversations");
  if (!data) throw new Error("Could not load conversations");
  return data;
}

type State = { kind: "loading" } | { kind: "ok"; status: string } | { kind: "error"; message: string };

export function App() {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [listError, setListError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(readStoredId);
  // Remounts ChatPage when the user opens a conversation. Not tied to selectedId: when
  // ChatPage creates a conversation itself on first send, it must keep streaming, not remount.
  const [chatKey, setChatKey] = useState(0);

  useEffect(() => {
    api
      .GET("/health")
      .then(({ data, error }) => {
        if (data) setState({ kind: "ok", status: data.status });
        else setState({ kind: "error", message: JSON.stringify(error) });
      })
      .catch((e: unknown) => setState({ kind: "error", message: String(e) }));
  }, []);

  function refresh(): Promise<void> {
    return fetchConversations().then(
      (loaded) => {
        setConversations(loaded);
        setListError(null);
      },
      (err: unknown) => setListError(err instanceof Error ? err.message : String(err)),
    );
  }

  useEffect(() => {
    fetchConversations()
      .then(setConversations)
      .catch((err: unknown) => setListError(err instanceof Error ? err.message : String(err)));
  }, []);

  function select(id: string | null) {
    storeId(id);
    setSelectedId(id);
    setChatKey((k) => k + 1);
  }

  async function create(title: string) {
    const { data } = await api.POST("/conversations", { body: { title: title || null } });
    if (!data) throw new Error("Could not create a conversation");
    select(data.id);
    await refresh();
  }

  return (
    <main>
      <h1>Loom</h1>
      <p data-testid="health">
        API health:{" "}
        {state.kind === "loading" ? "checking…" : state.kind === "ok" ? state.status : `error (${state.message})`}
      </p>
      <div style={{ display: "flex", gap: 24 }}>
        <div>
          <Conversations
            conversations={conversations}
            selectedId={selectedId}
            onSelect={select}
            onCreate={create}
          />
          {listError && <p role="alert">{listError}</p>}
        </div>
        <ChatPage
          key={chatKey}
          conversationId={selectedId}
          onCreated={(id) => {
            storeId(id);
            setSelectedId(id);
            void refresh();
          }}
          onMissing={() => {
            storeId(null);
            setSelectedId(null);
            void refresh();
          }}
          onTurnFinished={() => void refresh()}
        />
      </div>
    </main>
  );
}
