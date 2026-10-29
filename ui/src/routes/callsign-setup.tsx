"use client";

import { createFileRoute, redirect, useNavigate } from "@tanstack/react-router";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useTranslation } from "react-i18next";
import { EnrollmentLayout } from "@/components/enrollment/EnrollmentLayout";
import { CallsignForm } from "@/components/callsign-setup";
import { useCallsignSetup } from "@/hooks/auth/useCallsignSetup";

export const Route = createFileRoute("/callsign-setup")({
  component: CallsignSetupPage,
  validateSearch: (search: Record<string, unknown>): { code: string } => ({
    code: typeof search.code === "string" ? search.code : "",
  }),

  beforeLoad: ({ search }) => {
    if (!search.code) throw redirect({ to: "/login" });
  },
});

function CallsignSetupPage() {
  const navigate = useNavigate();
  const { code } = Route.useSearch();
  const { t } = useTranslation();

  const { errorMessage, isLoading, submitCallsign, clearError } =
    useCallsignSetup({ code });

  return (
    <EnrollmentLayout>
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-3">
          <CardTitle className="text-2xl font-bold text-center">
            {t("callsignSetup.title")}
          </CardTitle>
          <CardDescription className="text-center">
            {t("callsignSetup.usingInvite", { code })}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <CallsignForm
            onSubmit={submitCallsign}
            onBack={() => navigate({ to: "/login" })}
            errorMessage={errorMessage}
            onErrorClear={clearError}
            isLoading={isLoading}
          />
        </CardContent>
      </Card>
    </EnrollmentLayout>
  );
}

export default CallsignSetupPage;
