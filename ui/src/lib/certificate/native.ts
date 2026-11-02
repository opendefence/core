import { registerPlugin } from "@capacitor/core";
import type { Signer } from "./csr";
import { decode, encode } from "./pem";

export interface ClientCertificateStatus {
  hasKey: boolean;
  hasChain: boolean;
  /** Epoch milliseconds */
  notAfter?: number;
  subject?: string;
}

/** ClientCertificatePlugin.java */
interface ClientCertificatePlugin {
  generateKey(): Promise<{ spki: string; hardware: boolean }>;
  sign(options: { data: string }): Promise<{ signature: string }>;
  storeChain(options: { chainPem: string }): Promise<ClientCertificateStatus>;
  status(): Promise<ClientCertificateStatus>;
  remove(): Promise<void>;
  setDomain(options: { domain: string }): Promise<void>;
}

export const ClientCertificate =
  registerPlugin<ClientCertificatePlugin>("ClientCertificate");

/** Replaces any earlier key. */
export async function keystoreSigner(): Promise<Signer> {
  const { spki } = await ClientCertificate.generateKey();
  return {
    spki: async () => decode(spki),
    sign: async (data) =>
      decode((await ClientCertificate.sign({ data: encode(data) })).signature),
  };
}
