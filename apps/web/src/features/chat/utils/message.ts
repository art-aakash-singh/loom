import type { Message } from "../types";

export function textOf(message: Message): string {
  return message.content.map((block) => block.text).join("");
}

export function marker(message: Message): string | null {
  if (message.role !== "assistant") return null;
  if (message.status === "streaming") return "generating…";
  if (message.status === "cancelled") return "cancelled";
  if (message.status === "error") return `failed: ${message.error_kind}`;
  if (message.stop_reason && message.stop_reason !== "complete")
    return `stopped: ${message.stop_reason}`;
  return null;
}

const count = new Intl.NumberFormat("en");

/** The quiet facts under a reply: which model, what it cost, how long it took. */
export function replyFacts(message: Message): string[] {
  const facts: string[] = [];
  if (message.model) facts.push(message.model);
  if (message.usage) {
    facts.push(
      `${count.format(message.usage.input_tokens)} in`,
      `${count.format(message.usage.output_tokens)} out`,
    );
  }
  if (message.status === "complete" && message.stop_reason === "complete")
    facts.push("complete");
  if (message.finished_at) {
    const ms =
      new Date(message.finished_at).getTime() -
      new Date(message.created_at).getTime();
    if (ms > 0) facts.push(`${(ms / 1000).toFixed(1)} s`);
  }
  return facts;
}

/** Tokens stored for the messages on the active path (what a fresh turn would start from). */
export function pathTokens(messages: Message[]): number {
  return messages.reduce((sum, m) => sum + (m.token_count ?? 0), 0);
}

export function formatCount(n: number): string {
  return count.format(n);
}
