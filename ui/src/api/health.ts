import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "./client";

/** Deployment name and base domain, as the API reports them. */
export function useDeployment() {
  const { data } = useQuery({
    queryKey: ["health"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v3/health");
      if (error) throw new Error("Health check failed");
      return data;
    },
    staleTime: Infinity,
  });

  const deployment = data?.deployment ?? "";
  useEffect(() => {
    if (deployment) document.title = deployment;
  }, [deployment]);

  return { deployment, domain: data?.domain ?? "" };
}
