import { CircleAlert } from "lucide-react";

import type { ChatError } from "../types";

export function ErrorNotice({ error }: { error: ChatError }) {
  return (
    <div role="alert" className="chat-error">
      <CircleAlert size={16} aria-hidden="true" />
      <p>
        {error.kind === "conflict"
          ? error.message
          : `The reply didn't finish (${error.kind}): ${error.message.replace(/\.$/, "")}.${error.retryable ? " You can try again." : ""}`}
      </p>
    </div>
  );
}
