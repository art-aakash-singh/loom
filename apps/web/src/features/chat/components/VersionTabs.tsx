import type { Message } from "../types";

type Props = {
  message: Message;
  disabled: boolean;
  onSwitch: (id: string) => void;
};

/**
 * A message with siblings (an edited prompt, a regenerated reply) is a branch point in the
 * tree. Each sibling gets a tab; picking one moves the conversation's leaf onto that branch.
 */
export function VersionTabs({ message, disabled, onSwitch }: Props) {
  const ids = message.sibling_ids;
  if (ids.length < 2) return null;
  const noun = message.role === "user" ? "Version" : "Reply";
  return (
    <div
      className="vtabs"
      role="group"
      aria-label={
        message.role === "user"
          ? "Versions of this prompt"
          : "Versions of this reply"
      }
      data-testid="versions"
    >
      {ids.map((id, i) => {
        const current = id === message.id;
        return (
          <button
            key={id}
            type="button"
            className="vtab"
            aria-current={current ? "true" : undefined}
            disabled={disabled && !current}
            onClick={() => !current && onSwitch(id)}
          >
            {noun} {i + 1}
          </button>
        );
      })}
    </div>
  );
}
