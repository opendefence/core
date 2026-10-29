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

const key = (callsign: string) => `cert_pin:${callsign}`;

export function savedPin(callsign: string): string {
  const saved = readSession(key(callsign));
  if (saved) return saved;
  const pin = generatePin();
  writeSession(key(callsign), pin);
  return pin;
}

/** Drop the pin once it has done its job at the install dialog. */
export function clearPin(callsign: string): void {
  clearSession(key(callsign));
}
