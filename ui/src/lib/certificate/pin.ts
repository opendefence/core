const PIN_LENGTH = 4;
const CEILING = 250;

function digit(): number {
  const byte = new Uint8Array(1);
  do {
    crypto.getRandomValues(byte);
  } while (byte[0] >= CEILING);
  return byte[0] % 10;
}

export function generatePin(): string {
  return Array.from({ length: PIN_LENGTH }, digit).join("");
}
