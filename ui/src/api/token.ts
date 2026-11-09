import { clearStore, readStore, writeStore } from "@/lib/safeStorage";

// Carries the user through enrollment, until their certificate takes over.
const TOKEN_KEY = "token";
const USER_ID_KEY = "userId";

// Keyed by uid, not callsign: a callsign repeats, a uid never does.
const certKey = (userId: string) => `cert_downloaded:${userId}`;

/** Whether this user saved their bundle, the last step. */
export function readCertDownloaded(userId: string): boolean {
  return readStore(certKey(userId)) === "true";
}

export function writeCertDownloaded(userId: string): void {
  writeStore(certKey(userId), "true");
}

export function readUserId(): string | null {
  return readStore(USER_ID_KEY);
}

export function writeUserId(userId: string): void {
  writeStore(USER_ID_KEY, userId);
}

export function readToken(): string | null {
  return readStore(TOKEN_KEY);
}

export function writeToken(token: string): void {
  writeStore(TOKEN_KEY, token);
}

/** Drop what an unfinishable enrollment left behind, so the next visit is clean. */
export function clearEnrollment(): void {
  const userId = readUserId();
  if (userId) clearStore(certKey(userId));
  clearStore(USER_ID_KEY);
  clearStore(TOKEN_KEY);
}
