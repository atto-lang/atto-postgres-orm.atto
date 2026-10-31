# Typed PostgreSQL bind boundary and SQL-only security gates (stage 2)

Status: **native Oreslang driver execution is still unverified** until a JDK 25
build of the exact `SOURCE_REF` compiler executes the guest fixtures and a
real Oreslang PostgreSQL adapter performs the same operations over a database
connection.

## Implemented source boundary

- `DbValue(kind, scalar, is_null)` is a data-only metadata carrier. The
  checked factory rejects unsupported type tags and NULL with a nonempty
  scalar payload. Non-NULL empty strings are preserved as legitimate inputs.
- `TypedQueryPlan(sql, values)` copies the caller's parameter array at
  construction, retains its contents privately, and exposes only
  bounds-checked scalar access. Individual `DbValue` instances hold immutable
  fields; the runtime still needs to establish actor isolation.
- `workspace_typed_values_checked(table, values)` checks an ASCII table
  identifier, exactly two values, valid tags, and non-NULL UUID tags before
  creating a fixed parameterized SQL template.
- `find_in_workspace_typed_plan_checked(table, workspace, id)` produces that
  same checked plan from two UUID-tagged scalar values.
- `tests/plans.ores` checks hostile values, immutable plan snapshots,
  absent/extra parameters, invalid tags, null-binds and bounds.

## PostgreSQL 17 SQL-only gates

These tests exercise PostgreSQL itself and deliberately do **not** claim native
Oreslang execution.

- `tests/pg17-prepared-binds.bash` proves fixed prepared templates keep hostile
  text in bind slots and preserve rollback.
- `tests/pg17-bind-failures.bash` covers valid typed coercions plus expected
  SQLSTATE failures for malformed UUID, JSON, bigint overflow, boolean and
  bytea inputs.
- `tests/pg17-rls-contract.bash` creates two non-login tenant roles and
  database-enforced RLS policies. It proves cross-tenant reads are hidden,
  cross-tenant UPDATE/DELETE affect zero rows, cross-tenant INSERT fails with
  SQLSTATE 42501, and a prepared statement reused after `RESET ROLE` observes
  the new role's RLS view rather than stale tenant rows.
- `tests/pg17-cancel-transaction.bash` cancels a live `pg_sleep` inside a
  transaction, requires SQLSTATE 57014, verifies the uncommitted write was
  rolled back, and verifies the database remains usable afterward.

The RLS policy keys authorization to `current_user`, not a caller-settable
custom GUC. This is stronger database evidence, but it still does not prove
that an eventual pool resets roles correctly or that an Oreslang actor owns the
connection capability.

## Critical limitations and refusal rules

The source types are **not** proof of authorization, SQL provenance, valid UUID
syntax, valid JSON/bytea payloads, physical byte-size limits, wire encoding,
connection ownership, transaction safety, or correct Oreslang driver execution.
The public `DbValue` and `TypedQueryPlan` constructors allow arbitrary
objects: a driver must independently validate all tags, query templates,
counts, wire encodings and execution authority before any socket write.

An actor/tenant-bound execution capability is still required. The driver must
also enforce byte-size caps, parameter limits, no text interpolation,
cancellation delivery, lease-generation fencing, rollback on actor abort,
connection reset/destruction on unknown session state, and SQLSTATE
propagation.

## Release verification sequence

1. Compile the exact ORM head and pinned private Java compiler on JDK 25 with
   `scripts/verify-native-plans`; execute all four guest fixtures and retain
   fresh hashes/stdout/stderr/exit codes.
2. Execute all PostgreSQL 17 SQL-only gates above on a disposable database.
3. Implement the live Oreslang adapter and rerun the same bind, cancellation,
   transaction and RLS cases through that adapter.
4. Add actor-confined connection/transaction generation fencing and prove stale
   lease rejection, rollback on actor abort, and pool reset/destroy behavior.
5. Keep native guest, live-driver, Rust receipt, host-mock and SQL-only evidence
   as separate classes. None may be relabeled as another.

Mock verifier, Rust receipt tests and SQL-only PostgreSQL jobs are useful
evidence but never certify native guest or live-driver execution.
