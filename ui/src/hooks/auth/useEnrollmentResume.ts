import { useEffect, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { useEnrollmentStatus } from "@/api/enrollment";
import { clearEnrollment, readCertDownloaded, readToken } from "@/api/token";

/** Resume the step a vouched-for token left. Returns true while deciding. */
export function useEnrollmentResume(): boolean {
  const navigate = useNavigate();
  const [checking, setChecking] = useState(() => readToken() !== null);
  const { data: status, isError } = useEnrollmentStatus(undefined, checking);

  useEffect(() => {
    if (!checking) return;
    if (status) {
      if (readCertDownloaded(status.callsign)) setChecking(false);
      else
        navigate({ to: status.approved ? "/mtls-install" : "/waiting-room" });
    } else if (isError) {
      clearEnrollment();
      setChecking(false);
    }
  }, [checking, status, isError, navigate]);

  return checking;
}
