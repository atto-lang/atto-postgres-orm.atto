# PostgreSQL planner: executable acceptance gates

Status: **NOT EXECUTED at this pull-request head**. This is a guest test plan and
expected-oracle inventory, not a substitute for a native Oreslang compiler run.
The ORM planner does not execute SQL, authenticate tenants or own a DB socket.

## Provenance preflight

- Use **only** the private, authorized `oreslang-source.java` checkout at the
  exact 40-hex SHA in `SOURCE_REF`. Record compiler tree SHA and the runtime
  artifact digest, JDK version, command line, stdout, stderr and exit code.
- Build the compiler from that source with JDK 25, including Maven classpath
  generation as specified in the root README. The launcher in `scripts/ores`
  checks compiler HEAD and tracked modifications; a passing source pin alone
  does **not** prove a clean compiler binary. Bind the compiled class/JAR hashes.
- Inspect the **exact head tree** of this PR; do not silently run a changed or
  locally patched fixture. A zero-step CI job is runner-admission evidence only.

## Required guest runs

| Guest source | Phase | Command suffix | Oracle |
|---|---|---|---|
| `tests/plans.ores` | positive execution | `tests/plans.ores` | Exit 0 and exact stdout line `Postgres SQL planning contracts passed` |
| `tests/negative/empty_identifier.ores` | negative execution | `tests/negative/empty_identifier.ores` | Nonzero guest exit and diagnostic naming the empty PostgreSQL identifier; no query SQL output |
| `tests/negative/empty_table.ores` | negative execution | `tests/negative/empty_table.ores` | Nonzero guest exit and diagnostic naming a table without columns; no CREATE TABLE output |

Each invocation has the form `ORESLANG_SOURCE_DIR=/ABSOLUTE/AUTHORIZED/oreslang-source.java ./scripts/ores <suffix>`.
Use separate processes for negative fixtures to avoid catching/relabeling a
runtime panic as a successful assertion. Capture raw output and reject skipped
or silently missing negative fixtures.

The positive guest checks quoting of hostile table names, the type allowlist,
nullable columns, parameter/SQL separation and the exact generated DDL text.
The negative guests establish fail-closed planning behavior only. Neither
positive nor negative planner tests prove SQL execution or tenant isolation.

## Required later database gates (not runnable in this repository today)

- Real isolated PostgreSQL 17 query binding/plan execution via a revocable
  actor capability, with session/role lifetime constraints.
- Explicit rejection of embedded NUL and control characters, noncanonical
  qualified identifiers and identifiers over PostgreSQL's 63-byte UTF-8 limit
  **before** SQL reaches the database. Current planner does not implement these
  checks and cannot be promoted as a production identifier validator.
- A typed DDL AST replacing raw trusted SQL strings for columns/constraints;
  immutable, typed `DbValue` plans and a caller-independent tenant authority.
- Real RLS deny-by-default, cross-tenant read/write and SQL-template-poisoning
  adversarial tests. A custom `ores.tenant_id` GUC by itself can be set by any
  client holding the role credential and is not a non-spoofable principal.
- Exact-head independently reviewed executed CI steps, artifact hashes, and
  branch protection before a merge or production claim.

Keep Rust receipt-inspector host tests and Oreslang guest/backend test evidence
as **separate** classes. A syntactically consistent TSV receipt cannot certify
that the GitHub job or compiler actually executed.
