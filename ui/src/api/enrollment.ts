import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "./client";
import { writeToken } from "./token";

// 404 means the invite ran out, 409 that someone else holds the callsign.
export class EnrollError extends Error {
  status: number;

  constructor(status: number) {
    super(`Enrollment failed with ${status}`);
    this.status = status;
    this.name = "EnrollError";
  }
}

/** Whether an invite code can still be redeemed. */
export function useCheckCode() {
  return useMutation({
    mutationFn: async (code: string) => {
      const { data, error } = await api.POST("/api/v3/enrollment/check", {
        body: { code },
      });
      if (error) throw new Error("Code check failed");
      return data.valid;
    },
  });
}

/** Redeem an invite code, keeping the token it returns. */
export function useEnroll() {
  return useMutation({
    mutationFn: async (body: { code: string; callsign: string }) => {
      const { data, error, response } = await api.POST("/api/v3/enrollment", {
        body,
      });
      if (error) throw new EnrollError(response.status);
      writeToken(data.token.accessToken);
      return data.status;
    },
  });
}

/** The caller's own enrollment. Given an interval, polls until they are approved. */
export function useEnrollmentStatus(pollMs?: number) {
  return useQuery({
    queryKey: ["enrollment"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v3/enrollment");
      if (error) throw new Error("Enrollment status failed");
      return data;
    },
    refetchInterval: ({ state }) =>
      pollMs !== undefined && !state.data?.approved ? pollMs : false,
  });
}
