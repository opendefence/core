import * as asn1js from "asn1js";
import * as pkijs from "pkijs";
import { certificatesFromPem } from "./pem";

const SHROUDED_KEY_BAG = "1.2.840.113549.1.12.10.1.2";
const CERT_BAG = "1.2.840.113549.1.12.10.1.3";
const FRIENDLY_NAME = "1.2.840.113549.1.9.20";
const LOCAL_KEY_ID = "1.2.840.113549.1.9.21";
const COMMON_NAME = "2.5.4.3";
const HASH = "SHA-256";
const KEY_ID_HASH = "SHA-1";

const ITERATIONS = 2048;

const CIPHER = {
  name: "AES-CBC",
  length: 256,
} as pkijs.ContentEncryptionAlgorithm;

function commonName(certificate: pkijs.Certificate): string {
  const attribute = certificate.subject.typesAndValues.find(
    (entry) => entry.type === COMMON_NAME,
  );
  return attribute?.value.valueBlock.value ?? "";
}

async function bagAttributes(
  leaf: pkijs.Certificate,
): Promise<pkijs.Attribute[]> {
  const spki = leaf.subjectPublicKeyInfo.toSchema().toBER(false);
  const keyId = await crypto.subtle.digest(KEY_ID_HASH, spki);
  return [
    new pkijs.Attribute({
      type: LOCAL_KEY_ID,
      values: [new asn1js.OctetString({ valueHex: keyId })],
    }),
    new pkijs.Attribute({
      type: FRIENDLY_NAME,
      values: [new asn1js.BmpString({ value: commonName(leaf) })],
    }),
  ];
}

/** PKCS#12 holding the key and its issued chain, locked with the PIN. */
export async function createPfx(
  pkcs8: ArrayBuffer,
  chainPem: string,
  pin: string,
): Promise<ArrayBuffer> {
  const password = new TextEncoder().encode(pin).buffer as ArrayBuffer;
  const encryption = {
    password,
    contentEncryptionAlgorithm: CIPHER,
    hmacHashAlgorithm: HASH,
    iterationCount: ITERATIONS,
  };

  const chain = certificatesFromPem(chainPem).map((der) =>
    pkijs.Certificate.fromBER(der),
  );
  const attributes = await bagAttributes(chain[0]);

  const keyBag = new pkijs.PKCS8ShroudedKeyBag({
    parsedValue: pkijs.PrivateKeyInfo.fromBER(pkcs8),
  });
  await keyBag.makeInternalValues(encryption);

  const certBags = chain.map((certificate, index) => {
    const bag = new pkijs.SafeBag({
      bagId: CERT_BAG,
      bagValue: new pkijs.CertBag({ parsedValue: certificate }),
    });

    if (index === 0) bag.bagAttributes = attributes;
    return bag;
  });

  const authenticatedSafe = new pkijs.AuthenticatedSafe({
    parsedValue: {
      safeContents: [
        {
          privacyMode: 0,
          value: new pkijs.SafeContents({
            safeBags: [
              new pkijs.SafeBag({
                bagId: SHROUDED_KEY_BAG,
                bagValue: keyBag,
                bagAttributes: attributes,
              }),
            ],
          }),
        },
        {
          privacyMode: 0,
          value: new pkijs.SafeContents({ safeBags: certBags }),
        },
      ],
    },
  });
  await authenticatedSafe.makeInternalValues({ safeContents: [{}, {}] });

  const pfx = new pkijs.PFX({
    parsedValue: { integrityMode: 0, authenticatedSafe },
  });
  await pfx.makeInternalValues({
    password,
    iterations: ITERATIONS,
    pbkdf2HashAlgorithm: { name: HASH },
    hmacHashAlgorithm: HASH,
  });

  return pfx.toSchema().toBER(false);
}
