import { useEffect, useState } from "react";

import { api } from "./api/client";
import { ChatPage } from "./ChatPage";

type State = { kind: "loading" } | { kind: "ok"; status: string } | { kind: "error"; message: string };

export function App() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    api
      .GET("/health")
      .then(({ data, error }) => {
        if (data) setState({ kind: "ok", status: data.status });
        else setState({ kind: "error", message: JSON.stringify(error) });
      })
      .catch((e: unknown) => setState({ kind: "error", message: String(e) }));
  }, []);

  return (
    <main>
      <h1>Loom</h1>
      <p data-testid="health">
        API health:{" "}
        {state.kind === "loading" ? "checking…" : state.kind === "ok" ? state.status : `error (${state.message})`}
      </p>
      <ChatPage />
    </main>
  );
}
