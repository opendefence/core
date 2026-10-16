# Architecture reconciliation

Review date: 2026-10-16.
Reference: `opendefence-full-architecture-handoff.md`, dated 2026-10-16.
The reference file is a local design input. It is not part of this commit.

The branch starts from `dev` and rebases onto `dev_no_api` at `ab9c5da`.
It includes the API and deployment lifecycle from `dev`.
It preserves the model and operator fixes from `dev_no_api`.
The complete handoff is not implemented.

## Implemented contracts

| Contract                                                              | Implementation and checks                                                                                                                                                                             |
| --------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Shared models stay independent of the application.                    | `src/lib_opendefence_core/models/v1alpha1/`; package checks in `scripts/check_packages.py`.                                                                                                           |
| Callsign changes preserve identity.                                   | User callsigns are mutable. Certificates use the User UID in a URI SAN. `tests/test_certificates.py` checks rename behavior. The download route uses the current callsign and the stable Secret name. |
| Original approval time stays separate from replacement approval.      | `approvedAt` records enrollment. `certificateApprovedAt` authorizes replacement. Tests reject timestamp replay and changes to the original approval time as replacement authority.                    |
| User certificates do not renew automatically.                         | One-shot CertificateRequests consume approval before resource creation. Missing material and expired certificates require fresh approval.                                                             |
| Certificate lifetime comes from Kustomize.                            | The default is `2880h`, or 120 days. Zarf renders the operator Kustomization. `tests/test_render.py` checks the package path and configuration override.                                              |
| Public credential metadata identifies exact certificates.             | The User annotation publishes the leaf DER SHA-256, serial, issuing key identity, and validity window. Tests check the CSR, key, owner UID, and issuer.                                               |
| Revocation cleanup does not depend on valid Role or Group references. | User reconciliation clears accepted credentials before reference resolution. A regression test covers a missing Role.                                                                                 |
| Group hierarchy has one parent.                                       | The Group model has one `parentRef`. Admission checks the parent chain. Tests cover cycles and missing parents.                                                                                       |
| Stale binding conditions do not establish readiness.                  | `is_synced` requires the current binding generation. Tests reject stale and missing generations. This does not establish credential revision readiness.                                               |
| Integration workloads remain separate from Users.                     | Integration is a separate resource. Its controller manages extra Roles. Role removal uses a UID precondition. No workload is represented as a User or UserBinding.                                    |

The current credential record uses `serial`. The handoff proposes `serialHex` but leaves the schema open.
The issuer identifier is `sha256:` followed by the SHA-256 of the issuing CA public key SPKI.
The CN identity tag uses the first eight hexadecimal characters of SHA-256 over the canonical User UUID.
These formats are implementation choices. Consumers must use the documented formats.

## Remaining gaps

These gaps existed before the rebase. A passing unit suite does not prove these workflows.

| Area                             | Current limit and required next decision                                                                                                                                                                                                                                                                                                                               |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Human certificate handover       | Replacement removes current material before issuance. There is no overlap, first-use activation, delivery acknowledgement, or durable revocation history. Define the workflow state and trusted activation signal before adding these transitions.                                                                                                                     |
| Approval binding                 | The operator consumes a timestamp and binds its generated CSR and key to that issuance. There is no pending client CSR flow or explicit approval deadline. Define the request and approval contract.                                                                                                                                                                   |
| Integration workload credentials | Integration has product metadata, extra Roles, and intended network policy only. Named endpoints, connections, credentials, destination acknowledgements, activation, and cleanup are not implemented. Finalize the manifest and native adapter contracts.                                                                                                             |
| Effective permissions            | Core resolves direct references. It has no shared ancestor-membership and effective-role calculation. Define the consumer contract and its conformance tests.                                                                                                                                                                                                          |
| Credential readiness             | UserBinding tracks its own generation only. Credential annotation changes do not change that generation. Add acknowledgement of the exact credential set and permission revision before treating binding readiness as access readiness.                                                                                                                                |
| Native enforcement               | There is no Core ForwardAuth service, native OCSP enforcement, or authenticated native first-use signal. Secret deletion cannot revoke an exported certificate. Integration consumers must enforce accepted records and validity windows.                                                                                                                              |
| Concurrent invariants            | Per-object admission does not serialize concurrent group moves or reference creation and deletion. Choose a coordinated write path for these invariants.                                                                                                                                                                                                               |
| Enrollment and REST              | The restored API remains the small enrollment baseline. Bootstrap persistence, renewal operations, client CSR enrollment, ETags, effective permissions, and the full REST contract remain incomplete. Invite redemption counts a use before User creation and is not a multi-object transaction. Callsign uniqueness after rename needs a coordinated mutation policy. |
| Dependency baseline              | This branch keeps the locked PyPI Cloudcoil 0.8.0 dependency. The handoff requests a locked GitHub main commit. Select and validate that commit as a separate dependency migration.                                                                                                                                                                                    |
| Operations                       | Offline installation, native integration adapters, restore, upgrade, and live certificate issuance need environment tests. Restoring a User under a new Kubernetes UID requires a new identity certificate.                                                                                                                                                            |

Webhook, server TLS, and API signing certificates retain automatic renewal.
The no-renewal rule applies to user identity certificates.
Routine revocation preserves the User object.
Hard deletion remains an explicit operation with UserBinding admission checks.
