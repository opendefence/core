import { useQuery } from "@tanstack/react-query";
import { api } from "./client";
import type { components } from "./schema";

/** An installed integration, as the UI shows it: a product card. */
export type Product = components["schemas"]["IntegrationResponse"];

/** Products installed on the platform, in the closest language they offer. */
export function useProducts(language: string) {
  return useQuery({
    queryKey: ["integrations", language],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v3/integrations", {
        params: { query: { language } },
      });
      if (error) throw new Error("Failed to load the products");
      return data;
    },
  });
}
