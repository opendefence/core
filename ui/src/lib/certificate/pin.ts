import { clearSession, readSession, writeSession } from "@/lib/safeStorage";

const PIN_LENGTH = 4;
const CEILING = 250;

function digit(): number {
  const byte = new Uint8Array(1);
  do {
    crypto.getRandomValues(byte);
  } while (byte[0] >= CEILING);
  return byte[0] % 10;
}

function generatePin(): string {
  return Array.from({ length: PIN_LENGTH }, digit).join("");
}

const key = (userId: string) => `cert_pin:${userId}`;

export function savedPin(userId: string): string {
  const saved = readSession(key(userId));
  if (saved) return saved;
  const pin = generatePin();
  writeSession(key(userId), pin);
  return pin;
}

export function readPin(userId: string): string {
  return readSession(key(userId)) ?? "";
}

/** Drop the pin once it has done its job at the install dialog. */
export function clearPin(userId: string): void {
  clearSession(key(userId));
}
