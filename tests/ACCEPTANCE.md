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

## One-command native execution gate

From a clean checkout of this exact PR head, on an authorized machine with
**JDK 25, Maven and a clean pinned private Java compiler checkout**:

```sh
EXPECTED_ORM_SHA="$(git rev-parse HEAD)" \
ORESLANG_SOURCE_DIR=/absolute/authorized/oreslang-source.java \
ORES_JAVA=/absolute/path/to/jdk25/bin/java \
./scripts/verify-native-plans
```

The caller must independently pin `EXPECTED_ORM_SHA` to the **reviewed**
40-hex head, not blindly accept the working tree. The command above demonstrates
the shell interface; for independent release attestations substitute the pinned
reviewed commit value rather than deriving it from the local checkout.

The script stops on source HEAD mismatch, dirty tracked worktrees,
untracked guest source/scripts, bad compiler `SOURCE_REF`, wrong Java version,
missing tools, Maven build failure or absent generated runtime artifacts. It
runs `mvn clean package` against the exact pinned compiler, then hashes its
compiled classes, launcher, Maven runtime dependencies and guest inputs.

The evidence directory is created **outside** this repo by default and records
raw process output, exit statuses, exact commands, source/compiler tree identity,
compiled-artifact and dependency hashes. It writes `VERIFIED` to
`RESULT.txt` **only after all three separate native guest processes pass**.
A `NOT_VERIFIED` result is never a compiler or PostgreSQL test pass, and
harness-generated receipts remain subordinate to independent executed CI job
steps and logs. The script never accesses a PostgreSQL server or proves RLS.

For fail-closed negative guest tests, each fixture must print its **distinct
runtime-start sentinel** before invoking the rejected operation. A passing
negative oracle requires the exact sentinel as the only stdout, nonzero
non-launcher exit status and the specific panic diagnostic on stderr. Therefore
a parser/build failure before guest entry cannot pass merely because its error
message contained the desired string.

## Required guest runs

| Guest source | Phase | Command suffix | Oracle |
|---|---|---|---|
| `tests/plans.ores` | positive execution | `tests/plans.ores` | Exit 0 and exact stdout line `Postgres SQL planning contracts passed` |
| `tests/negative/empty_identifier.ores` | negative execution | `tests/negative/empty_identifier.ores` | Nonzero guest exit, exact stdout sentinel `PG_NEGATIVE_EMPTY_IDENTIFIER_STARTED` and error diagnostic; no query SQL output |
| `tests/negative/empty_table.ores` | negative execution | `tests/negative/empty_table.ores` | Nonzero guest exit, exact stdout sentinel `PG_NEGATIVE_EMPTY_TABLE_STARTED` and error diagnostic; no CREATE TABLE output |

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
  **before** SQL reaches the database. The typed-only path admits a conservative ASCII/63-byte subset; the
  legacy APIs do not implement full admission and cannot be promoted as
  production identifier validators.
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
