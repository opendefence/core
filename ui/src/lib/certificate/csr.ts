import * as asn1js from "asn1js";
import * as pkijs from "pkijs";
import { toPem } from "./pem";

const COMMON_NAME = "2.5.4.3";
const EXTENSION_REQUEST = "1.2.840.113549.1.9.14";
const URI_NAME = 6;

export async function createCsr(
  keys: CryptoKeyPair,
  commonName: string,
  uri: string,
): Promise<string> {
  const request = new pkijs.CertificationRequest();
  request.version = 0;
  request.subject.typesAndValues.push(
    new pkijs.AttributeTypeAndValue({
      type: COMMON_NAME,
      value: new asn1js.Utf8String({ value: commonName }),
    }),
  );
  await request.subjectPublicKeyInfo.importKey(keys.publicKey);

  const names = new pkijs.GeneralNames({
    names: [new pkijs.GeneralName({ type: URI_NAME, value: uri })],
  });
  request.attributes = [
    new pkijs.Attribute({
      type: EXTENSION_REQUEST,
      values: [
        new pkijs.Extensions({
          extensions: [
            new pkijs.Extension({
              extnID: pkijs.id_SubjectAltName,
              critical: false,
              extnValue: names.toSchema().toBER(false),
            }),
          ],
        }).toSchema(),
      ],
    }),
  ];

  await request.sign(keys.privateKey, "SHA-256");
  return toPem("CERTIFICATE REQUEST", request.toSchema().toBER(false));
}
