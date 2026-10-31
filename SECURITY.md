# PostgreSQL ORM planning security contract

Status: **experimental / no live-driver execution evidence**. This document is
a scope and release-gating contract, not certification.

## Trust boundaries

1. `pg.admitted_identifier` is a narrow safe input policy for typed DDL:
   ASCII `[A-Za-z_][A-Za-z0-9_]*`, 1..63 bytes, counted through
   `split_literal(...).size` after mapping the known ASCII alphabet to a delimiter.
   Non-ASCII, quotes, NUL/C0 controls and dotted/qualified input are rejected.
   The older `pg.ident` only escapes embedded quotes and rejects empty/LF/CR/TAB
   surfaces: it does not enforce complete NUL/C0 or byte-length admission and
   is not an authorization capability. Do not pass untrusted identifiers to
   `pg.ident`, `pg.table`, `pg.column`, or `pg.find_in_workspace`.
2. `pg.column` accepts a small fixed PostgreSQL type list. Legacy `pg.table`
   accepts **raw SQL column and constraint strings** and MUST NOT receive
   user-supplied content. No application should call it from request/tenant
   data. Its presence is a compatibility escape hatch, not a safe API.
3. `pg.table_typed_pk` renders declared `ColumnSpec` data and primary-key
   references through admitted type/identifier formatting, rejecting empty
   names, unknown types, missing keys, nullable primary-key columns and\n   duplicate names/keys. It is a
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

## Release-blocking negative oracles

- Typed-identifier: ASCII 63/64-byte boundary, quotes, NUL, C0 controls,
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
