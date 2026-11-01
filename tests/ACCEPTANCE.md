# PostgreSQL planner: executable acceptance gates

Status: **NATIVE ORESLANG GUEST NOT EXECUTED at this pull-request head**. This is a guest test plan and
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
`OresMain.class`. Eleven standalone host-only mock scenarios are
identified by current Git blobs
`fc88f48a612f32954c3919100476f424f7f74cab` (launcher) and
`d89f6ef3d278b85a54086fe797b118347561069e` (test).
Both files were reconstructed exactly, verified by `git hash-object`,
passed `bash -n`, and **11/11 scenarios executed and passed**,
including stale alternate classpath and symlinked classpath/class rejection. No private compiler
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
control values in both independent catalogs. The expanded four-guest **host-only** suite has now executed and passed
at the current scripts' exact Git blobs (see the updated host receipt below).
The native Oreslang guest has **not** executed. Earlier mock results
remain historical evidence for older verifier/mock blobs. The isolated JDK25 compiler and PostgreSQL
integration remain unexecuted.

## 2026-10-31 current-head executable host gate (NOT native)

The verifier now enforces exact guest-case order
(`positive`, `empty-identifier`, `empty-table`, `control-identifier`)
and requires exactly four `PASS` rows, plus a TSV header, before it may
write a `VERIFIED:` receipt. This is an independent check in addition
to calling each guest. The host harness checks the existence of those
fail-closed manifest gates.

**Executed against byte-identical script files (Linux, Bash + Git):**
`bash -n` passed all four scripts; the verifier mock suite
**10/10 PASS** and *historical* launcher mock suite **8/8 PASS**.
The current launcher suite expanded to **11/11 PASS**; see the current
Git blobs listed above.

- `scripts/verify-native-plans` Git blob:
  `8e356f83ba8acf445ca296c99d5c5bbd58a3af97`
- `tests/verify-native-plans-host.bash` Git blob:
  `bec97bcfd19e912b017c36bb1c37c27d8b7301df`
- `scripts/ores` Git blob:
  `f6f6319e671f7caa09d927156fe389a2c22b5ce5`
- `tests/verify-launcher-host.bash` Git blob:
  `106ac7192dd765b7d46f66206662ec89c69979b4`

The host mock suite deliberately uses fake compiler and guest worktrees
and locally verified **source excerpts**, not full byte-identical
`src/pg.ores` or `tests/plans.ores` files. It proves the verifier's
mocked control flow and guard presence, **not** the real Oreslang
compiler, an actual PostgreSQL database, tenant isolation, or backend
parity. The updated tests are not a successful source-org Actions run;
CI admission still fails with zero executed steps.

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

## SQL-only PostgreSQL 17 executable constraint gate

An independent integration workflow `.github/workflows/pg17-ddl-integration.yml`
provisions PostgreSQL 17 and invokes `tests/pg17-ddl-contract.bash` with
an explicit disposable-database opt-in. This test renders **no** native guest
source: it checks that the authored Oreslang golden remains unchanged, executes
the corresponding SQL on an ephemeral PostgreSQL schema, verifies UNIQUE,
FOREIGN KEY, NOT NULL and composite PRIMARY KEY behavior, rolls back and
confirms the schema did not persist.

The SQL gate now requires a successful `SHOW server_version_num` response
identifying the **PostgreSQL 17 server**, not merely a PostgreSQL 17 client.
It also checks `current_setting('server_version_num')` inside the same SQL
transaction as the DDL, so the preflight connection alone cannot certify
a separately routed PostgreSQL backend.
The separate host-only mock `bash tests/verify-pg17-ddl-host.bash` passed
**10/10** locally (missing opt-in, missing DSN, source golden drift before
any database contact, normal fake psql, unexpected
nonzero schema count, failed SQL process, PostgreSQL 16, PostgreSQL 18,
malformed server version, and failed version probe). Its exact GitHub blobs
matched the locally syntax-checked and executed scripts:
`tests/pg17-ddl-contract.bash` =
`445fd679fa4024e5cd479581f953ac2bc195b6ad`,
`tests/verify-pg17-ddl-host.bash` =
`7170ed9c321bde1e29043dd747b61ea18a56b358`.

The previous **5/5** and **9/9** evidence belongs to earlier host script
blobs. This **10/10** result proves only fake-psql control flow; no real PostgreSQL 17 process ran.

**Actual PostgreSQL 17 SQL execution: pending until a CI runner admits the
service job, or an authorized disposable database is supplied.** Native JDK25
Oreslang compilation, driver parameter binding, cancellation, independent
tenant RLS and five-backend parity remain distinct unfulfilled gates. The
SQL-only job must not be counted as native or production release evidence.

