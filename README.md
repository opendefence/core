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

An approved User gets a cert-manager Certificate.
The operator deletes the Certificate and key pair Secret when approval is removed,
when the User is revoked, or when the User is deleted.
The `publicKey` status field contains the public key fingerprint.

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
