# PostgreSQL ORM planning security contract

Status: **experimental / no live-driver execution evidence**. This document is
a scope and release-gating contract, not certification.

## Trust boundaries

1. `pg.admitted_identifier` is a narrow safe input policy for typed DDL:
   ASCII `[A-Za-z_][A-Za-z0-9_]*`, 1..63 bytes, counted through
   `split_literal(...).size` after mapping the known ASCII alphabet to a delimiter.
   Non-ASCII, quotes, NUL/C0 controls and dotted/qualified input are rejected.
   The legacy `pg.ident` escapes embedded quotes and now rejects
   empty names and every ASCII C0/DEL control, including NUL. It still
   does not enforce PostgreSQL's 63-byte UTF-8 identifier limit, Unicode
   normalization, or tenant authorization; it remains trusted-only. Do not pass untrusted identifiers to
   `pg.ident`, `pg.table`, `pg.column`, or `pg.find_in_workspace`.
2. `pg.column` accepts a small fixed PostgreSQL type list. Legacy `pg.table`
   accepts **raw SQL column and constraint strings** and MUST NOT receive
   user-supplied content. No application should call it from request/tenant
   data. Its presence is a compatibility escape hatch, not a safe API.
3. `pg.table_typed_pk` renders declared `ColumnSpec` data and primary-key
   references through admitted type/identifier formatting, rejecting empty
   names, unknown types, missing keys, nullable primary-key columns and
   duplicate names/keys. It is a
   restricted DDL builder, **not** general PostgreSQL AST coverage.
   Lexical identifier admission does not establish tenant authorization,
   transactional safety, or safe arbitrary SQL expressions.
3a. `pg.table_typed_pk_constraints` adds allowlisted data-only
   `UNIQUE` and `FOREIGN KEY` rendering. Inputs may only select
   validated local and referenced identifiers; the builder rejects
   duplicate/local-missing columns, mismatched FK arity, malformed or
   repeated constraint specifications and quoted/qualified identifiers.
   The renderer composes the full statement directly (no terminator
   string replacement) and compares duplicate clauses exactly. The
   `ConstraintSpec` constructor copies caller arrays into private
   fields. Both public read accessors return fresh arrays, preventing
   source- and accessor-alias mutation. This is not an independently
   verified cross-actor `Sendable` guarantee; objects stay actor-local. Referenced key existence,
   target uniqueness, permissions, lock behavior and tenant authority are
   **outside this planner**. This is unexecuted draft work; a real
   PostgreSQL DDL/rollback test remains mandatory.
4. Legacy `Query.sql` and `Query.params` remain distinct but
   `params` is a mutable actor-local array. New `QueryPlan` performs a
   defensive copy of its bound strings and exposes no public mutable array;
   `param_at(index)` returns a checked `Result`. This is a local
   value-snapshot guarantee, **not** runtime Sendable authorization or a
   database execution capability. `snapshot_legacy_query` explicitly
   preserves arbitrary SQL from the trusted legacy source; a driver must not
   accept it as a whitelisted/tenant-authorized prepared query. Runtime
   ownership, typed DbValue, and stale-connection fencing remain blockers.
5. `find_in_workspace_checked(table, workspace, id)` admits only the same
   bounded ASCII table identifiers as the typed DDL API and keeps values
   separate from SQL. The original `find_in_workspace` remains legacy and
   lacks complete identifier admission. Neither method is tenant
   authentication. A caller-provided workspace string is not authority.
   The execution adapter must bind tenant identity to an authenticated
   capability and configure independent PostgreSQL role/RLS restrictions.
6. No PostgreSQL wire protocol, prepared-statement cache, connection pool,
   transaction/cancellation implementation, row stream, or migrations API is
   implemented here. Never infer those capabilities from generated SQL.

## Native launcher admission

`scripts/ores` refuses missing explicit `ORES_JAVA`, a non-JDK25 runtime,
a mismatched `SOURCE_REF`, dirty or untracked/ignored compiler build inputs,
and absent Maven classpath or `OresMain.class`. It does not fall back
silently from a supplied Java binary. The self-tests
`tests/verify-launcher-host.bash` simulate successful and failing launcher
admissions using dummy files and fake Java executables; **11/11 passed locally**
against verified Git blobs. The launcher rejects stale alternate classpaths
and symlinked runtime artifacts, not only absent classpath/class files. This is only host admission
proof, not a successful private compiler build or guest execution.

