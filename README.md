# core

OpenDefence core: the operator, REST API, CRDs, and Traefik middlewares of the
operational platform. It runs on top of the operators from
[opendefence/base](https://github.com/opendefence/base) and produces:

- the Zarf package `oci://ghcr.io/opendefence/packages/core:<version>`;
- the container image `ghcr.io/opendefence/core:<version>`, which runs both
  the operator and the API;
- the `platform.opendefence.fi/v1alpha1` CRDs in `manifests/crds/crds.yaml`;
- `taskfiles/core.yaml`, which integration repositories include to install core
  or its CRDs.

## Development usage

Have Docker or Podman available and ports 80 and 443 free, then:

```sh
mise install
uv sync
task up       # cluster and base if missing, then build and deploy core once
task dev      # Tilt: keep core deployed and hot-reload the API from src/
task down     # delete the cluster, keep registry data
task reset    # also delete registry containers and cached images
task test
task lint
```

`task up` is safe to rerun:

1. `env` starts the registries and kind cluster if they are missing, using
   base's taskfiles from its `main` branch. It then installs
   `oci://ghcr.io/opendefence/base:latest` in local CA mode, unless a `base`
   package is already deployed (for example by `task up` in a base checkout).
   Override with `BASE_VERSION=<tag>` or `BASE_ISSUER`; reinstall explicitly
   with `task base:install BASE_VERSION=<tag>`.
2. `dev:ci` builds core from this checkout and deploys it once (`tilt ci`).

Remote includes are a Task experiment, enabled in `.taskrc.yml`; Task asks you
to trust each remote file the first time. To pin base, pass `BASE_REF=<commit>`
together with a `BASE_VERSION` published from that commit.

`task dev` runs `tilt up`. Tilt renders the package with
`values/local-dev.yaml`, builds the `dev` Dockerfile target, pushes it to
base's local registry, and port-forwards the API to `localhost:8000`. Changes
under `src/` are synced into the API container, which reloads; the operator is
rebuilt and restarted. Changes to `pyproject.toml` or `uv.lock` rebuild both.

The API is also served through Traefik at
`https://local-dev.opendefence.fi/api/` (the name resolves to 127.0.0.1), with
interactive docs at `/api/docs`. The certificate comes from base's local CA;
trust it in your browser or OS once:

```sh
task base:export-ca > public-root-ca.pem
curl --cacert public-root-ca.pem https://local-dev.opendefence.fi/api/v3/health
```

Try the platform objects with the examples:

```sh
kubectl apply -f examples/demo.yaml -f examples/invites/
kubectl patch user <callsign> --type merge --patch-file examples/users/approve.yaml
```

## How it works

Users, Groups, Roles, Invites, and Integrations are cluster-scoped; UserBindings are
namespaced. Objects reference each other by name (`roleRefs`, `groupRefs`,
`parentRef`, `managerRefs`), and the operator resolves the names to UIDs in
their status, reporting `ReferencesResolved`. Enrollment uses the initial
callsign as the resource name. Later callsign changes preserve the resource
name, UID, certificate, and bindings.

The **operator** (`opendefence_core operator run`, Deployment `core-operator`)
reconciles them:

- An approved, unrevoked User gets a one-shot cert-manager `CertificateRequest`
  named `user-<resource-name>` in `opendefence-public-certs`.
  It uses base's `public-issuer`. The operator stores the key pair in a Secret.
  `CertificateReady` reports progress. `status.publicKey` contains the SHA-256
  fingerprint of the public key SPKI. See the certificate contract below.
- The admission webhook rejects Group cycles, missing parent groups, deleting
  a group that still has children, and deleting a User that still has
  UserBindings. With `failurePolicy: Fail`, those writes are rejected while
  the operator is down.

The **REST API** (`opendefence_core api run`, Deployment `core-api`) serves
under `/api/v3`:

| Endpoint                           | Purpose                                                                  |
| ---------------------------------- | ------------------------------------------------------------------------ |
| `GET /health`                      | Liveness and readiness probe                                             |
| `POST /enrollment/check`           | Whether an invite code can be redeemed                                   |
| `POST /enrollment`                 | Redeem an invite code into a pending User; returns its status and a JWT  |
| `GET /enrollment`                  | The caller's enrollment status and approval code (JWT)                   |
| `GET /certificates/{callsign}.pfx` | The caller's certificate and key as PKCS#12, password the callsign (JWT) |

JWTs are ES256, signed with a cert-manager-generated key that the API reloads
when cert-manager rotates it. The API reads `CORE_API_*` environment variables:
`CORE_API_JWT_KEY_PATH`, `CORE_API_JWT_LIFETIME`, and `CORE_API_JWT_ISSUER`.

The API and the operator read the `core-config` ConfigMap as environment variables.
`CORE_DOMAIN` is the `domain` value. `CORE_DEPLOYMENT` is the first DNS label
of `domain`, for example `local-dev`. Both are required.
`CORE_DEPLOYMENT` must have at most 55 characters.

### User certificates

cert-manager does not renew user identity certificates.
The operator does not replace expired certificates or missing private material.

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
The CN is `<CORE_DEPLOYMENT>#<identity tag>`, for example `local-dev#1a2b3c4d`.
The CN is a label for people. Integrations must not use it for identity.
The tag is the first eight lowercase hexadecimal digits of SHA-256 over the canonical UUID text.
Callsign changes preserve the User UID and certificate.
Deployment name and duration changes apply to the next approved issuance.
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

The webhook serving certificate keeps automatic renewal.
The no-renewal policy applies to user identity certificates.

### Certificate settings

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

### Integrations

An `Integration` records an installed product: its version, UI product info, extra
roles, and the ingress and egress it intends. The operator creates each extra
role as a cluster `Role` owned by the Integration, and deletes that Role when
the Integration drops it. The network policy is stored only; core does not
enforce it yet.

An integration creates one `UserBinding` per User in its own namespace, naming
the User in `spec.userRef`, and sets the binding's `Synced` condition to
`True` once the User is provisioned. The condition must include the current
binding generation in `observedGeneration`. Core lists the bindings and their sync
state in the User's `status.bindings` and `BindingsSynced` condition, and
blocks deleting a User while bindings remain.

Integration workloads must not use User or UserBinding identities.
The current Integration controller manages extra Roles only.
It does not issue workload credentials.

Integration repositories include `taskfiles/core.yaml` remotely, pinned to a
core commit, and enable the `REMOTE_TASKFILES` experiment like this repository
does in `.taskrc.yml`. Write include vars with a `default` so that the command
line can still override them:

```yaml
version: "3"
includes:
  core:
    taskfile: https://raw.githubusercontent.com/opendefence/core/<commit>/taskfiles/core.yaml
    vars:
      CORE_VERSION: '{{.CORE_VERSION | default "<published-version>"}}'
      CORE_REF: <commit>
      # Local development: the kind cluster's hostname, without HSTS
      CORE_SET_VALUES: domain=local-dev.opendefence.fi,hsts.maxAge=0
```

| Task           | Effect                                                                                   |
| -------------- | ---------------------------------------------------------------------------------------- |
| `core:install` | Deploy `CORE_PACKAGE` (default `oci://ghcr.io/opendefence/packages/core:<CORE_VERSION>`) |
| `core:remove`  | Remove the core package                                                                  |
| `core:status`  | Show core's Deployments and the platform objects                                         |
| `core:crds`    | Apply only the CRDs from `CORE_REF`, to work with the platform kinds without core        |

`CORE_VALUES_FILE` and `CORE_SET_VALUES` pass deployment values. Like base,
Zarf deploys to the current kube-context, which must equal `KUBE_CONTEXT`
(default `kind-<CLUSTER_NAME>`).

## Package

`zarf.yaml` defines the package. Components deploy in order:

1. `namespaces`: `opendefence-system` (Linkerd-injected) and
   `opendefence-public-certs` (user certificates).
2. `crds`: the `platform.opendefence.fi/v1alpha1` CRDs (User, Group, Role,
   Invite, UserBinding, Integration).
3. `traefik-middlewares`: shared middlewares in Traefik's `traefik-system`
   namespace, referenced as `traefik-system-<name>@kubernetescrd`.
4. `operator`: the operator, its RBAC, and its admission webhook. The webhook's
   serving certificate comes from base's `internal-root-issuer`; cert-manager
   injects its CA.
5. `api`: the REST API, its RBAC, and its JWT signing key.
6. `ingress`: the `domain` certificate from `public-issuer`, Traefik's default
   `TLSStore`, and the `IngressRoute` serving `/api`.

Resources are raw YAML in `manifests/`; the middlewares, API, and ingress use
Go templates. `manifests/crds/crds.yaml` and `manifests/operator/operator.yaml`
are generated from the operator code; regenerate them after changing models,
controllers, webhooks, or RBAC rules (a test fails while they are stale).
The hand-written patches in `manifests/operator/kustomization.yaml` harden the
generated operator Deployment and webhook configuration:

```sh
task build:manifests
```

Deployment configuration is Zarf package values. `values/values.yaml` holds the
defaults baked into the package, `values/values.schema.json` validates them,
and `values/local-dev.yaml` is the development variant used by Tilt and the
build tasks:

| Value         | Default               | local-dev                  | Effect                                      |
| ------------- | --------------------- | -------------------------- | ------------------------------------------- |
| `domain`      | `opendefence.invalid` | `local-dev.opendefence.fi` | Public hostname, its certificate and route  |
| `hsts.maxAge` | `31536000`            | `0`                        | HSTS max-age; `0` clears it in your browser |

The default `domain` is a placeholder that every deployment must override:
its certificate can't be issued, so a deployment that forgets it fails the
`core-tls` health check instead of serving the wrong name.

Set `domain` once per deployment and do not change it.
Its first DNS label becomes `CORE_DEPLOYMENT` and part of every user certificate CN.
The schema limits that label to 55 characters.

```sh
task build:lint
task build:inspect                    # render with VALUES_FILE (default local-dev)
task build:deploy                     # zarf dev deploy --connected, no Tilt
task build:package ARCH=amd64 BUILD_DIR=.build
```

The package targets connected deployment and has no offline image inventory
yet. `build:deploy` deploys the image tag pinned in the manifests, so it needs
that version to be published; use Tilt for unpublished code.

## Container image

The `Dockerfile` builds a distroless image with a standalone Python.
`production` is the default target (`task build:image`); `dev` adds busybox for
Tilt's live updates and runs the synced source from `/app/src`. The entrypoint
is `tini -- opendefence_core`, and the Deployments pass `api run` or
`operator run` as arguments.

## Publishing and versioning

A successful `main` release publishes `lib-opendefence-core` to Nexus, the
image `ghcr.io/opendefence/core:<tag>`, and the Zarf package
`oci://ghcr.io/opendefence/packages/core:<tag>`. The workflow then creates
the Git tag. The application is delivered in the image; CI does not publish
an application wheel. The OCI tag uses `-` in place of `+`: version `0.2.1+261010`
uses tag `0.2.1-261010`.

Run `task version:bump` to update both package versions, the exact library
dependency, the image tags, and `uv.lock`. The application version comes from
installed package metadata. The library version is in its `__init__.py` file.
Set `NEXUSBOT_PAT` in the `opendefence/core` repository before a release.

Import resource models from `lib_opendefence_core.models.v1alpha1`. The old
`opendefence_core.models` path is no longer available.

## GitHub Actions

Do not edit `.github/workflows/actions.lock` by hand. When a workflow adds or
removes a `uses` dependency, update the lock:

```sh
gh actions-lock
```

## Checks

```sh
task test
task lint
task build:manifests:check
task build:lint
task --list
task -t taskfiles/core.yaml --list
task -t taskfiles/build.yaml --list
```
