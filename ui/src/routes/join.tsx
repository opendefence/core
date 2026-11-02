import { createFileRoute } from "@tanstack/react-router";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { QRScanner } from "@/components/approve-users";
import { EnrollmentLayout } from "@/components/enrollment/EnrollmentLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ClientCertificate } from "@/lib/certificate/native";
import { deploymentHost, joinDomain, typedHost } from "@/lib/native";

export const Route = createFileRoute("/join")({
  component: JoinPage,
});

// The query params login reads
const CARRIED = ["code", "guides"];

/** Invite QR codes carry https://<domain>/login?code=… */
function inviteUrl(data: string): URL | null {
  try {
    const url = new URL(data);
    return url.protocol === "https:" && url.pathname === "/login" ? url : null;
  } catch {
    return null;
  }
}

function JoinPage() {
  const { t } = useTranslation();
  const [domain, setDomain] = useState("");

  const join = async (host: string, path: string) => {
    await ClientCertificate.setDomain({ domain: host });
    joinDomain(host, path);
  };

  const readInvite = (data: string) => {
    const url = inviteUrl(data);
    if (!url) {
      toast.error(t("join.notInvite"));
      return false;
    }
    const search = new URLSearchParams();
    for (const key of CARRIED) {
      const value = url.searchParams.get(key);
      if (value) search.set(key, value);
    }
    void join(deploymentHost(url), `/login?${search}`);
    return true;
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    let host: string;
    try {
      host = typedHost(domain);
    } catch {
      toast.error(t("join.invalidDomain"));
      return;
    }
    void join(host, "/login");
  };

  return (
    <EnrollmentLayout>
      <div data-testid="join-page" className="space-y-6">
        <div className="space-y-2 text-center">
          <h1 className="text-2xl font-bold">{t("join.title")}</h1>
          <p className="text-muted-foreground">{t("join.description")}</p>
        </div>

        <div className="flex">
          <QRScanner
            onRead={readInvite}
            trigger={t("join.scan")}
            title={t("join.scan")}
            description={t("join.scanDescription")}
          />
        </div>

        <form onSubmit={submit} className="space-y-3">
          <Label htmlFor="join-domain">{t("join.domain")}</Label>
          <Input
            id="join-domain"
            data-testid="join-domain"
            inputMode="url"
            autoCapitalize="none"
            autoCorrect="off"
            placeholder="local-dev.opendefence.fi"
            value={domain}
            onChange={(event) => setDomain(event.target.value)}
          />
          <Button type="submit" className="w-full" disabled={!domain.trim()}>
            {t("join.continue")}
          </Button>
        </form>
      </div>
    </EnrollmentLayout>
  );
}
