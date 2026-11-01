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
  checks compiler HEAD and tracked modifications; the native verifier additionally
  checks untracked *and ignored* compiler/guest source input paths (without
  consulting .gitignore). A passing source pin alone
  does **not** prove a clean compiler binary. Bind the compiled class/JAR hashes.
- Inspect the **exact head tree** of this PR; do not silently run a changed or
  locally patched fixture. A zero-step CI job is runner-admission evidence only.

## Host-only verifier regression suite (NOT guest execution)

Run on any host with Bash and Git; no JDK 25, Maven, private compiler,
PostgreSQL, or network is needed:

```sh
bash -n scripts/verify-native-plans
bash -n tests/verify-native-plans-host.bash
bash tests/verify-native-plans-host.bash
```

This test is deliberately isolated from the real guest: it initializes
temporary **mock Git repositories**, a fake Maven build, a fake Java 25
launcher, and fake guest outcomes, then removes them. No fake receipt is
valid native evidence. Ten cases cover normal mocked results; missing
guest-start sentinel; **wrong negative panic diagnostic**; wrong Maven Java;
stale evidence directory; wrong reviewed ORM SHA; untracked fixture;
ignored guest and compiler source; and dirty tracked source.

### Exact diagnostic oracle (P0 correction)

The negative fixture `pg.find_in_workspace("", ...)` reaches
`pg.ident("")`, whose actual source panic is
`invalid PostgreSQL identifier surface`. The previous verifier
mistakenly expected `empty PostgreSQL identifier` and would have
falsely rejected the correctly failing guest. The real negative oracle
now matches the authored panic string.

To prevent future drift, the host mock-suite first checks that both
verifier diagnostics match explicit `panic(...)` strings in
`src/pg.ores`, and that both earlier negative fixtures call their intended
operations. The wrong-diagnostic case must fail closed.

**Executed host-only evidence:** exact reconstructed verifier Git blob
`690244a50f8dbb2a690d1d9dd82655cf399e179d`; mock-suite Git blob
`54503f9273c50c3cfb2483562165f1f4081ec799`.
Both SHA-1 blobs matched the GitHub source; both passed `bash -n`;
the full ten-case mocked suite ran locally and printed
`MOCK_HOST_GATE_SCENARIOS=10/10 PASS`. Source diagnostics were
checked against verified excerpts from `src/pg.ores` and the two
negative fixtures. These are **host/mock tests only**. The true Oreslang
compiler, guest panics, live PostgreSQL behavior, and cross-backend
parity remain **NOT EXECUTED**.

The separate CI job `.github/workflows/pg-host-verifier.yml` runs these
host-only checks after runner admission is restored. It cannot satisfy the
native guest/release gate.

## Host-only launcher hardening checks (not native guest proof)

```sh
bash -n scripts/ores
bash -n tests/verify-launcher-host.bash
bash tests/verify-launcher-host.bash
```

The launcher requires an explicitly selected Java 25 runtime when
`ORES_JAVA` is provided and rejects mismatched compiler SHA, dirty or
untracked/ignored compiler build inputs, missing classpath and missing
`OresMain.class`. Eight standalone host-only mock scenarios are
authoritatively identified by Git blobs
`f6f6319e671f7caa09d927156fe389a2c22b5ce5` (launcher) and
`106ac7192dd765b7d46f66206662ec89c69979b4` (test).
Both files were reproduced exactly and passed `bash -n` locally;
**8/8 mock launch scenarios executed and passed**. No private compiler
or genuine Oreslang guest was executed in those tests.

### Alternate-org admission screening

Source-free workflows on private `athlet-o/athleto-sync`
(run `41231046150`) and `honeypot-r-us-test/hnpt-e2e`
(run `41231112018`) both finished failure with no steps. Prior source,
Voxletra and Benefactor source-free runs failed similarly, and more
recent admission-focused runs in Zed/Scintilla/Akrion also had no
executed steps. These runs do not reveal the exact billing/policy
reason; **no private ORM tree has been transferred**. See issue #7.

### 2026-10-31 C0/DEL incremental fixture extension

`invalid_identifier_surface` now enumerates **32 C0 characters plus DEL**
in `src/pg.ores`, with an independent 33-value positive guest catalog.
A separate `control_identifier` negative guest emits its own start marker
before calling `pg.ident("bad\\u0001name")`. The verifier now runs and
hashes **four** guest input files, not three. The mock verifier has four
fake guest responses and expects four outcomes plus the TSV header;
its scenario count remains ten.

