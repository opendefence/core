import { useMutation, useQuery } from "@tanstack/react-query";
import { api, type Options } from "./client";
import type { components } from "./schema";

export type Invite = components["schemas"]["InviteResponse"];

/** Any number of redemptions. */
const UNLIMITED = -1;

/** Mirrors the server's rule in api/lib/invites.py. */
export function isActive(invite: Invite, now: number = Date.now()): boolean {
  const expired =
    invite.validUntil !== null && new Date(invite.validUntil).getTime() <= now;
  const usedUp =
    invite.useCount !== UNLIMITED && invite.used >= invite.useCount;
  return !expired && !usedUp;
}

/** Invites an administrator may manage. Given an interval, keeps the list fresh. */
export function useInvites(pollMs?: number) {
  return useQuery({
    queryKey: ["invites"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v3/invites");
      if (error) throw new Error("Failed to load invites");
      return data;
    },
    refetchInterval: pollMs,
  });
}

/** Create an invite with a server-generated code. */
export function useCreateInvite(options?: Options<Invite, void>) {
  return useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/v3/invites", {
        body: { useCount: UNLIMITED },
      });
      if (error) throw new Error("Failed to create the invite");
      return data;
    },
    ...options,
  });
}

export function useDeleteInvite(options?: Options<void, string>) {
  return useMutation({
    mutationFn: async (id: string) => {
      const { error } = await api.DELETE("/api/v3/invites/{invite_id}", {
        params: { path: { invite_id: id } },
      });
      if (error) throw new Error("Failed to delete the invite");
    },
    ...options,
  });
}

interface SetActive {
  invite: Invite;
  active: boolean;
}

/**
 * Modify an existing invite
 */
export function useSetInviteActive(options?: Options<void, SetActive>) {
  return useMutation({
    mutationFn: async ({ invite, active }: SetActive) => {
      const { error } = await api.PATCH("/api/v3/invites/{invite_id}", {
        params: { path: { invite_id: invite.id } },
        // useCount is resent as it stands: the API replaces every field it gets.
        body: {
          useCount: invite.useCount,
          validUntil: active ? null : new Date().toISOString(),
        },
      });
      if (error) throw new Error("Failed to change the invite");
    },
    ...options,
  });
}
