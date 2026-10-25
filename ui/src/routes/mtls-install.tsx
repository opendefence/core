"use client";

import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect, useRef } from "react";
import { toast } from "sonner";
import { CertificateError, useCertificate } from "@/api/certificates";
import { useEnrollmentStatus } from "@/api/enrollment";
import { downloadBlob } from "@/lib/downloadBlob";
import {
  useGuidePreferences,
  withGuidePreference,
} from "@/hooks/useGuidePreferences";
import { useTranslation } from "react-i18next";
import { useIsMobile } from "@/hooks/use-mobile";
import { MtlsInstructions } from "@/components/mtls/MtlsInstructions";
import { MtlsPasswordDisplay } from "@/components/mtls/MtlsPasswordDisplay";
import { MtlsExplanationCard } from "@/components/mtls/MtlsExplanationCard";
import { MtlsPageHeader } from "@/components/mtls/MtlsPageHeader";
import { MtlsActionButtons } from "@/components/mtls/MtlsActionButtons";
import { PlatformSelector } from "@/components/mtls/PlatformSelector";
import { AndroidInstallFlow } from "@/components/mtls/AndroidInstallFlow";
import { IosInstallFlow } from "@/components/mtls/IosInstallFlow";
import { MacInstallFlow } from "@/components/mtls/MacInstallFlow";
import { WinInstallFlow } from "@/components/mtls/WinInstallFlow";
import { LinuxInstallFlow } from "@/components/mtls/LinuxInstallFlow";
import { CompactHeader } from "@/components/CompactHeader";
import { readStore, writeStore } from "@/lib/safeStorage";
import {
  getOperatingSystem,
  PLATFORM_INSTRUCTIONS,
} from "@/components/mtls/platformUtils";
import { useDeployment } from "@/api/health";
import { appUrl } from "@/lib/origins";
import { LanguageSwitcher } from "@/components/auth/LanguageSwitcher";
import { HelpCircle } from "lucide-react";
import { MtlsGuide } from "@/components/guides";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/mtls-install")({
  component: MtlsInstallPage,
});

// Platforms we walk through the install one screen at a time.
const GUIDED = ["Android", "iOS"];
const GUIDED_DESKTOP = ["MacOS", "Windows", "Linux"];
const isGuidedOS = (os: string) =>
  GUIDED.includes(os) || GUIDED_DESKTOP.includes(os);

