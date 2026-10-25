import createClient from "openapi-fetch";

import type { paths } from "../api/generated/schema";
import { env } from "../config/env";

export const api = createClient<paths>({ baseUrl: env.apiUrl });
