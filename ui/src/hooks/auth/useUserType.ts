import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { readToken } from "@/api/token";
import type { components } from "@/api/schema";
import { isAppOrigin } from "@/lib/origins";

type UserResponse = components["schemas"]["UserResponse"];

// Should match naming.SUPERADMIN_ROLE.
const SUPERADMIN_ROLE = "superadmin";

function typeOf(user: UserResponse): "superadmin" | "user" {
  return user.effectiveRoles.some((role) => role.name === SUPERADMIN_ROLE)
    ? SUPERADMIN_ROLE
    : "user";
}

export function useUserType() {
  const { data, isLoading } = useQuery({
    queryKey: ["users", "me"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v3/users/me");
      if (error) throw new Error("Not authenticated");
      return data;
    },
    // On app.* the certificate answers for us, elsewhere only a token can.
    enabled: isAppOrigin() || readToken() !== null,
    retry: false,
    staleTime: Infinity,
  });

  return {
    userType: data ? typeOf(data) : null,
    isLoading,
    callsign: data?.callsign ?? null,
    isValidUser: data !== undefined,
  };
}
