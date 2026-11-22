import { useEffect, useRef } from "react";
import { useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { Check, KeyRound, Loader2 } from "lucide-react";
import { CertificateError, useKeystoreCertificate } from "@/api/certificates";
import { useEnrollmentStatus } from "@/api/enrollment";
import { useDeployment } from "@/api/health";
import { clearEnrollment, readToken, writeCertDownloaded } from "@/api/token";
import { CompactHeader } from "@/components/CompactHeader";
import { ClientCertificate } from "@/lib/certificate/native";
import { appUrl } from "@/lib/origins";
import { WizardAction } from "./WizardParts";

export function NativeInstallFlow() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { deployment, domain } = useDeployment();
  const { data: status, isError } = useEnrollmentStatus();
  const userId = status?.id ?? "";
  const commonName = status?.certificateCommonName;
  const uri = status?.certificateUri;

  // An earlier visit may have stored the chain
  const stored = useQuery({
    queryKey: ["clientCertificate"],
    queryFn: () => ClientCertificate.status(),
  });
  const { mutate: request, isSuccess, error } = useKeystoreCertificate();
  const installed = isSuccess || !!stored.data?.hasChain;

  const requested = useRef(false);
  useEffect(() => {
    if (requested.current || !stored.isSuccess || stored.data.hasChain) return;
    if (!commonName || !uri) return;
    requested.current = true;
    request(
      { commonName, uri },
      {
        onError: (error) => {
          const reason =
            error instanceof CertificateError ? error.reason : "failed";
          if (reason !== "approvalUsed")
            toast.error(t(`mtlsInstall.errors.${reason}`));
        },
      },
    );
  }, [stored.isSuccess, stored.data, commonName, uri, request, t]);

  // Stops /login resuming here
  useEffect(() => {
    if (installed && userId) writeCertDownloaded(userId);
  }, [installed, userId]);

  useEffect(() => {
    const spent =
      error instanceof CertificateError && error.reason === "approvalUsed";
    if (!readToken()) navigate({ to: "/login" });
    else if (status && !status.approved) navigate({ to: "/waiting-room" });
    else if (isError || spent) {
      // A kept token would loop back here
      clearEnrollment();
      navigate({ to: "/login", search: { reason: "enrollment_failed" } });
    }
  }, [status, isError, error, navigate]);

  return (
    <div
      data-testid="mtls-install-page"
      data-mtls-layout="native"
      data-native-installed={installed ? "true" : "false"}
      className="flex min-h-dvh flex-col bg-background px-4 pb-4 pt-4"
    >
      <div className="mx-auto flex min-h-0 w-full max-w-md flex-1 flex-col gap-5">
        <CompactHeader deployment={deployment} />

        <h1 className="flex items-center gap-3 text-4xl font-bold leading-tight">
          {installed ? (
            <span className="flex h-10 w-10 flex-none items-center justify-center rounded-full bg-success">
              <Check className="h-6 w-6 text-white" strokeWidth={3} />
            </span>
          ) : (
            <Loader2 className="size-10 flex-none animate-spin" />
          )}
          {installed
            ? t("mtlsInstall.done.title")
            : t("mtlsInstall.native.working")}
        </h1>

        <div className="flex flex-1 flex-col items-center justify-center gap-4 text-center">
          <KeyRound className="size-16 text-muted-foreground" />
          <p className="text-lg text-muted-foreground">
            {t("mtlsInstall.native.explanation")}
          </p>
        </div>

        <WizardAction
          data-testid="mtls-navigate-link"
          disabled={!installed || !domain}
          onClick={() => window.location.assign(appUrl(domain))}
        >
          {t("mtlsInstall.done.action")}
        </WizardAction>
      </div>
    </div>
  );
}
