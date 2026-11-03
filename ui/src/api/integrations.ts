import { useQuery } from "@tanstack/react-query";
import { api } from "./client";
import type { components } from "./schema";

export type Product = components["schemas"]["IntegrationResponse"];

export const PRODUCT_POLL_MS = 30000;

const PRODUCT_TIMEOUT_MS = 10000;

/** Past two missed reads the states are unknown, not what they last were. */
export const PRODUCT_STALE_AFTER_MS = PRODUCT_POLL_MS * 2 + PRODUCT_TIMEOUT_MS;

async function read(language: string) {
  const { data, error } = await api.GET("/api/v3/integrations", {
    params: { query: { language } },
    signal: AbortSignal.timeout(PRODUCT_TIMEOUT_MS),
  });
  if (error) throw new Error("Failed to load the products");
  return data;
}

/** Products installed on the platform, in the closest language they offer. */
export function useProducts(language: string) {
  return useQuery({
    queryKey: ["integrations", language],
    queryFn: () => read(language),
  });
}

/** The same products, kept fresh. Its own entry, so polling never redraws the grid. */
export function useProductStatus(language: string) {
  return useQuery({
    queryKey: ["integrations", "status", language],
    queryFn: () => read(language),
    refetchInterval: PRODUCT_POLL_MS,
    retry: 1,
  });
}