function MtlsInstallPage() {
  const { t } = useTranslation();
  const isMobile = useIsMobile();

  const [selectedOS, setSelectedOS] = useState("");
  const [userOS, setUserOS] = useState("");
  const [showGuide, setShowGuide] = useState(false);
  const { autoOpen } = useGuidePreferences();
  const [certDownloaded, setCertDownloaded] = useState<boolean>(
    () => readStore("cert_downloaded") === "true",
  );
  // Counts completed downloads rather than tracking a flag: re-downloading has
  // to move the Android flow on again, and the flag is already true by then.
  const [downloadCount, setDownloadCount] = useState(0);
  const { deployment, domain } = useDeployment();

  useEffect(() => {
    setUserOS(getOperatingSystem());
  }, []);

  const osToShow = selectedOS || userOS;
  const guided = isGuidedOS(osToShow);

  useEffect(() => {
    if (!userOS) return;
    // The guided flows are the walkthrough, so the guide would only cover them.
    // The help button still opens it; only the uninvited appearance stops.
    if (autoOpen && !isGuidedOS(userOS)) setShowGuide(true);
  }, [autoOpen, userOS]);

  const mtlsUrl = withGuidePreference(appUrl(domain));

  const { data: status } = useEnrollmentStatus();
  const callsign = status?.callsign ?? "";
  const commonName = status?.certificateCommonName;
  const uri = status?.certificateUri;

  const { mutate: request, data: bundle, isPending } = useCertificate();

  // The certificate is made as soon as identity is known.
  const requested = useRef(false);
  useEffect(() => {
    if (requested.current || !commonName || !uri) return;
    requested.current = true;
    request(
      { commonName, uri },
      {
        onError: (error) => {
          const reason =
            error instanceof CertificateError ? error.reason : "failed";
          toast.error(t(`mtlsInstall.errors.${reason}`));
        },
      },
    );
  }, [commonName, uri, request, t]);

  const canNavigate = certDownloaded;

  const handleDownloadKey = () => {
    if (!bundle) return;
    downloadBlob(
      new Blob([bundle.pfx], { type: "application/x-pkcs12" }),
      `${callsign}_${deployment}.pfx`,
    );
    writeStore("cert_downloaded", "true");
    setCertDownloaded(true);
    setDownloadCount((n) => n + 1);
    if (!guided) toast.success(t("mtlsInstall.certificateDownloaded"));
  };

  const chooseOS = setSelectedOS;

  const platformInstructions =
    PLATFORM_INSTRUCTIONS[osToShow] || PLATFORM_INSTRUCTIONS.Android;

  if (guided && GUIDED_DESKTOP.includes(osToShow)) {
    return (
      <>
        <MtlsGuide open={showGuide} onOpenChange={setShowGuide} />

        <div
          data-testid="mtls-install-page"
          data-mtls-layout="guided-desktop"
          data-mtls-os={osToShow}
          className="flex min-h-dvh flex-col bg-background px-6 py-6"
        >
          <div className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-10">
            <CompactHeader
              deployment={deployment}
              onHelp={() => setShowGuide(true)}
            />
            <div className="my-auto pb-10">
              {osToShow === "Linux" ? (
                <LinuxInstallFlow
                  callsign={callsign}
                  certName={commonName ?? ""}
                  deployment={deployment}
                  fileName={`${callsign}_${deployment}.pfx`}
                  mtlsUrl={mtlsUrl}
                  onDownload={handleDownloadKey}
                  isDownloading={isPending}
                  password={bundle?.pin ?? ""}
                  downloadCount={downloadCount}
                  platformPicker={
                    <PlatformSelector
                      value={osToShow}
                      onValueChange={chooseOS}
                      triggerLabel={t("mtlsInstall.linux.notLinux")}
                    />
                  }
                />
              ) : osToShow === "Windows" ? (
                <WinInstallFlow
                  callsign={callsign}
                  certName={commonName ?? ""}
                  deployment={deployment}
                  fileName={`${callsign}_${deployment}.pfx`}
                  mtlsUrl={mtlsUrl}
                  onDownload={handleDownloadKey}
                  isDownloading={isPending}
                  password={bundle?.pin ?? ""}
                  downloadCount={downloadCount}
                  platformPicker={
                    <PlatformSelector
                      value={osToShow}
                      onValueChange={chooseOS}
                      triggerLabel={t("mtlsInstall.win.notWindows")}
                    />
                  }
                />
              ) : (
                <MacInstallFlow
                  callsign={callsign}
                  certName={commonName ?? ""}
                  deployment={deployment}
                  fileName={`${callsign}_${deployment}.pfx`}
                  mtlsUrl={mtlsUrl}
                  onDownload={handleDownloadKey}
                  isDownloading={isPending}
                  password={bundle?.pin ?? ""}
                  downloadCount={downloadCount}
                  platformPicker={
                    <PlatformSelector
                      value={osToShow}
                      onValueChange={chooseOS}
                      triggerLabel={t("mtlsInstall.mac.notMac")}
                    />
                  }
                />
              )}
            </div>
          </div>
        </div>
      </>
    );
  }

  if (guided) {
    return (
      <>
        <MtlsGuide open={showGuide} onOpenChange={setShowGuide} />

        <div
          data-testid="mtls-install-page"
          data-mtls-layout="guided"
          data-mtls-os={osToShow}
          className="flex min-h-dvh flex-col bg-background px-4 pb-4 pt-4"
        >
          <div className="mx-auto flex min-h-0 w-full max-w-md flex-1 flex-col gap-4">
            <CompactHeader
              deployment={deployment}
              onHelp={() => setShowGuide(true)}
            />

            {osToShow === "iOS" ? (
              <IosInstallFlow
                callsign={callsign}
                certName={commonName ?? ""}
                mtlsUrl={mtlsUrl}
                onDownload={handleDownloadKey}
                isDownloading={isPending}
                password={bundle?.pin ?? ""}
                downloadCount={downloadCount}
                platformPicker={
                  <PlatformSelector
                    value={osToShow}
                    onValueChange={chooseOS}
                    triggerLabel={t("mtlsInstall.ios.notIos")}
                  />
                }
              />
            ) : (
              <AndroidInstallFlow
                callsign={callsign}
                fileName={`${callsign}_${deployment}.pfx`}
                mtlsUrl={mtlsUrl}
                onDownload={handleDownloadKey}
                isDownloading={isPending}
                password={bundle?.pin ?? ""}
                downloadCount={downloadCount}
                platformPicker={
                  <PlatformSelector
                    value={osToShow}
                    onValueChange={chooseOS}
                    triggerLabel={t("mtlsInstall.android.notAndroid")}
                  />
                }
              />
            )}
          </div>
        </div>
      </>
    );
  }

  if (isMobile) {
    return (
      <>
        <MtlsGuide open={showGuide} onOpenChange={setShowGuide} />

        <div
          data-testid="mtls-install-page"
          data-mtls-layout="mobile"
          data-mtls-os={osToShow || ""}
          className="min-h-screen flex flex-col bg-background"
        >
          <div className="flex justify-between items-center p-6 border-b border-border">
            <Button
              data-testid="mtls-help-button"
              variant="ghost"
              size="icon"
              onClick={() => setShowGuide(true)}
              aria-label={t("common.help")}
            >
              <HelpCircle className="w-5 h-5" />
            </Button>
            <LanguageSwitcher />
          </div>

          <div className="flex-1 flex flex-col items-center justify-start overflow-y-auto p-6">
            <div className="w-full max-w-6xl space-y-8 py-8">
              <MtlsPageHeader deployment={deployment} />

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 auto-rows-max">
                <div className="lg:col-span-1 space-y-6">
                  <PlatformSelector value={osToShow} onValueChange={chooseOS} />
                  <MtlsPasswordDisplay password={bundle?.pin ?? ""} />
                  <MtlsActionButtons
                    onDownload={handleDownloadKey}
                    isDownloading={isPending}
                    mtlsUrl={mtlsUrl}
                    disabled={!bundle}
                    canNavigate={canNavigate}
                  />
                </div>

                <div className="lg:col-span-2 space-y-6">
                  <MtlsExplanationCard />
                  <MtlsInstructions instructions={platformInstructions} />
                </div>
              </div>
            </div>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <MtlsGuide open={showGuide} onOpenChange={setShowGuide} />

      <div
        data-testid="mtls-install-page"
        data-mtls-layout="desktop"
        data-mtls-os={osToShow || ""}
        className="min-h-screen flex flex-col items-center justify-start bg-background p-4"
      >
        <div className="w-full max-w-3xl space-y-6 py-8">
          <div className="absolute top-4 right-4 flex items-center gap-2">
            <Button
              data-testid="mtls-help-button"
              variant="ghost"
              size="icon"
              onClick={() => setShowGuide(true)}
              aria-label={t("common.help")}
            >
              <HelpCircle className="w-5 h-5" />
            </Button>
            <LanguageSwitcher />
          </div>

          <MtlsPageHeader deployment={deployment} />

          <MtlsExplanationCard />

          <PlatformSelector value={osToShow} onValueChange={chooseOS} />

          <MtlsInstructions instructions={platformInstructions} />

          <MtlsPasswordDisplay password={bundle?.pin ?? ""} />

          <MtlsActionButtons
            onDownload={handleDownloadKey}
            isDownloading={isPending}
            mtlsUrl={mtlsUrl}
            disabled={!bundle}
            canNavigate={canNavigate}
          />
        </div>
      </div>
    </>
  );
}

export default MtlsInstallPage;
