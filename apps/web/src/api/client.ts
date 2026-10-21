import createClient from "openapi-fetch";

import type { paths } from "./schema";

export const api = createClient<paths>({
  baseUrl: import.meta.env.VITE_API_URL ?? "http://localhost:8000",
});
