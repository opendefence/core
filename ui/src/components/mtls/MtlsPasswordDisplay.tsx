"use client";

import { useTranslation } from "react-i18next";

interface MtlsPasswordDisplayProps {
  password: string;
}

export function MtlsPasswordDisplay({ password }: MtlsPasswordDisplayProps) {
  const { t } = useTranslation();

  return (
    <div
      data-testid="mtls-password-display"
      data-password={password}
      className="pt-2 p-4 bg-muted/50 border border-border rounded-lg"
    >
      <p className="text-sm text-muted-foreground">
        <span className="font-semibold">{t("mtlsInstall.password")} </span>
        <span className="font-mono font-semibold text-foreground bg-card px-2 py-0.5 rounded inline-block mt-1">
          {password}
        </span>
      </p>
    </div>
  );
}
