import type { Conversation } from "../types";

export type ConversationGroup = { label: string; items: Conversation[] };

const DAY = 24 * 60 * 60 * 1000;

/** Buckets by last activity, keeping the server's order inside each bucket. */
export function groupByActivity(conversations: Conversation[], now: Date = new Date()): ConversationGroup[] {
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const buckets: ConversationGroup[] = [
    { label: "Today", items: [] },
    { label: "Yesterday", items: [] },
    { label: "Previous 7 days", items: [] },
    { label: "Older", items: [] },
  ];
  for (const c of conversations) {
    const at = new Date(c.updated_at).getTime();
    const index = at >= startOfToday ? 0 : at >= startOfToday - DAY ? 1 : at >= startOfToday - 7 * DAY ? 2 : 3;
    buckets[index]!.items.push(c);
  }
  return buckets.filter((b) => b.items.length > 0);
}