## Native pinned-compiler schema regression extension (not yet executed)

The six-oracle scripts/verify-native-plans path now demands the existing PostgreSQL planner positive and three negative guest cases plus tests/schema-plans.ores and tests/schema-adversarial.ores. Every stdout is exact-compared; nonzero, missing or reordered cases fail the receipt, and both additional guest sources are included in provenance hashes. tests/verify-native-plans-host.bash deliberately withholds the new adversarial sentinel to test fail-closed admission. The new Oreslang suite has 83 explicit panic assertions with parameterized kind and risk cases. These remain authored source, not compiler-backed evidence until an exact-head native job executes.

## Seven native oracles: additional metamorphic catalog guest (authored, NOT executed)

`tests/schema-invariants.ores` adds 57 native Oreslang assertions on empty/ordered/reordered catalogs, creation/deletion inverse direction, manual stable-ID renames, name collisions, nullable add-vs-destructive reverse diff, deterministic nominal class previews, unsupported UUID/nullable types, malformed public descriptors, and deny-by-default review manifests. `scripts/verify-native-plans` now pins the seventh guest, fingerprints its exact source, compares stdout, and requires eight receipt rows including the header. The host mock harness adds missing-invariants-sentinel rejection and reports 12 mock scenarios. No native compiler or PostgreSQL evidence is claimed.


## Five additional fail-closed host/mock injection branches (draft verification)

The seven-required-guest exact-head harness remains unchanged. The **mock**
self-test suite grows from 12 to **17 scenarios**: successful fake baseline
plus deliberate missing-guest, broken provenance, invalid JDK/SDK, and five
new signal-substitution cases (zero-exit but wrong stdout, valid stdout but
nonzero exit, launcher sentinel rc=69, negative guest erroneously succeeding,
and unexpected output from a negative guest). The 17/17 label is the **expected
mock-harness result**, never a claim that native execution occurred.

The seventh Oreslang guest adds independent three-way
`plan_from_snapshot_checked` cases for fresh, stale, malformed and permuted
snapshots, including a desired state that happens to equal unauthorized
observed drift. Both native and shell smoke tests need a stepful trusted run.


## PostgreSQL 17 SQL-only catalog and migration-lock E2E — authored, not DB-executed

Two new disposable-database integration fixtures are included in
`.github/workflows/pg17-ddl-integration.yml` and are strictly separate
from the pinned JDK25 pure Oreslang guest verification gate.

- `tests/pg17-catalog-readback-e2e.bash` validates explicit opt-in,
  a PG17 server-version probe, a bounded temporary schema name and an exact
  two-line receipt. It runs `tests/pg17-catalog-readback-e2e.sql`, which
  captures real `pg_catalog.pg_attribute` column name/type/nullability
  projections, repeats a guarded nullable-column addition, rejects injected
  column type, rename and extra-column drift, then **ROLLBACKs** and requires
  zero surviving fixture schemas.
- `tests/pg17-migration-lock-e2e.bash` opens **two independent PostgreSQL
  connections**, requires a real `pg_try_advisory_xact_lock` conflict while
  one transaction holds the lock, and verifies post-COMMIT release. A missed
  lock or unsuccessful holder cannot produce a passing receipt.

Run **only against an isolated disposable PostgreSQL 17 database**:

```sh
export PG_TEST_DISPOSABLE=I_ACKNOWLEDGE_DISPOSABLE_DATABASE
export PG_TEST_DSN='postgresql://test_user@isolated_host/disposable_db'
bash tests/pg17-catalog-readback-e2e.bash
bash tests/pg17-migration-lock-e2e.bash
```

**Executed host-only evidence:** the two GitHub Bash blob identities
`4b6b50d62f64362f62d8a957a37f5e6a1d38e4c8` and
`deb83d7d50641af6eafb9e90b2fac7d98386fc3d` matched the local
byte-for-byte Bash files via `git hash-object`. Both passed `bash -n`.
An **18/18** local **fake-psql** test matrix passed missing opt-in, missing
DSN, PostgreSQL 16/18/malformed versions, version-probe errors, mocked
correct/wrong rollback receipts, failed mocked catalog commands and simulated
two-session lock behavior. That is harness verification, **NOT live PG17**.

The PostgreSQL 17 server was unavailable in the local execution container
and source Actions jobs still failed before runner allocation; these two
actual database tests remain **NOT EXECUTED**. Do not promote, merge or
claim live PostgreSQL proof from fake-pg mocks. These tests do not certify
TypeSpec/JSON Schema semantic parity, a stable-ID ledger, unmodeled database
objects, actual DPM migration artifacts, a native Oreslang driver, actor
leases, or backend parity.


## 2026-11-01 migration history/checksum replay E2E (SQL-only, unexecuted)

