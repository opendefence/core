# User certificates

![CSR flow](csr_flow_visualization.drawio.svg)

Each approved User gets one client certificate.
The user's browser generates the key pair.
The server never generates, stores, or sends a private key.

## Enrollment flow

1. The user redeems an invite with `POST /api/v3/enrollment`. The response contains a JWT.
2. An administrator checks the approval code and sets `approvedAt`.
3. The browser reads `GET /api/v3/enrollment`. After approval, the response contains `name`, `certificateCommonName`, and `certificateUri`.
4. The browser generates an ECDSA P-256 key pair. It builds a CSR for that CN and URI SAN.
5. The browser sends the CSR with `POST /api/v3/certificates/csr`. The API checks the CSR and stores it in the User field `spec.certificateSigningRequest`.
6. The operator checks the CSR again and consumes the approval. It creates a one-shot cert-manager `CertificateRequest` named `user-<resource-name>` in `opendefence-public-certs`.
7. cert-manager signs the request with base's `public-issuer`. The operator verifies the certificate and publishes the accepted credential.
8. The browser polls `GET /api/v3/certificates/chain.pem` until it receives the chain.
9. The browser builds `<name>_<CORE_DEPLOYMENT>.pfx` from the private key and the chain.

The private key exists only in the page memory until the browser saves the `.pfx`.
Keep the page open until the download completes.
If the key is lost after the approval is consumed, the user needs a fresh `certificateApprovedAt`.

## Certificate API

All routes need the enrollment JWT. They act on the user that the token names.

| Route                                | Result                                                                                                                                                                               |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `POST /api/v3/certificates/csr`      | `202`: the CSR is stored. `400`: the CSR does not match the rules below. `403`: the user is not approved. `409`: the approval is already used, or the User changed during the write. |
| `GET /api/v3/certificates/chain.pem` | `200`: `application/x-pem-file`, the leaf certificate and then the CA. `409`: the certificate is not ready.                                                                          |

Both routes return `401` without a valid token.
Retry the CSR after a `409` that reports a changed User.

The request body is `{"csr": "<PEM>"}`. The API and the operator accept the CSR only if all of these are true:

- It is a PEM PKCS#10 request of at most 8192 characters.
- Its key is ECDSA P-256.
- Its self-signature is valid.
- Its subject is exactly `CN=<certificateCommonName>`.
- Its only extension is a subjectAltName with one URI, `<certificateUri>`.

## The .pfx file

The browser builds the PKCS#12 file with the private key, the certificate chain, and a PIN.
The browser generates a random 4-digit PIN with `crypto.getRandomValues` and shows it to the user.
Apple devices do not import a `.pfx` without a password. The PIN exists for this reason.
A 4-digit PIN does not protect a copied file. Delete the `.pfx` after import.
Use the PKCS#12 encryption that the target devices import.
The file name uses the User resource name, not the callsign.

Generate the key as extractable, so the browser can export it into the `.pfx`:

```js
const keys = await crypto.subtle.generateKey(
  { name: "ECDSA", namedCurve: "P-256" },
  true,
  ["sign", "verify"],
);
const pkcs8 = await crypto.subtle.exportKey("pkcs8", keys.privateKey);
```

Build the CSR with `@peculiar/x509` and the PKCS#12 file with PKI.js.

## Status

The `CertificateReady` condition on the User reports progress:

| Reason                       | Meaning                                                                         |
| ---------------------------- | ------------------------------------------------------------------------------- |
| `PendingApproval`            | The User is not approved.                                                       |
| `Revoked`                    | The User is revoked.                                                            |
| `AwaitingRequest`            | The approval is fresh. The operator waits for a CSR.                            |
| `InvalidRequest`             | The stored CSR does not match the rules. The message tells why. Send a new CSR. |
| `Issuing`                    | cert-manager has not signed the request yet.                                    |
| `Issued`                     | The certificate is verified and accepted.                                       |
| `InvalidCertificate`         | The signed certificate failed verification.                                     |
| `CertificateOutsideValidity` | The certificate is expired or not yet valid.                                    |
| `FreshApprovalRequired`      | The approval is consumed and the CertificateRequest is missing.                 |

`status.publicKey` contains the SHA-256 fingerprint of the public key SPKI.

## Approval and replacement

cert-manager does not renew user identity certificates.
The operator does not replace expired certificates or lost keys.

`approvedAt` records the original user approval and authorizes the first issuance.
Keep this timestamp unchanged during certificate replacement.
An administrator sets `certificateApprovedAt` to authorize another issuance.
The new timestamp must be later than the consumed approval.
Each approval authorizes one CSR and one issuance.
Changing `approvedAt` after issuance does not authorize replacement.
Clearing or restoring an older `certificateApprovedAt` leaves the current certificate unchanged.

The operator consumes the approval and clears the CSR in one patch. It then creates the CertificateRequest.
The API refuses a CSR after the approval is consumed. The operator clears such a CSR.
If creation stops partway through, the user needs a fresh approval.
A fresh `certificateApprovedAt` withdraws the current certificate at once.
The user needs a valid enrollment JWT to send a new CSR.

Removing approval or revoking the User clears accepted credentials and any pending CSR.
The operator then deletes the CertificateRequest.
The CertificateRequest has an owner reference to the User. Kubernetes deletes it with the User.

## Identity

The certificate URI SAN is `urn:uuid:<canonical Kubernetes User UID>`.
The CN is `<CORE_DEPLOYMENT>#<identity tag>`, for example `local-dev#1a2b3c4d`.
The CN is a label for people. Integrations must not use it for identity.
The tag is the first eight lowercase hexadecimal digits of SHA-256 over the canonical UUID text.
Callsign changes preserve the User UID and certificate.
Deployment name and duration changes apply to the next approved issuance.
Restoring a User under a new Kubernetes UID requires a new certificate.

## Accepted credentials

The operator owns two User annotations:

- `platform.opendefence.fi/certificate-approval` records the consumed approval timestamp.
- `platform.opendefence.fi/accepted-credentials` contains `{"version":1,"accepted":[...]}`.

Each accepted record contains `fingerprintSha256`, `serial`, `issuerId`, `notBefore`, and `notAfter`.
The fingerprint is SHA-256 of the complete leaf certificate DER.
The serial is lowercase hexadecimal without separators.
The issuer ID is `sha256:` followed by SHA-256 of the signing CA's public key SPKI.
The validity timestamps use RFC 3339 with a UTC offset.
The operator verifies the leaf against the approved CSR, the User UID, and the signing CA before publication.
Integrations must check the accepted fingerprint and validity window.
Missing, empty, malformed, or unsupported records grant no access.
Integrations must remove access when the accepted record is removed.
Deleting the CertificateRequest does not revoke an exported certificate.
The current flow accepts one certificate per User.
Overlapping replacement and first-use retirement are not implemented.

The webhook serving certificate keeps automatic renewal.
The no-renewal policy applies to user identity certificates.

## Certificate settings

`manifests/operator/kustomization.yaml` generates the operator configuration.
The default user certificate duration is `2880h` (120 days, or four 30-day months).
Use a positive whole number of hours.
The issuer must honor the requested duration.
The CN takes the deployment name from `CORE_DEPLOYMENT`, not from this configuration.

Override the default in a Kustomize overlay:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ../../manifests/operator
configMapGenerator:
  - name: core-operator-config
    namespace: opendefence-system
    behavior: merge
    literals:
      - USER_CERTIFICATE_DURATION=2880h
```

Kustomize updates the Deployment's ConfigMap reference when this value changes.
The cert-manager request approver must approve requests for `public-issuer`.
User approval remains the Core issuance gate.
