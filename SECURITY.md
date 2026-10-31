# PostgreSQL ORM planning security contract

Status: **experimental / no live-driver execution evidence**. This document is
a scope and release-gating contract, not certification.

## Trust boundaries

1. `pg.ident` escapes embedded double quotes and rejects empty names (in
   the prerequisite hardening branch), but does **not** validate NUL, control
   characters, PostgreSQL's identifier byte limit, schema-qualified component
   boundaries, or normalization/truncation collisions. Identifier validation
   must occur before any privileged execution. Quoted text is not an
   authorization capability.
2. `pg.column` accepts a small fixed PostgreSQL type list. Legacy `pg.table`
   accepts **raw SQL column and constraint strings** and MUST NOT receive
   user-supplied content. No application should call it from request/tenant
   data. Its presence is a compatibility escape hatch, not a safe API.
3. `pg.table_typed_pk` renders declared `ColumnSpec` data and primary-key
   references through admitted type/identifier formatting, rejecting empty
   names, unknown types, missing keys, nullable primary-key columns and\n   duplicate names/keys. It is a
   restricted DDL builder, **not** general PostgreSQL AST coverage. Even this
   API is not yet approved for untrusted identifiers due to item 1.
4. `Query.sql` and `Query.params` are distinct but `params` is currently a
   mutable actor-local array. No cross-actor sharing, reuse after handoff,
   or assumption of a deep copy is allowed. The driver must implement owned,
   immutable typed bound values and reject stale connection generations.
5. `find_in_workspace(table, workspace, id)` is SQL planning, not tenant
   authentication. A caller-provided workspace string is not authority.
   The execution adapter must bind tenant identity to an authenticated
   capability and configure independent PostgreSQL role/RLS restrictions.
6. No PostgreSQL wire protocol, prepared-statement cache, connection pool,
   transaction/cancellation implementation, row stream, or migrations API is
   implemented here. Never infer those capabilities from generated SQL.

## Release-blocking negative oracles

- Identifier: empty, embedded quote, NUL, C0 controls, multibyte UTF-8 at
  63/64-byte boundaries, qualified names, collisions after truncation,
  reserved words, case sensitivity and Unicode normalization variants.
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
