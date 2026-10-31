# Typed PostgreSQL bind boundary (stage 1)

Status: **source and native guest fixtures only** until a JDK 25 build of
the exact `SOURCE_REF` compiler executes `tests/plans.ores`.

## Implemented

- `DbValue(kind, scalar, is_null)` is a data-only metadata carrier. The
  checked factory rejects unsupported type tags and NULL with a nonempty
  scalar payload. Non-NULL empty strings are preserved as legitimate inputs.
- `TypedQueryPlan(sql, values)` copies the caller's parameter array at
  construction, retains its contents privately, and exposes only
  bounds-checked scalar access. Individual `DbValue` instances hold
  immutable fields; the runtime still needs to establish actor isolation.
- `workspace_typed_values_checked(table, values)` checks an ASCII
  table identifier, **exactly two** values, valid tags, and non-NULL UUID
  tags before creating a fixed, parameterized SQL template.
- `find_in_workspace_typed_plan_checked(table, workspace, id)` produces
  that same checked plan from two UUID-tagged scalar values.
- `tests/plans.ores` now checks hostile values, immutable plan snapshots,
  absent/extra parameters, invalid tags, null-binds and bounds.

## Critical limitations and refusal rules

The types are **not** proof of authorization, SQL provenance, valid UUID
syntax, valid JSON/bytea payloads, physical byte-size limits, wire encoding,
connection ownership, transaction safety, or correct PostgreSQL execution.
The public `DbValue` and `TypedQueryPlan` constructors allow arbitrary
objects: an eventual driver **must** independently validate all tags, query
templates, counts, wire encodings and execution authority before any socket
write. In particular, it must never treat a caller-supplied workspace UUID
as a tenant credential. This project still has no live PostgreSQL driver.

An actor/tenant-bound execution capability must be required before executing
this plan, and the database must independently enforce role/RLS isolation.
The driver must also enforce byte-size caps, parameter limits, no-text-interpolation,
cancellation, lease-generation fencing and SQLSTATE propagation.

## Executable verification gates

1. Exact ORM head and `SOURCE_REF` compile on JDK 25 with the native
   verifier `scripts/verify-native-plans`.
2. Four guest fixtures (positive and three negatives) actually execute,
   with fresh hashes, stdout/stderr, exit codes and `VERIFIED` result.
3. Actual PostgreSQL 17 parameter-binding integration uses prepared
   statements, hostile text and invalid UUID/JSON input; no ORM guest
   execution is inferred from SQL-only `psql` tests.
4. Actor confinement, rollback/cancel, RLS and backend parity tests execute.

Mock verifier, Rust receipt tests and SQL-only PostgreSQL jobs are valuable
but each has a **separate evidence classification** and never certifies
native guest execution.