Cross-organization private-source mirror testing is permitted by this
task's explicit user request, but **none of the checked private
candidate organizations has demonstrated runner admission**. Do not
replicate the private ORM/compiler source merely to accumulate
non-executing jobs; keep source local to the owner until an authorized
private runner is confirmed. No source has been copied cross-org in
this task.

## Release-blocking negative oracles

- Typed-identifier: ASCII 63/64-byte boundary, quotes, NUL, C0/DEL controls,
  Unicode, reserved words, case sensitivity, schema qualification and truncation
  collisions. Reject unsupported inputs explicitly. Separate tests must enforce
  the legacy API's trusted-only boundary; it is not equivalent to typed admission.
- Schema: unknown type, empty columns/keys, duplicate names/keys,
  undeclared primary-key reference, malformed foreign/unique/check expressions,
  raw-SQL injection through legacy inputs.
- Values: hostile bound strings never appear in SQL text; mutation of a bound
  `Array` after plan creation must not alter the dispatched plan; stale actor
  or connection generation must fail closed.
- Execution: cross-workspace access denied by independent PostgreSQL RLS;
  prepared-query binding, cancellation, rollback, connection retirement,
  bounded backpressure, malformed wire lengths, SQLSTATE and error mapping.
- Migration: deterministic SQL/diff checksums, locked serialization, no
  silent drift, no automatic destructive DDL, explicit approval gates.

## Evidence policy

Run `tests/plans.ores` against the exact compiler commit in `SOURCE_REF`
using the native launcher, with a clean compiler tree. A real nonzero-step run
must include the compiler commit/tree, repository head/tree, exact commands,
expected diagnostics and test outcomes. Test this branch's actual tree, not
`main` or a merge base. Compile and execute with the Java backend first,
then require independent executable evidence for LLVM, Wasm, .NET and Forge
before claiming cross-backend parity. Do not convert skipped, zero-step,
failed-admission, Rust receipt self-test or model-check results into native
execution passes.

Run integration fixtures against disposable real PostgreSQL under restricted
roles and independent RLS tests before any production promotion. The current
source contains no such driver or integration harness. Do not export private
source to another organization or relax branch protection to obtain CI results
without separate approved source-transfer policy.

## C0/DEL additional guest gate

The legacy quoted-identifier path now enumerates and rejects all 33
ASCII C0/DEL characters. The positive native fixture checks every byte
independently, while `tests/negative/control_identifier.ores` verifies that
`pg.ident` panics before emitting SQL. The exact error diagnostic is
`invalid PostgreSQL identifier surface`. Its separate runtime-start marker
must be observed; a compiler failure cannot count as a negative guest pass.
This change is not yet validated by a real pinned JDK25 guest run.

## SQL-only PostgreSQL 17 transactional constraint gate (new)

The opt-in `tests/pg17-ddl-contract.bash` fixture is deliberately separate
from native guest evidence. Before connecting, it checks for the exact DDL
golden authored in `tests/plans.ores`; its PostgreSQL script uses a generated
simple-ASCII schema inside `BEGIN` / `ROLLBACK` and fails unless the schema
is absent afterward. It checks UNIQUE, FK, NOT NULL and composite PK rejects
with distinct PostgreSQL exception categories. An explicitly disposable database
and `PG_TEST_DISPOSABLE=I_ACKNOWLEDGE_DISPOSABLE_DATABASE` are mandatory. The SQL-only gate also reads the server's `server_version_num` and fails unless the backend identifies as PostgreSQL 17; a client-version string is insufficient. The DDL SQL checks `server_version_num` again inside its transaction, preventing a routed preflight connection from certifying a different backend used by the actual DDL.

The CI `pg17-ddl-integration.yml` declares a disposable PostgreSQL 17
service, **but a declared CI job is not an executed job**. The separate mock
suite `verify-pg17-ddl-host.bash` runs without PostgreSQL and checks
negative preflight, altered-output, fixture-drift-before-connection,
and server-major checks; **10/10 cases passed locally** with exact matching GitHub shell-script blobs, including
rejection of PostgreSQL 16/18 or missing/malformed version inspection. This does not prove that Oreslang
emits the SQL, that database access is authorized, that RLS is enforced, or
that a PostgreSQL driver/actor connection exists. Do not promote the ORM
on this contract alone.