New `tests/pg17-migration-history-e2e.sql` and the guarded
`tests/pg17-migration-history-e2e.bash` extend the isolated PostgreSQL 17
service workflow. The SQL reference ledger records sequential migration
version numbers and 64-character lowercase hexadecimal digests.
It verifies that replay of the *same* digest does not create another
ledger row, while changed digests, skipped versions, zero/NULL versions,
NULL/noncanonical digests and uppercase digest strings are **rejected with
specific SQLSTATE 23514 diagnostics**. The fixture explicitly rolls back
every table/function it creates and demands a zero-surviving-schema receipt.

The catalog E2E fixture was also hardened: all five drift provocations
(type change, physical rename, new column, nullability relaxation and
column drop) require the exact `CATALOG_SHAPE_DRIFT` diagnostic. An
unrelated `check_violation` can no longer be silently counted as a pass.
These cases check only v1 physical column shape, not full SQL/database
catalog authority or real DPM migration-file digests.

**Actually executed local host evidence:** the exact migration-history Bash
wrapper blob `923705451240a8c5233eb483948e6c6bade0ddcd`
and SQL blob `d36b309acc5290e5d263f123df14e774d7341b68`
were reproduced byte-for-byte and verified with `git hash-object`.
The wrapper passed `bash -n`, and **21/21 fake-psql host-mock cases
passed**, covering no opt-in, missing/empty DSN, PostgreSQL 16/18 and
malformed versions, failed server probe, incomplete or forged receipts,
failed SQL subprocess and one expected mock success. They prove only
shell control flow. `tests/test_schema_contract.py` additionally authors
three Python subprocess methods to exercise these mock gates in CI
(total **48 host test methods**, not executed as a full suite).

**Actual PostgreSQL 17 ledger/collision/rollback SQL execution is
NOT VERIFIED.** PostgreSQL server binaries were unavailable locally;
source GitHub Actions job runs failed before runner allocation. These tests
do not establish native Oreslang execution, TypeSpec/JSON Schema parity,
PostgreSQL driver correctness, actor/tenant ownership, or full-catalog
migration authorization. The migration ledger is an isolated SQL reference,
not a production migration tool, a real file hash attestation or a green
release gate.


## Additional migration recovery and rollback-lock E2E (authored; PG17 not run)

The PostgreSQL 17 SQL-only history fixture now tests a failed migration's
savepoint rollback, including:
- A transient version-3 application followed by identical-digest replay.
- Discard of its ledger row using `ROLLBACK TO SAVEPOINT`.
- Proof that the discarded version is missing and total rows return to two.
- A fresh retry with a *different valid hexadecimal digest*, undone within
  an exception subtransaction, leaving the ledger unchanged.
The outer fixture still has exactly one final `ROLLBACK` and the same
seven-line test receipt. The recovery checks do not hash real migration
files, and they do not implement a production migration engine.

New `tests/pg17-migration-lock-abort-e2e.bash` is registered beside the
existing commit-lock E2E in both CI workflows. It opens two independently
connected PostgreSQL clients, requires transaction advisory-lock contention,
and checks that a `ROLLBACK` releases the lock. The original script
independently checks the `COMMIT` release path.

**Exact-source, executed host evidence:** both local lock scripts matched
their exact GitHub blob SHAs:
`deb83d7d50641af6eafb9e90b2fac7d98386fc3d` (commit)
and `6f24ea264b89313367f15ca70c12583771ecb04b` (rollback).
Both passed `bash -n`. An isolated fake-`psql` process test executed
**8/8 passing host-fault scenarios**: one normal mocked path plus
holder-process failure, malformed try-lock output and unreleased lock,
for each transaction ending. A race in the mock was detected and fixed
by synchronizing with the fake holder's startup marker before fault
injection. This is **NOT** a PostgreSQL 17 runtime pass.

Fourteen source-only consistency checks passed on the exact GitHub
blobs (balanced dollar-quoted blocks, one outer ROLLBACK, savepoint
recovery guards, canonical retry digest, transactional lock primitives,
CI registration, fake-holder synchronization, and unique Python method
names). `tests/test_schema_contract.py` contains **50 authored test
methods**, including executable host lock-mutation tests and source-level
recovery assertions.

**Still unverified:** genuine PostgreSQL 17 execution; the full
official Python/jsonschema test suite; pinned native Oreslang compiler
and guest execution; full TypeSpec/JSON Schema peer contract equivalence,
DPM full-catalog changes, production-safe migration admission, and
cross-backend actor/driver conformance. The source GitHub Actions
admission problem has not been resolved; a zero-step job is neither a
test failure nor a passing test. Do not transfer private source across
organizations while the unresolved source-exposure incident is open.


