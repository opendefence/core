import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { readToken } from "@/api/token";
import { SUPERADMIN_ROLE } from "@/api/roles";
import { isAdmin, type User } from "@/api/users";
import { isAppOrigin } from "@/lib/origins";

function typeOf(user: User): "superadmin" | "user" {
  return isAdmin(user) ? SUPERADMIN_ROLE : "user";
}

export function useUserType() {
  const certified = isAppOrigin();
  const { data, isLoading } = useQuery({
    queryKey: certified ? ["users", "me"] : ["enrollment"],
    queryFn: async () => {
      const { data, error } = certified
        ? await api.GET("/api/v3/users/me")
        : await api.GET("/api/v3/enrollment");
      if (error) throw new Error("Not authenticated");
      return data;
    },
    enabled: certified || readToken() !== null,
    retry: false,
    staleTime: Infinity,
  });

  return {
    userType: data && "effectiveRoles" in data ? typeOf(data) : null,
    isLoading,
    callsign: data?.callsign ?? null,
    isValidUser: data !== undefined,
  };
}
