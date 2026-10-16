# core

OpenDefence core contains the platform operator and the shared model library.
The REST API is not included in this branch.

## Development

```sh
mise install
uv sync --locked
uv run --locked prek install
task test
task lint
task build:manifests:check
task build:lint
```

Run `task build:manifests` after you change models, controllers, or RBAC rules.
Do not edit the generated manifests by hand.

## Operator

The operator resolves User, Group, Role, and Invite references.
It rejects Group cycles and deletion of Groups that have children.
It reports UserBinding sync status on each User.
It rejects deletion of Users that have UserBindings.

An approved User gets a one-shot cert-manager `CertificateRequest`.
The operator creates the private key and stores the issued certificate in a Secret.
cert-manager cannot renew this request.
The operator does not replace expired certificates or missing private material.
The `publicKey` status field remains the SHA-256 fingerprint of the public key SPKI.

`approvedAt` records the original user approval and authorizes the first issuance.
Keep this timestamp unchanged during certificate replacement.
An administrator sets `certificateApprovedAt` to authorize another issuance.
The new timestamp must be later than the consumed approval.
Each approval authorizes one issuance.
Changing `approvedAt` after issuance does not authorize replacement.
Clearing or restoring an older `certificateApprovedAt` leaves the current certificate unchanged.
The operator records consumption before it creates private material.
If creation stops partway through, missing resources require fresh approval.
Removing approval or revoking the User clears accepted credentials before cleanup.
The operator then deletes the signing request and the key pair Secret.
It also deletes these resources when the User is deleted.
Legacy managed Certificates are removed to stop renewal.
Their replacement requires fresh approval.
This transition removes their key pair Secrets.

The certificate URI SAN is `urn:uuid:<canonical Kubernetes User UID>`.
The CN is `<deployment display name> · <identity tag>`.
The tag is the first eight lowercase hexadecimal digits of SHA-256 over the canonical UUID text.
Deployment label and duration changes apply to the next approved issuance.
Restoring a User under a new Kubernetes UID requires a new certificate.

The operator owns two User annotations:

- `platform.opendefence.fi/certificate-approval` records the consumed approval timestamp.
- `platform.opendefence.fi/accepted-credentials` contains `{"version":1,"accepted":[...]}`.

Each accepted record contains `fingerprintSha256`, `serial`, `issuerId`, `notBefore`, and `notAfter`.
The fingerprint is SHA-256 of the complete leaf certificate DER.
The serial is lowercase hexadecimal without separators.
The issuer ID is `sha256:` followed by SHA-256 of the signing CA's public key SPKI.
The validity timestamps use RFC 3339 with a UTC offset.
The operator verifies the leaf against the approved CSR, key, User UID, and signing CA before publication.
Integrations must check the accepted fingerprint and validity window.
Missing, empty, malformed, or unsupported records grant no access.
Integrations must remove access when the accepted record is removed.
Deleting a Secret alone does not revoke an exported certificate.
The current flow accepts one certificate per User.
Overlapping replacement and first-use retirement are not implemented.

The Integration controller creates the extra Roles listed in each Integration.
It deletes owned Roles that the Integration no longer lists.
Integration network policy is stored only. The operator does not enforce it.

Run `uv run --locked opendefence_core operator run` to start the operator.
The cluster must have cert-manager and the `public-issuer` and
`internal-root-issuer` ClusterIssuers.
Create the `opendefence-system` and `opendefence-public-certs` namespaces.
Apply `manifests/operator/certificate.yaml` for the webhook serving certificate.
Use `kubectl kustomize manifests/operator` to render the operator deployment.
The deployment uses image `ghcr.io/opendefence/core`.
The webhook serving certificate keeps automatic renewal.
The no-renewal policy applies to user identity certificates.

## Shared library

Import models from `lib_opendefence_core.models.v1alpha1`.
The library contains User, Group, Role, Invite, UserBinding, and Integration.
The library does not import the operator package.

```sh
uv build --package lib-opendefence-core --no-sources --out-dir dist
uv run --locked python scripts/check_packages.py dist
```

CI checks the library wheel and source archive before publication to Nexus.
Publication runs only from `main` after the checks pass.
Set the `NEXUSBOT_PAT` repository secret for publication.
Image and Zarf package publication are not included.

Run `task version:bump -- patch` to update both package versions and the lock.
Replace `patch` with the required version part.

## Dev branch port

This branch starts at `main` commit `af0375a`.
The model split, package checks, CI, version, and Integration changes come from
Eero af Heurlin and Santeri Sointu on `dev`, through `d6b096a`.
Their logging changes are applied separately with cherry-picks where possible.
Required operator code and manifest rendering come from the earlier `dev` commits.
The reference behavior is the
[legacy operator](https://github.com/pvarki/python-rasenmaeher-k8soperator).
Certificate handling and the Integration controller are also included.
API code, API dependencies, and the base and Zarf deployment lifecycle are excluded.
