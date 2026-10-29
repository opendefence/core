"use client";

import { createFileRoute } from "@tanstack/react-router";
import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { TriangleAlert } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { LoginForm } from "@/components/auth/LoginForm";
import { EnrollmentLayout } from "@/components/enrollment/EnrollmentLayout";
import { useDeployment } from "@/api/health";
import { baseUrl, appUrl, isAppOrigin } from "@/lib/origins";

interface LoginSearch {
  code?: string;
  /** "off" on an invite link whose creator does not want guides popping up. */
  guides?: string;
  /** Why enrollment sent them back here. Each value needs a login.reasons key. */
  reason?: string;
}

const REASONS = ["enrollment_failed"];

export const Route = createFileRoute("/login")({
  component: LoginPage,
  validateSearch: (search: Record<string, unknown>): LoginSearch => ({
    code: typeof search.code === "string" ? search.code : undefined,
    guides: typeof search.guides === "string" ? search.guides : undefined,
    reason:
      typeof search.reason === "string" && REASONS.includes(search.reason)
        ? search.reason
        : undefined,
  }),
});

function LoginPage() {
  const { t } = useTranslation();
  const { domain } = useDeployment();
  const { code: urlCode, reason } = Route.useSearch();

  // Reaching login on the mTLS origin means the certificate did not work
  useEffect(() => {
    if (isAppOrigin() && domain) {
      window.location.href = `${baseUrl(domain)}error?code=mtls_fail`;
    }
  }, [domain]);

  return (
    <EnrollmentLayout>
      {reason && (
        <Alert
          data-testid="login-reason"
          data-reason={reason}
          variant="warning"
          className="mb-4"
        >
          <TriangleAlert />
          <AlertTitle>{t(`login.reasons.${reason}.title`)}</AlertTitle>
          <AlertDescription>
            {t(`login.reasons.${reason}.description`)}
          </AlertDescription>
        </Alert>
      )}
      <LoginForm mtlsUrl={appUrl(domain)} initialCode={urlCode} />
    </EnrollmentLayout>
  );
}
