import createClient from "openapi-fetch";
import type { paths } from "./schema";

// Same origin: Traefik serves /api next to the UI
export const api = createClient<paths>({});
