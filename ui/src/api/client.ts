import createClient, { type Middleware } from "openapi-fetch";
import type { paths } from "./schema";
import { isAppOrigin } from "@/lib/origins";
import { readToken } from "./token";

// app.* authenticates by client certificate
const authorization: Middleware = {
  onRequest({ request }) {
    const token = isAppOrigin() ? null : readToken();
    if (token) request.headers.set("Authorization", `Bearer ${token}`);
    return request;
  },
};

// Same origin: Traefik serves /api next to the UI
export const api = createClient<paths>({});
api.use(authorization);
