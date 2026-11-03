import { useEffect } from "react";
import { useNavigate } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { useUserType } from "@/hooks/auth/useUserType";

interface Messages {
  /** Translation keys for the two ways in. */
  noCallsign: string;
  forbidden: string;
}

/** Send anyone who may not be on an admin page away, and say whether to render it. */
export function useRequireSuperadmin(messages: Messages) {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { userType, isLoading, callsign } = useUserType();
  const { noCallsign, forbidden } = messages;

  // Exclusive: a visitor with no session is sent to login, not told they lack a role.
  useEffect(() => {
    if (isLoading) return;
    if (!callsign) {
      toast.error(t(noCallsign));
      navigate({ to: "/login" });
    } else if (userType !== "superadmin") {
      toast.error(t(forbidden));
      navigate({ to: "/" });
    }
  }, [callsign, userType, isLoading, navigate, t, noCallsign, forbidden]);

  return { callsign, isLoading, allowed: userType === "superadmin" };
}
