import {
  useMutation,
  useQuery,
  type UseMutationOptions,
} from "@tanstack/react-query";
import { api } from "./client";
import type { components } from "./schema";

export type User = components["schemas"]["UserResponse"];
export type UserState = components["schemas"]["UserState"];

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
