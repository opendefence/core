import * as asn1js from "asn1js";
import * as pkijs from "pkijs";
import { toPem } from "./pem";

const COMMON_NAME = "2.5.4.3";
const EXTENSION_REQUEST = "1.2.840.113549.1.9.14";
const ECDSA_WITH_SHA256 = "1.2.840.10045.4.3.2";
const URI_NAME = 6;

export interface Signer {
  /** DER SubjectPublicKeyInfo */
  spki(): Promise<ArrayBuffer>;
  /** DER Ecdsa-Sig-Value */
  sign(data: ArrayBuffer): Promise<ArrayBuffer>;
}

// pkijs keeps encodeTBS protected
class Request extends pkijs.CertificationRequest {
  encodeInfo(): ArrayBuffer {
    return this.encodeTBS().toBER(false);
  }
}

export async function createCsr(
  signer: Signer,
  commonName: string,
  uri: string,
): Promise<string> {
  const request = new Request();
  request.version = 0;
  request.subject.typesAndValues.push(
    new pkijs.AttributeTypeAndValue({
      type: COMMON_NAME,
      value: new asn1js.Utf8String({ value: commonName }),
    }),
  );
  request.subjectPublicKeyInfo = pkijs.PublicKeyInfo.fromBER(
    await signer.spki(),
  );

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

  request.signatureAlgorithm = new pkijs.AlgorithmIdentifier({
    algorithmId: ECDSA_WITH_SHA256,
  });
  request.tbs = request.encodeInfo();
  request.signatureValue = new asn1js.BitString({
    valueHex: await signer.sign(request.tbs),
  });
  return toPem("CERTIFICATE REQUEST", request.toSchema().toBER(false));
}
