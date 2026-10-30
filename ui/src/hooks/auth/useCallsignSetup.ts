import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { EnrollError, useEnroll } from "@/api/enrollment";
import { writeStore } from "@/lib/safeStorage";

interface UseCallsignSetupOptions {
  code: string;
}

export function useCallsignSetup({ code }: UseCallsignSetupOptions) {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [errorMessage, setErrorMessage] = useState("");

  const clearError = () => setErrorMessage("");

  const { mutate: enroll, isPending } = useEnroll();

  const submitCallsign = (callsign: string) => {
    setErrorMessage("");
    enroll(
      { code, callsign },
      {
        onSuccess: (status) => {
          writeStore("callsign", status.callsign);
          navigate({ to: "/waiting-room" });
        },
        onError: (error) => {
          const status = error instanceof EnrollError ? error.status : 0;
          if (status === 409) {
            setErrorMessage(t("callsignSetup.errors.alreadyInUse"));
          } else if (status === 404) {
            navigate({ to: "/login", search: { reason: "invite_unusable" } });
          } else {
            setErrorMessage(t("callsignSetup.errors.unexpected"));
          }
        },
      },
    );
  };

  return {
    errorMessage,
    isLoading: isPending,
    submitCallsign,
    clearError,
  };
}
