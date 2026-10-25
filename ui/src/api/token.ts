import { readStore, writeStore } from "@/lib/safeStorage";

// Carries the user through enrollment, until their certificate takes over.
const TOKEN_KEY = "token";

export function readToken(): string | null {
  return readStore(TOKEN_KEY);
}

export function writeToken(token: string): void {
  writeStore(TOKEN_KEY, token);
}
