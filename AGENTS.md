# Agent guide

This repository holds OpenDefence core: a cloudcoil operator and a FastAPI REST API in one Python package (`src/opendefence_core`), the `platform.opendefence.fi/v1alpha1` CRDs, and the Zarf package `core` that deploys them on top of [opendefence/base](https://github.com/opendefence/base). Read [README.md](README.md) for the lifecycle commands, the API, and the integration contract. Tool versions are in `mise.toml`; Python dependencies are in `pyproject.toml` and `uv.lock`.

## Structure

- `src/lib_opendefence_core/models/v1alpha1/` defines the custom resources in the separate `lib-opendefence-core` package. The library must not import `opendefence_core`. The operator, the API, and the generated CRDs all use them.
- `naming.py` holds the names shared across components: namespaces, issuers, the operator name, and the user certificate and Secret names. YAML under `manifests/` and the `Tiltfile` repeat them because they can't import Python, so keep them in sync.
- `k8s_operator/` holds the Application (`app.py`), its controllers, and `render.py`, which generates `manifests/crds/crds.yaml` and `manifests/operator/operator.yaml`; `manifests/operator/kustomization.yaml` patches the latter.
- `api/` holds the FastAPI app: `routes/<area>/{views,schema}.py`, the shared `ApiModel` base in `schema.py`, the JWT dependency in `dependencies.py`, and helpers in `lib/`.
- `cli/console.py` is the only entrypoint: `api run`, `operator run`, and `operator render [--check]`.
- `Taskfile.yaml` orchestrates local development on base's kind cluster and registries. It includes base's taskfiles from `BASE_REF` (default `main`) and installs base `BASE_VERSION` (default `latest`).
- `taskfiles/core.yaml` installs a published core package or applies the CRDs. It must stay remote-safe: integration repositories include it by URL without a checkout, so it can't reference companion files.
- `taskfiles/build.yaml` works on the checkout: Zarf lint, inspect, deploy and package, the image build, and manifest rendering.
- `tests/` uses `fakes.py` (cloudcoil clients, caches, contexts, admission requests) and `factories.py` (resource builders). Reuse them; don't define per-file copies.

## Conventions

- Never edit the generated manifests by hand. After changing models, controllers, webhooks, or `RBACRule`s, run `task build:manifests`; `tests/test_render.py` and `task build:manifests:check` fail while the files are stale.
- Every CRD field needs a description (a test checks this). Refer to other platform objects by name with `ObjectRef` and resolve them with the `_refs.py` helpers. Condition types are constants in the models.
- The API speaks camelCase JSON through `ApiModel`. Routes live under `/api/v3` and get their configuration from `get_config()`, never from a module-level instance.
- The operator only gains permissions through `RBACRule` in `k8s_operator/app.py`; the API's RBAC is hand-written in `manifests/api/rbac.yaml`. Keep both least-privilege.
- The image is `ghcr.io/opendefence/core` and the Zarf package `core` is published under `oci://ghcr.io/opendefence/packages`. They share version tags, so they must stay in separate repositories.
- Deployments pass only `args`, keeping the image entrypoint `tini -- opendefence_core`.
- Bump the version with `uv run --locked bump-my-version bump <part>`. When pinning base, set `BASE_REF` and `BASE_VERSION` together. Keep their defaults in the include URLs and the `install-base` command: Task doesn't evaluate templated vars in include paths, and base's own empty `BASE_*` defaults shadow root-level vars.
- Follow base's Taskfile rules: scalar defaults go in each included file's top-level `vars:` using `default`; public tasks get descriptions and tool preconditions; shell arguments are quoted with `shellQuote`. A value derived from a var that includers may set, such as `CORE_PACKAGE` from `CORE_VERSION`, is computed in the task's `vars:`, because file-level vars are evaluated before include vars apply.

## Validation

```sh
task test
task lint
task build:manifests:check
task build:lint
task --list
task -t taskfiles/core.yaml --list
task -t taskfiles/build.yaml --list
```

Run the relevant checks after each edit, and all of them before finishing. `task lint` runs every pre-commit hook: ruff, pyrefly, bandit, detect-secrets, prettier, and actionlint. Lifecycle tasks (`up`, `env`, `dev`, `down`, `reset`, `build:deploy`, `core:install`) change local clusters and registries; run them only when asked.