## PostgreSQL 17 non-column metadata preservation gate (2026-11-01)

Added `tests/pg17-catalog-metadata-e2e.sql` and guarded
`tests/pg17-catalog-metadata-e2e.bash`. They are SQL-only test fixtures
against a **disposable** PostgreSQL 17 instance; they are not native Oreslang
or Declarative Migrations (DPM) execution or an approval mechanism.

The fixture starts a transaction, creates a randomly named isolated schema,
a test table, primary key and check constraint, a separate unique index,
FORCE + ENABLE row-level security, a tenant policy, and a column default.
It records PostgreSQL catalog-projected policy expressions and default
expressions before applying a nullable-column addition. It requires that
`pg_class`, `pg_policy`, `pg_constraint`, `pg_index`, and `pg_attrdef`
continue to match the reviewed baseline after the addition.

Thirteen mutation cases must fail with SQLSTATE 23514 **and the exact**
`PROTECTED_CATALOG_DRIFT` diagnostic: RLS disable, FORCE RLS removal,
policy removal, policy weakening, policy role-scope changes, injection of
an additional permissive policy, unique-index drop, check-constraint
drop, and column-default change. The extra four cases replace a same-name
unique index, CHECK constraint, and primary key with weaker definitions and
inject an unreviewed index. The fixture now fingerprints the full
`pg_get_indexdef` and `pg_get_constraintdef` text and requires an exact
index/constraint inventory, rather than trusting object names alone. PL/pgSQL exception subtransactions
roll back the hostile mutations, and the outer transaction always
`ROLLBACK`s. The final query must show that the temporary schema
did not survive. This covers selected catalog objects; grants,
extensions, triggers, arbitrary index definitions and cross-schema
dependencies remain outside this fixture's authority.

Both the PostgreSQL 17 service workflow and the host-contract workflow
register the new files; `orm-schema-contract.yml` now discovers all
`test_*.py` files. A standalone Python module adds **three authored
host-only methods** with source guards, Bash syntax checking and simulated
`psql` response mutation. The consolidated authored suite has
**59 Python test methods** (56 schema + 3 metadata).

**Executed locally on an isolated host:** exact wrapper Git blob
`778432466819013cc3f558693c2c46c8052da653` matched
`git hash-object`; `bash -n` passed; **13/13 fake-psql subprocess
scenarios passed** (no opt-in/DSN without contact, PG16/PG18 and malformed
server versions, version-probe failure, correct mock receipt, forged/extra/
incomplete receipt and SQL-subprocess failure). Exact-tree inspection
also passed **20/20 source consistency checks** including all seven
drift-rejection blocks and correct CI registration. These do **not**
execute the fixture's actual SQL or certify a PostgreSQL server.

**Unverified release gates:** real PostgreSQL 17 service execution;
actual pinned JDK25 Oreslang guest execution, live driver and actor
ownership; independently executed TypeSpec/JSON Schema parity and
full DPM catalog/approval; all five backend parity. GitHub source
Actions run IDs 41280293922 and 41280293938 failed before runner
allocation (`runner_id=0`, `steps=[]`); 41280290489 contained
zero jobs. The private-source cross-org export hold from security
issue #22 remains in force. Keep PR draft; no production database
or source `main` was changed.


## Actions admission and supply-chain guard (security hold #22)

`.github/workflows/orm-schema-contract.yml` now uses SHA-pinned
`actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683`
(v4.2.2) and
`actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065`
(v5.6.0), verified against the action repositories' Git tag refs. Checkout
uses `persist-credentials: false`. The workflow now runs Python test-file
compilation and a `bash -n` syntax loop across all PG17 E2E shells before
host-only unit tests. `pg-host-verifier.yml` also watches the new PG17
fixtures and syntax-checks them, with old static scenario counts removed
from the job description.

`tests/test_workflow_security.py` adds source-only regression checks for
full-length action pins, disabled checkout credential persistence,
read-only token scopes, no privileged trigger such as
`pull_request_target`, discovery of both host test modules, registration
of every PG17 SQL-only gate, and zero source checkout in the source-free
runner-admission canary. The host tests cannot certify current GitHub
runner billing or eligibility; they should not be considered executed in
source Actions when the job has no steps.

**Security hold:** `oreslang-platform-conformance` issue #22 remains
open, explicitly disallows private-source export to another GitHub
organization, and requires independent review of earlier exposure.
Transferring a Git tree via API without secrets is still a prohibited
private-source transfer. No alternate-org repository was written or
mirrored during this hardening work. The Actions admission reason is still
unknown (issue `oreslang-source.java` #963); an owner must check
billing, eligibility, private Actions policy and runner groups before
claiming lack of minutes.
