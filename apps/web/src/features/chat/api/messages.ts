import { api } from "../../../lib/api-client";
import type { Message } from "../types";

/** null means the conversation does not exist (any more). */
export async function fetchMessages(id: string): Promise<Message[] | null> {
  const { data, response } = await api.GET("/conversations/{conversation_id}", {
    params: { path: { conversation_id: id } },
  });
  if (data) return data.messages;
  if (response.status === 404) return null;
  throw new Error(`Could not load conversation (HTTP ${response.status})`);
}

/**
 * Load history once the turn's reply is finalized. After a normal end the server finalizes
 * before closing the stream, so the first fetch is enough. After Stop the finalize runs just
 * after the disconnect, so retry briefly while that reply is still 'streaming'.
 */
export async function fetchMessagesAfterReply(
  id: string,
  replyId: string | null,
): Promise<Message[] | null> {
  const pending = (messages: Message[] | null) =>
    replyId !== null &&
    messages?.find((m) => m.id === replyId)?.status === "streaming";
  let messages = await fetchMessages(id);
  for (let attempt = 0; attempt < 5 && pending(messages); attempt++) {
    await new Promise((resolve) => setTimeout(resolve, 200));
    messages = await fetchMessages(id);
  }
  return messages;
}

export async function createConversation(): Promise<string> {
  const { data } = await api.POST("/conversations");
  if (!data) throw new Error("Could not create a conversation");
  return data.id;
}

/** Point the conversation at another branch; resolves to that branch's path, or an error message. */
export async function switchLeaf(
  conversationId: string,
  messageId: string,
): Promise<{ messages: Message[] } | { error: string }> {
  const { data, response } = await api.PUT(
    "/conversations/{conversation_id}/leaf",
    {
      params: { path: { conversation_id: conversationId } },
      body: { message_id: messageId },
    },
  );
  return data
    ? { messages: data.messages }
    : { error: `Could not switch (HTTP ${response.status})` };
}
