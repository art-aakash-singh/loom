import { useLayoutEffect, useRef } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import { ArrowUp, Square } from "lucide-react";

type Props = {
  value: string;
  streaming: boolean;
  onChange: (value: string) => void;
  onSubmit: (e: FormEvent) => void;
  onStop: () => void;
};

/** Grows with its content up to the CSS max-height, then scrolls. */
export function useAutosize(value: string) {
  const ref = useRef<HTMLTextAreaElement>(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [value]);
  return ref;
}

/** Enter submits; Shift+Enter (or Enter while an IME is composing) inserts a newline. */
export function submitOnEnter(e: KeyboardEvent<HTMLTextAreaElement>) {
  if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
    e.preventDefault();
    e.currentTarget.form?.requestSubmit();
  }
}

export function Composer({
  value,
  streaming,
  onChange,
  onSubmit,
  onStop,
}: Props) {
  const ref = useAutosize(value);
  return (
    <form className="composer" onSubmit={onSubmit}>
      <textarea
        ref={ref}
        aria-label="Message"
        placeholder="Message Loom"
        rows={1}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={submitOnEnter}
        disabled={streaming}
      />
      {streaming ? (
        <button
          type="button"
          className="btn btn-outline btn-icon composer-action"
          aria-label="Stop"
          onClick={onStop}
        >
          <Square size={14} fill="currentColor" aria-hidden="true" />
        </button>
      ) : (
        <button
          type="submit"
          className="btn btn-primary btn-icon composer-action"
          aria-label="Send"
          disabled={!value.trim()}
        >
          <ArrowUp size={18} strokeWidth={2.25} aria-hidden="true" />
        </button>
      )}
    </form>
  );
}
