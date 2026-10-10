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
   base's taskfiles at the commit pinned in `BASE_REF`. It then installs base
   version `BASE_VERSION` in local CA mode, unless a `base` package is already
   deployed (for example by `task up` in a base checkout). Override with
   `BASE_VERSION=<tag>` or `BASE_ISSUER`; reinstall explicitly with
   `task base:install BASE_VERSION=<tag>`.
2. `dev:ci` builds core from this checkout and deploys it once (`tilt ci`).

Remote includes are a Task experiment, enabled in `.taskrc.yml`; Task asks you
to trust each remote file the first time. Bump `BASE_REF` and `BASE_VERSION`
in `Taskfile.yaml` together, to a base commit and the version published from it.

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

Users, Groups, Roles, and Invites are cluster-scoped; UserBindings are
namespaced. Objects reference each other by name (`roleRefs`, `groupRefs`,
`parentRef`, `managerRefs`), and the operator resolves the names to UIDs in
their status, reporting `ReferencesResolved`. A User is named after its
callsign: the API server rejects a `spec.callsign` that differs from
`metadata.name`.

The **operator** (`opendefence_core operator run`, Deployment `core-operator`)
reconciles them:

- An approved, unrevoked User gets a cert-manager Certificate `user-<callsign>`
  from base's `public-issuer` in `opendefence-public-certs`. Its public key
  fingerprint goes to `status.publicKey`, and `CertificateReady` reports
  progress. Revoking or unapproving deletes the Certificate and its key pair
  Secret, so re-approval issues a new key. A finalizer does the same when the
  User is deleted.
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
`CORE_API_DOMAIN` (required, from the `domain` value), `CORE_API_JWT_KEY_PATH`,
`CORE_API_JWT_LIFETIME`, and `CORE_API_JWT_ISSUER`.

### Integrations

An integration creates one `UserBinding` per User in its own namespace, naming
the User in `spec.userRef`, and sets the binding's `Synced` condition to
`True` once the User is provisioned. Core lists the bindings and their sync
state in the User's `status.bindings` and `BindingsSynced` condition, and
blocks deleting a User while bindings remain.

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
   Invite, UserBinding).
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
controllers, webhooks, or RBAC rules (a test fails while they are stale):

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
