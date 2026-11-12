import { useQuery } from "@tanstack/react-query";
import { api } from "./client";
import type { components } from "./schema";

export type Group = components["schemas"]["GroupResponse"];

/** Every group on the platform. The hierarchy follows parentId. */
export function useGroups() {
  return useQuery({
    queryKey: ["groups"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v3/groups");
      if (error) throw new Error("Failed to load the groups");
      return data;
    },
  });
}

/** Groups that grant the role to their effective members. */
export function granting(groups: Group[] | undefined, roleId: string): Group[] {
  return (
    groups?.filter((group) => group.roles.some((r) => r.id === roleId)) ?? []
  );
}
