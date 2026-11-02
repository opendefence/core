import { Capacitor } from "@capacitor/core";
import { readStore, writeStore } from "./safeStorage";

/** True inside the Capacitor app */
export const isNative = Capacitor.isNativePlatform();

const DOMAIN_KEY = "native_domain";

/** host[:port] of the joined deployment. */
export function readDomain(): string | null {
  return readStore(DOMAIN_KEY);
}

export function readPort(): string {
  const domain = readDomain();
  return domain ? new URL(`https://${domain}`).port : "";
}

// A phone reaches the dev cluster through `adb reverse tcp:8443 tcp:443`
const LOCAL_DEV = "local-dev.opendefence.fi";
const LOCAL_DEV_PORT = "8443";

export function deploymentHost(url: URL): string {
  return url.hostname === LOCAL_DEV && !url.port
    ? `${url.hostname}:${LOCAL_DEV_PORT}`
    : url.host;
}

/** Drops a typed scheme or path. */
export function typedHost(input: string): string {
  const bare = input
    .trim()
    .replace(/^[a-z][a-z0-9+.-]*:\/\//i, "")
    .replace(/\/.*$/, "");
  return deploymentHost(new URL(`https://${bare}`));
}

/** Reloads so the API client picks up the domain. */
export function joinDomain(domain: string, path: string): void {
  writeStore(DOMAIN_KEY, domain);
  window.location.replace(path);
}
