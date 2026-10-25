import { useEffect, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { PanelLeft, X } from "lucide-react";

import { ChatPage } from "../features/chat";
import { Conversations } from "../features/conversations";
import type { Conversation } from "../features/conversations";
import { api } from "../lib/api-client";
import { LoomMark } from "./LoomMark";
import { readStoredId, storeId } from "./selection";
import { ThemeSwitch } from "./ThemeSwitch";
import { useTheme } from "./theme";
import wordmarkUrl from "./wordmark.png";

async function fetchConversations(): Promise<Conversation[]> {
  const { data } = await api.GET("/conversations");
  if (!data) throw new Error("Could not load conversations");
  return data;
}

type State =
  | { kind: "loading" }
  | { kind: "ok"; status: string }
  | { kind: "error"; message: string };

export function App() {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [listError, setListError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(readStoredId);
  // Remounts ChatPage when the user opens a conversation. Not tied to selectedId: when
  // ChatPage creates a conversation itself on first send, it must keep streaming, not remount.
  const [chatKey, setChatKey] = useState(0);
  // Only matters below the narrow breakpoint, where the sidebar becomes a drawer.
  const [navOpen, setNavOpen] = useState(false);
  const [themePreference, setThemePreference] = useTheme();
  const sidebarRef = useRef<HTMLElement>(null);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const wasOpen = useRef(false);

  // Drawer focus: move into the sidebar when it opens, hand back to the toggle when it closes.
  useEffect(() => {
    if (navOpen)
      sidebarRef.current?.querySelector<HTMLElement>("button")?.focus();
    else if (wasOpen.current) toggleRef.current?.focus();
    wasOpen.current = navOpen;
  }, [navOpen]);

  // Widening past the drawer breakpoint closes it, so <main> never stays inert on desktop.
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const wide = window.matchMedia("(min-width: 861px)");
    const close = () => wide.matches && setNavOpen(false);
    wide.addEventListener("change", close);
    return () => wide.removeEventListener("change", close);
  }, []);

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
      (err: unknown) =>
        setListError(err instanceof Error ? err.message : String(err)),
    );
  }

  useEffect(() => {
    fetchConversations()
      .then(setConversations)
      .catch((err: unknown) =>
        setListError(err instanceof Error ? err.message : String(err)),
      );
  }, []);

  function select(id: string | null) {
    storeId(id);
    setSelectedId(id);
    setChatKey((k) => k + 1);
    setNavOpen(false);
  }

  async function create(title: string) {
    const { data } = await api.POST("/conversations", {
      body: { title: title || null },
    });
    if (!data) throw new Error("Could not create a conversation");
    select(data.id);
    await refresh();
  }

  const health =
    state.kind === "loading"
      ? "checking…"
      : state.kind === "ok"
        ? state.status
        : `error (${state.message})`;
  const title =
    conversations.find((c) => c.id === selectedId)?.title ??
    (selectedId ? "Untitled" : "New conversation");

  return (
    <div
      className="shell"
      data-nav-open={navOpen}
      onKeyDown={(e) => navOpen && e.key === "Escape" && setNavOpen(false)}
    >
      <aside className="shell-side" id="sidebar" ref={sidebarRef}>
        <div className="shell-brand">
          <LoomMark size={32} tile />
          <span
            className="shell-wordmark"
            role="img"
            aria-label="Loom"
            style={{ "--wordmark": `url(${wordmarkUrl})` } as CSSProperties}
          />
          <button
            type="button"
            className="btn btn-icon shell-close"
            aria-label="Hide conversations"
            onClick={() => setNavOpen(false)}
          >
            <X size={18} />
          </button>
        </div>
        <Conversations
          conversations={conversations}
          selectedId={selectedId}
          onSelect={select}
          onCreate={create}
        />
        {listError && (
          <p role="alert" className="shell-side-error">
            {listError}
          </p>
        )}
        <div className="shell-foot">
          <p
            data-testid="health"
            className="shell-health"
            data-state={state.kind}
            title={health}
          >
            API health: {health}
          </p>
          <ThemeSwitch value={themePreference} onChange={setThemePreference} />
        </div>
      </aside>
      <div className="shell-scrim" onClick={() => setNavOpen(false)} />
      {/* inert keeps Tab inside the open drawer instead of wandering behind the scrim. */}
      <main className="shell-main" inert={navOpen}>
        <ChatPage
          key={chatKey}
          conversationId={selectedId}
          title={title}
          emptyMark={<LoomMark size={56} />}
          navToggle={
            <button
              ref={toggleRef}
              type="button"
              className="btn btn-quiet btn-icon shell-menu"
              aria-label="Show conversations"
              aria-controls="sidebar"
              aria-expanded={navOpen}
              onClick={() => setNavOpen(true)}
            >
              <PanelLeft size={18} />
            </button>
          }
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
      </main>
    </div>
  );
}
