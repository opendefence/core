"use client";

import { createFileRoute } from "@tanstack/react-router";
import { useEffect } from "react";
import { LoginForm } from "@/components/auth/LoginForm";
import { EnrollmentLayout } from "@/components/enrollment/EnrollmentLayout";
import { useDeployment } from "@/api/health";
import { baseUrl, appUrl, isAppOrigin } from "@/lib/origins";

interface LoginSearch {
  code?: string;
  /** "off" on an invite link whose creator does not want guides popping up. */
  guides?: string;
}

export const Route = createFileRoute("/login")({
  component: LoginPage,
  validateSearch: (search: Record<string, unknown>): LoginSearch => ({
    code: typeof search.code === "string" ? search.code : undefined,
    guides: typeof search.guides === "string" ? search.guides : undefined,
  }),
});

function LoginPage() {
  const { domain } = useDeployment();
  const { code: urlCode } = Route.useSearch();

  // Reaching login on the mTLS origin means the certificate did not work
  useEffect(() => {
    if (isAppOrigin() && domain) {
      window.location.href = `${baseUrl(domain)}error?code=mtls_fail`;
    }
  }, [domain]);

  return (
    <EnrollmentLayout>
      <LoginForm mtlsUrl={appUrl(domain)} initialCode={urlCode} />
    </EnrollmentLayout>
  );
}