A source-level cross-file audit confirmed **14/14 control catalog,
fixture, verifier, and mock-harness invariants**, with all 33 distinct
control values in both independent catalogs. The **newly modified host
suite and native guest have not been executed** at this head. The earlier
10/10 host mock PASS cited above pertains to preceding verifier/mock
blobs, not this revision. The isolated JDK25 compiler and PostgreSQL
integration remain unexecuted.

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
`RESULT.txt` **only after all four separate native guest processes pass**.
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
| `tests/negative/control_identifier.ores` | negative execution | `tests/negative/control_identifier.ores` | Nonzero guest exit, exact stdout sentinel `PG_NEGATIVE_CONTROL_IDENTIFIER_STARTED` and `invalid PostgreSQL identifier surface` on stderr; no SQL output |

Each invocation has the form `ORESLANG_SOURCE_DIR=/ABSOLUTE/AUTHORIZED/oreslang-source.java ./scripts/ores <suffix>`.
Use separate processes for negative fixtures to avoid catching/relabeling a
runtime panic as a successful assertion. Capture raw output and reject skipped
or silently missing negative fixtures.

The positive guest checks quoting of hostile table names, the type allowlist,
nullable columns, parameter/SQL separation and the exact generated DDL text.
It now also contains an **unexecuted** typed UNIQUE/FOREIGN KEY SQL golden and
negative fixtures for duplicate constraints/columns, missing local columns,
empty UNIQUE, mismatched FK arity, an injected remote table and qualified
referenced column. This is a bounded subset of DDL, not arbitrary CHECK
expressions or source-authored constraint SQL.

The new constrained-table builder limits column count (64), PK arity (32),
extra constraints (32) and local columns per constraint (32).
The new renderer emits complete DDL directly; additional positive fixtures
assert unchanged PK-only SQL, ordered distinct UNIQUE/FK clauses, exact
duplicate comparisons, copied caller-owned constraint arrays and
fresh-copy read accessors that cannot mutate the stored identifiers.
The `QueryPlan` fixtures test copied bound strings, mutation of legacy
source arrays after snapshot creation and parameter index bounds. These
new assertions are **authored, not executed by the native compiler**. It relies on
the same conservatively admitted ASCII identifier path. A real PostgreSQL
17 parse/execute test is required before claiming valid DDL or foreign-key
behavior; the host reference golden cannot establish database validity.
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

## Future Diesel/SeaORM generated-ORM acceptance suite (NOT EXECUTED)

The [separate compile-fail, ActiveModel, relation and migration matrix](DIESEL_SEAORM_ACCEPTANCE.md) adds static type-safety, SQL/bind, tenant and cancellation gates. These are **specifications only**: the AOT schema descriptors, driver and generated model APIs must first be implemented and then exercised by actual nonzero-step native guest and PostgreSQL runs. Existing planner negative tests are not evidence for these new features.

## Implemented-source typed patch acceptance (native execution pending)

The `tests/plans.ores` positive guest now includes native-source assertions
for closed `PgType`, UUID lexer, `DbValue` admission, parameter separation,
explicit SQL NULL, `NotSet` / `Unchanged` no-ops, field type mismatch,
forged field state, tenant/PK mutation protection, and SQL-identifier
injection. These **source-authored tests have not executed** against the
pinned compiler. Positive suite stdout remains
`Postgres SQL planning contracts passed` only.

The checked single-field patch planner is **data-only**. It is not a live
PostgreSQL transaction, a complete `Change<T>` generic or a generated
schema capability. Do not promote it as authorization: the UUID string is not
verified against authenticated RLS tenant ownership. Real actor-owned
connection + independent PostgreSQL RLS tests remain P0 blockers.

The new `PgTableDescriptor` positive guest cases also verify that table
schemas require nonnullable UUID `id` and `workspace_id`, reject duplicate
columns and unsupported types, prevent mutation of the original/returned
column arrays, and reject patch fields missing from the declared schema.
These are **unexecuted guest assertions**, not proof that `PgTableDescriptor`
is a compiler-generated nominal capability or PostgreSQL tenant authority.

## New multi-field planner and projection checks (not executed in a native guest)

`tests/plans.ores` contains data/SQL goldens and adversarial checks for
`plan_schema_update_fields_checked` and `plan_schema_select_columns_checked`:
canonical multi-column SQL with typed placeholder order; bound hostile text;
explicit nullable NULL versus omitted/unchanged; empty/no-op updates; duplicate
field admission; schema-only field scope; immutable tenant/id; mismatched
codec/NULL; 8-field admission boundary; projection wildcard/unknown/duplicate/
injected columns; tenant UUIDs and parameter bounds. These are **source-authored
assertions only** until the exact pinned compiler and PostgreSQL driver run.
