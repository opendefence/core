// check_csr accepts nothing else.
const ALGORITHM: EcKeyGenParams = { name: "ECDSA", namedCurve: "P-256" };

/** A signing key for one request */
export function generateKeyPair(): Promise<CryptoKeyPair> {
  return crypto.subtle.generateKey(ALGORITHM, true, ["sign", "verify"]);
}

export function exportPrivateKey(key: CryptoKey): Promise<ArrayBuffer> {
  return crypto.subtle.exportKey("pkcs8", key);
}
