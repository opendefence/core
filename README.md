# core

OpenDefence core: the operator, REST API, and Traefik middlewares of the
operational platform, packaged as a native Zarf package named `core`. It runs
on top of the operators from [opendefence/base](https://github.com/opendefence/base).

## Development usage

Have Docker or Podman available and ports 80 and 443 free, then:

```sh
mise install
uv sync
task up     # cluster and base if missing, then build and deploy core
task dev    # Tilt: keep core deployed and hot-reload the API from src/
task down   # delete the cluster, keep registry data
task reset  # also delete registry containers and cached images
```

`task up` is safe to rerun:

1. `env`: starts the registries and kind cluster if they are missing (base's
   taskfiles, included from base's `main` branch), and installs
   `oci://ghcr.io/opendefence/base:latest` in local CA mode unless a `base`
   package is already deployed, for example by `task up` in a base checkout.
   Override with `BASE_VERSION=<tag>` or `BASE_ISSUER`; reinstall explicitly
   with `task base:install BASE_VERSION=<tag>`.
2. `deploy`: builds core from this checkout and deploys it once (`tilt ci`).

Remote includes are a Task experiment, enabled in `.taskrc.yml`; Task asks
you to trust each remote file the first time.

`task dev` runs `tilt up`. Tilt renders the package with
`values/local-dev.yaml`, builds the `dev` Dockerfile target, pushes it to
base's local registry, and port-forwards the API to `localhost:8000`. Changes
under `src/` are synced into the running container and uvicorn reloads;
changes to `pyproject.toml` or `uv.lock` rebuild the image.

The API is also served through Traefik at
`https://local-dev.opendefence.fi/api/` (the name resolves to 127.0.0.1), with
interactive docs at `/api/docs`. The certificate comes from base's local CA;
trust it in your browser or OS once:

```sh
task base:export-ca > public-root-ca.pem
curl --cacert public-root-ca.pem https://local-dev.opendefence.fi/api/v3/health
```

```sh
task test
task lint
```

## Package

`zarf.yaml` defines the package. Components deploy in order:

1. `namespaces`: `opendefence-system` (Linkerd-injected) and
   `opendefence-public-certs` (user certificates).
2. `crds`: the `platform.opendefence.fi/v1alpha1` CRDs (User, Group, Role,
   Invite, UserBinding).
3. `traefik-middlewares`: shared middlewares in Traefik's `traefik-system`
   namespace, referenced as `traefik-system-<name>@kubernetescrd`.
4. `operator`: the operator (`opendefence_core operator run`), its RBAC, and
   its admission webhook. The webhook's serving certificate comes from base's
   `internal-root-issuer`; cert-manager injects its CA. With
   `failurePolicy: Fail`, Group writes and User deletes are rejected while the
   operator is down. User certificates are issued from base's `public-issuer`.
5. `api`: the REST API (`uvicorn opendefence_core.api.app:app`), its RBAC, and
   its ES256 JWT signing key (a cert-manager-generated key pair).
6. `ingress`: the `domain` certificate from `public-issuer`, Traefik's default
   `TLSStore`, and the `IngressRoute` serving `/api`.

Resources are raw YAML in `manifests/`; the middlewares, API, and ingress use
Go templates. `manifests/crds/crds.yaml` and `manifests/operator/operator.yaml`
are generated from the operator code; regenerate them after changing models,
controllers, or webhooks (a test fails while they are stale):

```sh
task operator:manifests
```

The API reads `CORE_API_*` environment variables: `CORE_API_DOMAIN` (set from
the `domain` value), `CORE_API_JWT_KEY_PATH`, `CORE_API_JWT_LIFETIME`, and
`CORE_API_JWT_ISSUER`. Its liveness and readiness probe is `/api/v3/health`.

Deployment configuration is Zarf package values. `values/values.yaml` holds
the production defaults baked into the package and
`values/values.schema.json` validates them. `values/local-dev.yaml` is the
development variant, used by Tilt and `zarf:deploy`:

| Value         | Default                    | local-dev | Effect                                      |
| ------------- | -------------------------- | --------- | ------------------------------------------- |
| `domain`      | `local-dev.opendefence.fi` | (default) | Public hostname, its certificate and route  |
| `hsts.maxAge` | `31536000`                 | `0`       | HSTS max-age; `0` clears it in your browser |

```sh
task zarf:lint
task zarf:inspect                     # render with VALUES_FILE (default local-dev)
task zarf:deploy                      # zarf dev deploy --connected, no Tilt
task zarf:package ARCH=amd64 BUILD_DIR=.build
```

The package targets connected deployment and has no offline image inventory
yet.

## Container image

The `Dockerfile` builds a distroless image with a standalone Python 3.14.
`production` is the default target (`task image:build`); `dev` adds busybox
for Tilt's live updates and runs the synced source from `/app/src`.

## Versioning

`uv run --locked bump-my-version bump patch` updates the package version and
the image tag in `manifests/api/deployment.yaml`. Container tags can't contain
`+`, so version `0.1.1+261010` is image tag `0.1.1-261010`.
