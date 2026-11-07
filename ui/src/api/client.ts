import type { UseMutationOptions } from "@tanstack/react-query";
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

/** What a caller may say about a mutation. The call itself belongs to the hook. */
export type Options<TData, TVars> = Omit<
  UseMutationOptions<TData, Error, TVars>,
  "mutationFn"
>;

/** The server's own reason, when it sent a plain one. */
export function reason(error: unknown, fallback: string): string {
  const detail = (error as { detail?: unknown } | undefined)?.detail;
  return typeof detail === "string" ? detail : fallback;
}
