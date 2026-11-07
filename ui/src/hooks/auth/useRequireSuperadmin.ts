import { useEffect } from "react";
import { useLocation, useNavigate } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { useUserType } from "@/hooks/auth/useUserType";
import { useDeployment } from "@/api/health";
import { appUrl, isAppOrigin } from "@/lib/origins";

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
  const { domain } = useDeployment();
  const { pathname } = useLocation();
  const { noCallsign, forbidden } = messages;
  // Admin routes answer only to a client certificate, which app.* alone presents.
  const elsewhere = !isAppOrigin();

  // Exclusive: a visitor with no session is sent to login, not told they lack a role.
  useEffect(() => {
    if (elsewhere) {
      if (domain) window.location.href = appUrl(domain) + pathname.slice(1);
      return;
    }
    if (isLoading) return;
    if (!callsign) {
      toast.error(t(noCallsign));
      navigate({ to: "/login" });
    } else if (userType !== "superadmin") {
      toast.error(t(forbidden));
      navigate({ to: "/" });
    }
  }, [
    callsign,
    userType,
    isLoading,
    navigate,
    t,
    noCallsign,
    forbidden,
    elsewhere,
    domain,
    pathname,
  ]);

  // Keep the page on its spinner while the browser moves to the app origin.
  return {
    callsign,
    isLoading: isLoading || elsewhere,
    allowed: userType === "superadmin",
  };
}
