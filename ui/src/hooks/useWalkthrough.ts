import { useEffect, useState } from "react";
import { useGuidePreferences } from "@/hooks/useGuidePreferences";

/** useState pair for a walkthrough dialog that opens itself once per browser. */
export function useWalkthrough(key: string, ready: boolean) {
  const { autoOpen } = useGuidePreferences();
  const [open, setOpen] = useState(false);

  // The help button still opens it; only the uninvited appearance stops.
  useEffect(() => {
    if (!autoOpen || !ready || localStorage.getItem(key)) return;
    localStorage.setItem(key, "true");
    setOpen(true);
  }, [key, ready, autoOpen]);

  return [open, setOpen] as const;
}
