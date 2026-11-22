import * as pkijs from "pkijs";
import type { Signer } from "./csr";

// check_csr accepts nothing else.
const ALGORITHM: EcKeyGenParams = { name: "ECDSA", namedCurve: "P-256" };
const SIGNING: EcdsaParams = { name: "ECDSA", hash: "SHA-256" };

/** A signing key for one request */
export function generateKeyPair(): Promise<CryptoKeyPair> {
  return crypto.subtle.generateKey(ALGORITHM, true, ["sign", "verify"]);
}

export function exportPrivateKey(key: CryptoKey): Promise<ArrayBuffer> {
  return crypto.subtle.exportKey("pkcs8", key);
}

/** WebCrypto gives raw r||s, X.509 wants DER. */
export function webSigner(keys: CryptoKeyPair): Signer {
  return {
    spki: () => crypto.subtle.exportKey("spki", keys.publicKey),
    sign: async (data) =>
      pkijs.createCMSECDSASignature(
        await crypto.subtle.sign(SIGNING, keys.privateKey, data),
      ),
  };
}
