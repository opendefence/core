import { Capacitor } from "@capacitor/core";
import { readStore, writeStore } from "./safeStorage";

/** True inside the Capacitor app */
export const isNative = Capacitor.isNativePlatform();

const DOMAIN_KEY = "native_domain";

export function readDomain(): string | null {
  return readStore(DOMAIN_KEY);
}

/** Reloads so the API client picks up the domain. */
export function joinDomain(domain: string, path: string): void {
  writeStore(DOMAIN_KEY, domain);
  window.location.replace(path);
}
