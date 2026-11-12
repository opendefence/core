const LINE_LENGTH = 64;

const CERTIFICATE_BLOCK =
  /-----BEGIN CERTIFICATE-----[\s\S]+?-----END CERTIFICATE-----/g;

function encode(der: ArrayBuffer): string {
  const bytes = new Uint8Array(der);
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}

function decode(base64: string): ArrayBuffer {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes.buffer;
}

export function toPem(label: string, der: ArrayBuffer): string {
  const body = encode(der).match(new RegExp(`.{1,${LINE_LENGTH}}`, "g")) ?? [];
  return `-----BEGIN ${label}-----\n${body.join("\n")}\n-----END ${label}-----\n`;
}

/** Every certificate in a chain, leaf first, as the API returns them. */
export function certificatesFromPem(pem: string): ArrayBuffer[] {
  const blocks = pem.match(CERTIFICATE_BLOCK) ?? [];
  return blocks.map((block) =>
    decode(block.replace(/-----[A-Z ]+-----/g, "").replace(/\s+/g, "")),
  );
}
