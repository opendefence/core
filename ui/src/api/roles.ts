import { useMutation, useQuery } from "@tanstack/react-query";
import { api, reason, type Options } from "./client";
import type { components } from "./schema";

export type Role = components["schemas"]["RoleResponse"];

/** A user as the role endpoints name them. */
export type Member = components["schemas"]["UserSummary"];

/** Should match naming.SUPERADMIN_ROLE. */
export const SUPERADMIN_ROLE = "superadmin";

/** Names the platform accepts, from models.v1alpha1.integration.ROLE_NAME_PATTERN. */
export const NAME_PATTERN = /^[a-z0-9]([-a-z0-9]*[a-z0-9])?$/;

/** Longest name a Kubernetes resource may carry. */
export const NAME_MAX = 63;

/**
 * Whether the platform keeps the role. An integration owns a managed role, and
 * deleting superadmin would leave nobody able to administer the deployment.
 */
export function isProtected(role: Role): boolean {
  return role.managed || role.name === SUPERADMIN_ROLE;
}

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

/** Users that hold the role directly. A group may grant it to more. */
export function useRoleMembers(roleId: string | undefined) {
  return useQuery({
    queryKey: ["roles", roleId, "members"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v3/roles/{role_id}/members", {
        params: { path: { role_id: roleId ?? "" } },
      });
      if (error) throw new Error("Failed to load the holders of the role");
      return data;
    },
    enabled: roleId !== undefined,
  });
}

interface NewRole {
  name: string;
  displayName: string;
}

/** Create a role. The name is its permanent slug; the API has no rename. */
export function useCreateRole(options?: Options<Role, NewRole>) {
  return useMutation({
    mutationFn: async (role: NewRole) => {
      const { data, error } = await api.POST("/api/v3/roles", { body: role });
      if (error) throw new Error(reason(error, "Failed to create the role"));
      return data;
    },
    ...options,
  });
}

/** Delete a role nothing names any more. The server lists what still does. */
export function useDeleteRole(options?: Options<void, string>) {
  return useMutation({
    mutationFn: async (roleId: string) => {
      const { error } = await api.DELETE("/api/v3/roles/{role_id}", {
        params: { path: { role_id: roleId } },
      });
      if (error) throw new Error(reason(error, "Failed to delete the role"));
    },
    ...options,
  });
}
