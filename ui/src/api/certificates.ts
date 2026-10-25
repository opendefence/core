import { useMutation } from "@tanstack/react-query";
import { api } from "./client";
import { createCsr } from "@/lib/certificate/csr";
import { exportPrivateKey, generateKeyPair } from "@/lib/certificate/keypair";
import { createPfx } from "@/lib/certificate/pfx";
import { generatePin } from "@/lib/certificate/pin";

const POLL_MS = 1000;
const ATTEMPTS = 60;

export type CertificateFailure =
  "notApproved" | "approvalUsed" | "notIssued" | "failed";

export class CertificateError extends Error {
  reason: CertificateFailure;

  constructor(reason: CertificateFailure) {
    super(reason);
    this.reason = reason;
    this.name = "CertificateError";
  }
}

interface Request {
  commonName: string;
  uri: string;
}

export interface Bundle {
  pin: string;
  pfx: ArrayBuffer;
}

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function submit(csr: string): Promise<void> {
  const { error, response } = await api.POST("/api/v3/certificates/csr", {
    body: { csr },
  });
  if (!error) return;
  if (response.status === 403) throw new CertificateError("notApproved");
  // The key only ever lived in this page, so a spent approval is not ours.
  if (response.status === 409) throw new CertificateError("approvalUsed");
  throw new CertificateError("failed");
}

async function awaitChain(): Promise<string> {
  for (let attempt = 0; attempt < ATTEMPTS; attempt++) {
    const { data, response } = await api.GET("/api/v3/certificates/chain.pem", {
      parseAs: "text",
    });
    if (response.status === 200 && typeof data === "string") return data;
    if (response.status !== 409) throw new CertificateError("failed");
    await wait(POLL_MS);
  }
  throw new CertificateError("notIssued");
}

/**
 * Request the certificate and bundle it with its key, ready to save.
 */
export function useCertificate() {
  return useMutation({
    mutationFn: async ({ commonName, uri }: Request): Promise<Bundle> => {
      const keys = await generateKeyPair();
      await submit(await createCsr(keys, commonName, uri));
      const chain = await awaitChain();

      const pin = generatePin();
      const pfx = await createPfx(
        await exportPrivateKey(keys.privateKey),
        chain,
        pin,
      );
      return { pin, pfx };
    },
  });
}
