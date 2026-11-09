import { clearStore, readStore, writeStore } from "@/lib/safeStorage";

// Carries the user through enrollment, until their certificate takes over.
const TOKEN_KEY = "token";
const CALLSIGN_KEY = "callsign";

// One browser may enroll more than once.
const certKey = (callsign: string) => `cert_downloaded:${callsign}`;

/** Whether this callsign saved its bundle, the last step. */
export function readCertDownloaded(callsign: string): boolean {
  return readStore(certKey(callsign)) === "true";
}

export function writeCertDownloaded(callsign: string): void {
  writeStore(certKey(callsign), "true");
}

export function readToken(): string | null {
  return readStore(TOKEN_KEY);
}

export function writeToken(token: string): void {
  writeStore(TOKEN_KEY, token);
}

/** Drop what an unfinishable enrollment left behind, so the next visit is clean. */
export function clearEnrollment(): void {
  const callsign = readStore(CALLSIGN_KEY);
  if (callsign) clearStore(certKey(callsign));
  clearStore(CALLSIGN_KEY);
  clearStore(TOKEN_KEY);
}
