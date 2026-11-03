import {
  useMutation,
  useQuery,
  type UseMutationOptions,
} from "@tanstack/react-query";
import { api } from "./client";
import { SUPERADMIN_ROLE, useRoleId } from "./roles";
import type { components } from "./schema";

export type User = components["schemas"]["UserResponse"];
export type UserState = components["schemas"]["UserState"];

/** Whether the user holds the superadmin role, however they came by it. */
export function isAdmin(user: User): boolean {
  return user.effectiveRoles.some((role) => role.name === SUPERADMIN_ROLE);
}

type Options<TData, TVars> = Omit<
  UseMutationOptions<TData, Error, TVars>,
  "mutationFn"
>;

/** The server's own reason, when it sent a plain one. */
function reason(error: unknown, fallback: string): string {
  const detail = (error as { detail?: unknown } | undefined)?.detail;
  return typeof detail === "string" ? detail : fallback;
}

/** Users in one state, or all of them. Given an interval, keeps the list fresh. */
export function useUsers(state?: UserState, pollMs?: number) {
  return useQuery({
    queryKey: ["users", state ?? "all"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v3/users", {
        params: { query: { state } },
      });
      if (error) throw new Error("Failed to load the users");
      return data;
    },
    refetchInterval: pollMs,
  });
}

interface Approval {
  userId: string;
  approvalCode: string;
}

/** Approve a pending user. Only the code they show lets them in. */
export function useApproveUser(options?: Options<User, Approval>) {
  return useMutation({
    mutationFn: async ({ userId, approvalCode }: Approval) => {
      const { data, error } = await api.POST(
        "/api/v3/users/{user_id}/approve",
        {
          params: { path: { user_id: userId } },
          body: { approvalCode },
        },
      );
      if (error) throw new Error(reason(error, "Failed to approve the user"));
      return data;
    },
    ...options,
  });
}

/** The operator defines the superadmin role, so it is missing only while the roles load. */
function roleOrThrow(roleId: string | undefined): string {
  if (!roleId) throw new Error("The superadmin role is unknown");
  return roleId;
}

/** Make the user an administrator. */
export function usePromoteUser(options?: Options<User, string>) {
  const roleId = useRoleId(SUPERADMIN_ROLE);
  return useMutation({
    mutationFn: async (userId: string) => {
      const { data, error } = await api.PUT(
        "/api/v3/users/{user_id}/roles/{role_id}",
        {
          params: {
            path: { user_id: userId, role_id: roleOrThrow(roleId) },
          },
        },
      );
      if (error) throw new Error(reason(error, "Failed to promote the user"));
      return data;
    },
    ...options,
  });
}

/** Take the administrator role back. A group may still grant it. */
export function useDemoteUser(options?: Options<void, string>) {
  const roleId = useRoleId(SUPERADMIN_ROLE);
  return useMutation({
    mutationFn: async (userId: string) => {
      const { error } = await api.DELETE(
        "/api/v3/users/{user_id}/roles/{role_id}",
        {
          params: {
            path: { user_id: userId, role_id: roleOrThrow(roleId) },
          },
        },
      );
      if (error) throw new Error(reason(error, "Failed to demote the user"));
    },
    ...options,
  });
}

/** Take the user's access away. They keep their callsign. */
export function useRevokeUser(options?: Options<User, string>) {
  return useMutation({
    mutationFn: async (userId: string) => {
      const { data, error } = await api.POST("/api/v3/users/{user_id}/revoke", {
        params: { path: { user_id: userId } },
      });
      if (error) throw new Error(reason(error, "Failed to revoke the user"));
      return data;
    },
    ...options,
  });
}
