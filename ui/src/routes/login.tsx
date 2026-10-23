"use client";

import { createFileRoute } from "@tanstack/react-router";
import { useEffect } from "react";
import { LoginHeader } from "@/components/auth/LoginHeader";
import { LoginForm } from "@/components/auth/LoginForm";
import { LanguageSwitcher } from "@/components/auth/LanguageSwitcher";
import { useDeployment } from "@/api/health";
import { baseUrl, appUrl, isAppOrigin } from "@/lib/origins";

interface LoginSearch {
  code?: string;
  /** "off" on an invite link whose creator does not want guides popping up. */
  guides?: string;
}

export const Route = createFileRoute("/login")({
  component: LoginPage,
  validateSearch: (search: Record<string, unknown>): LoginSearch => {
    return {
      code: (search.code as string) || undefined,
      guides: (search.guides as string) || undefined,
    };
  },
});

function LoginPage() {
  const { deployment, domain } = useDeployment();
  const { code: urlCode } = Route.useSearch();

  // Reaching login on the mTLS origin means the certificate did not work
  useEffect(() => {
    if (isAppOrigin() && domain) {
      window.location.href = `${baseUrl(domain)}error?code=mtls_fail`;
    }
  }, [domain]);

  const mtlsUrl = appUrl(domain);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-background p-4">
      <div className="absolute top-4 right-4">
        <LanguageSwitcher />
      </div>

      <div className="w-full max-w-md space-y-8">
        <LoginHeader deployment={deployment} />
        <LoginForm mtlsUrl={mtlsUrl} initialCode={urlCode} />
      </div>
    </div>
  );
}
