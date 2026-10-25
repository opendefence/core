import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { useInitEnrollment } from "@/hooks/api/firstuser/useInitEnrollment";

interface StatusCodeError extends Error {
  statusCode?: number;
}

interface UseCallsignSetupOptions {
  code: string;
}

export function useCallsignSetup({ code }: UseCallsignSetupOptions) {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [errorMessage, setErrorMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleCommonError = (error: StatusCodeError) => {
    setIsSubmitting(false);
    if (error.statusCode === 400) {
      setErrorMessage(t("callsignSetup.errors.alreadyInUse"));
    } else {
      setErrorMessage(t("callsignSetup.errors.unexpected"));
    }
  };

  const clearError = () => setErrorMessage("");

  const { mutate: initEnrollment, isLoading: isLoadingEnrollment } =
    useInitEnrollment({
      onSuccess: (data) => {
        localStorage.setItem("token", data.jwt);
        localStorage.setItem("approveCode", data.approvecode);
        localStorage.setItem("callsign", data.callsign);
        navigate({ to: "/waiting-room" });
      },
      onError: handleCommonError,
    });

  const submitCallsign = (callsign: string) => {
    setIsSubmitting(true);
    setErrorMessage("");
    initEnrollment({ callsign, invite_code: code });
  };

  const isLoading = isSubmitting || isLoadingEnrollment;

  return {
    errorMessage,
    isLoading,
    submitCallsign,
    clearError,
  };
}
