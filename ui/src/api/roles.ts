import { useQuery } from "@tanstack/react-query";
import { api } from "./client";
import type { components } from "./schema";

export type Role = components["schemas"]["RoleResponse"];

/** Should match naming.SUPERADMIN_ROLE. */
export const SUPERADMIN_ROLE = "superadmin";

/** Roles the platform defines. */
export function useRoles() {
  return useQuery({
    queryKey: ["roles"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v3/roles");
      if (error) throw new Error("Failed to load the roles");
      return data;
    },
    staleTime: Infinity,
  });
}

/** The id the role endpoints ask for. Undefined until the roles are known. */
export function useRoleId(name: string): string | undefined {
  const { data } = useRoles();
  return data?.find((role) => role.name === name)?.id;
}
