# Checked multi-field UPDATE and projection planner

This module is **a data-only SQL planning slice**, not a database driver,
tenant capability, generated Diesel-like type-level schema, migration engine
or SeaORM-style executable ActiveModel. Backend-specific compiler results,
PostgreSQL integration and transaction/RLS authorization remain unverified.

## Implemented in `src/pg.ores`

`PgFieldPatch(name,change)` represents one field from an already validated
`PgTableDescriptor`. For convenience, call `pg.field_patch`. The new
`pg.plan_schema_update_fields_checked(descriptor, patches, workspace, id)`
validates each patch's identifier, uniqueness, declaration, immutability,
change state and codec. It handles up to 8 entries, including those not
resulting in a database write. It returns `Result<TypedPatchPlan,string>`.

For `Set` fields, SQL assignment placeholders appear in patch order.
`NotSet` / `Unchanged` are skipped, and an all-skipped patch has
`is_noop=true`, empty SQL, and zero binds. Workspace and record UUIDs are
always the final two placeholders, ensuring source values never become SQL.
`Set` with typed NULL is legal only for nullable columns; NULL and
omission are not conflated. Duplicate edits fail, even if one is skipped.

`pg.plan_schema_select_columns_checked` renders an explicit projection of
1–16 distinct, declared identifiers: `SELECT "id", "title" FROM "docs"
WHERE workspace_id = $1::uuid AND id = $2::uuid`. It uses a
`TypedSelectPlan`, not a mutation plan. No wildcard or raw expression is
accepted, and its two typed UUID binds are copied at construction.

## Trust boundaries and explicit omissions

- `PgTableDescriptor` is caller-constructible; its contents are
  revalidated, but it is **not** an AOT nominal/authority-bearing schema
  token, nor proof of the database catalog's live schema.
- UUID lexical checks are not authenticated tenant credentials; actual
  PostgreSQL application-role RLS/tenant checks remain mandatory.
- `DbValue` has a type tag and explicit `is_null`, **not** a PostgreSQL
  wire representation or checked OID. The only active codec tags are text,
  UUID, boolean. SQL parameter types are not validated against a server.
- Arrays are copied into plan objects and accessed via checked methods;
  no inter-actor `Sendable` or isolate ownership guarantee is established.
- String and array admission must also be byte-bounded at the actual
  network/driver boundary before expensive operations.
- No hidden I/O, reflection, implicit conversions, operator overloading,
  migration application, nested writes, transaction/pool lease or retries.

## Next release gates

1. Execute `tests/plans.ores` and all negative fixtures with pinned clean
   Oreslang compiler SHA/JDK25, real job steps and exact-head tree receipts.
2. Replace remaining caller-constructible descriptors with AOT-generated
   nominal schema tokens and compile-fail typeclass assertions.
3. Add true numeric/jsonb/timestamptz/bytea codecs and OID/nullability tests.
4. Implement async actor-owned PostgreSQL driver and transaction fencing,
   then run two-tenant RLS and cancellation/rollback tests against PostgreSQL.
5. Add relation JOIN/batch planners only after bounded fan-out and explicit
   tenant conditions are proven; never introduce implicit lazy I/O.

The new SQL goldens and adversarial guest cases live in `tests/plans.ores`.
