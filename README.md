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
curl --cacert public-root-ca.pem https://local-dev.opendefence.fi/api/health
```

```sh
task test
task lint
```

## Package

`zarf.yaml` defines the package. Components deploy in order:
`traefik-middlewares` (into Traefik's `traefik-system` namespace, referenced
as `traefik-system-<name>@kubernetescrd`), `api`, then `ingress`: the
`domain` certificate from base's `public-issuer`, Traefik's default
`TLSStore`, and the `IngressRoute` serving the API under `/api`. Resources are
raw YAML in `manifests/`; the middlewares and ingress use Go templates. Add a
`crds` component first once core defines CRDs.

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
