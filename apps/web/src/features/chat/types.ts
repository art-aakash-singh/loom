import type { components } from "../../api/generated/schema";

export type Message = components["schemas"]["MessageOut"];
export type ChatError = { kind: string; message: string; retryable: boolean };
