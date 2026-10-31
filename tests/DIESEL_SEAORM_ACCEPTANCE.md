# Diesel/SeaORM-inspired Oreslang acceptance matrix

**Pending tests, not executable guest tests today.** This is a test specification to implement as native `.ores` fixtures after the generated schema, codecs and driver exist; no passing status is implied. Do not use host string checks as compiler or PostgreSQL evidence. Reuse `SOURCE_REF`, exact-tree hashes, required JDK25 pin, real CI job steps and independently checked PostgreSQL 17 results from `tests/ACCEPTANCE.md`.

## Static compile-fail suite (Diesel)

| ID | Input | Required compiler behavior |
| --- | --- | --- |
| D-01 | `Column<Docs, Text>.eq(Uuid)` | reject `TypeMismatch`, no implicit conversion |
| D-02 | projection nullable `Option<Uuid>` into nonnullable `Uuid` | reject `NullabilityViolation` |
| D-03 | select `Accounts.email` from `Docs` without declared join | reject `ColumnNotInScope` |
| D-04 | unrelated relation join with incompatible composite-key arity/type | reject `InvalidRelation` |
| D-05 | decode `(id:Uuid, title:Text)` into `(title:Text, id:Uuid)` | reject projection order mismatch |
| D-06 | use `Text` where `Boolean` is expected in filter | reject `NonBooleanPredicate` |
| D-07 | `order_by(request_string)` | reject raw string column authority |
| D-08 | write generated/readonly or tenant ownership column without privileged capability | reject `FieldNotWritable` |
| D-09 | `decode(row)` with unregistered enum variant or wrong PostgreSQL OID | runtime `DecodeError` with bounded field path; never silently coerce |
| D-10 | `select` no deterministic order with offset paging and stable-key requirement | reject or require explicit ordering contract, never nondeterministic page API |
| D-11 | query typed descriptor with stale manifest/schema hash | reject before execution, require migration handshake |
| D-12 | typeclass/macro expansion references unknown private table/column or unconstrained raw SQL | reject during AOT, never runtime fallback |

Compile-fail cases must compile far enough to reach the correct typed checker, and must fail with the expected diagnostic; a missing compiler or unrelated syntax error is **not** a valid negative test.

## ActiveModel/patch tests (SeaORM 2.0)

Given `docs(id:Uuid, workspace_id:Uuid, title:Text NOT NULL, comment:Text NULL)`:

| ID | Patch input | Required result |
| --- | --- | --- |
| S-01 | title `Set("a")`, comment `NotSet` | bind title only; comment absent from SQL assignments |
| S-02 | title `Unchanged("a")`, comment `NotSet` | `NoChanges`, no SQL execution |
| S-03 | comment `Set(None)` | bind typed PostgreSQL NULL; not omit |
| S-04 | title `Set(None)` | reject before SQL: nonnullable type |
| S-05 | insert with required `title=NotSet` without server default | reject `MissingRequired` |
| S-06 | insert with generated key `id=NotSet` and verified server default | omit PK, `RETURNING` typed key |
| S-07 | insert with `Unchanged` field lacking a loaded record | reject invalid state; do not treat as `Set` |
| S-08 | mutate primary key or `workspace_id` in unprivileged patch | reject `FieldNotWritable` |
| S-09 | malicious field name or unknown field in mutation DTO | reject; no raw SQL fallback |
| S-10 | patch `comment=Set(Some("null"))` | send literal text `null`, not SQL NULL |
| S-11 | `Set(new)` equal to prior value | optional explicit `set_if_changed` yields `Unchanged`; ordinary `Set` retains explicit-write semantics |
| S-12 | two concurrent patches against stale row revision | optimistic revision check or explicit locking yields conflict; never silent last-writer-wins when configured |
| S-13 | many nullable values plus an oversized `bytea` | fail bounded resource admission before allocating unbounded buffers |
| S-14 | unknown JSON field, invalid UUID, invalid timestamp | Zorde + codec fail closed with typed, redacted error |

Use positive SQL goldens in `docs/DIESEL_SEAORM_ADOPTION.md`. Test bind values/OIDs as **separate receipts**, not just rendered interpolated SQL.

## Relations and transaction scenarios

| ID | Scenario | Required evidence |
| --- | --- | --- |
| R-01 | fetch 200 docs, each with 3 comments | batch count bounded by configured size; no 201-query N+1 behavior |
| R-02 | one-to-one join where right row is absent | explicit Option relation; no parent loss or malformed model |
| R-03 | composite-key many-to-many relation spanning two workspaces | preserve each tuple key and tenant predicate; no cross-tenant join |
| R-04 | nested write with error in third child | all previously written rows rolled back, no partial committed graph |
| R-05 | cancel nested write after a suspended I/O | rollback completes and pool lease cannot be reused early |
| R-06 | transaction/connection generation retired during await | reject stale continuation and double commit/rollback |
| R-07 | relation graph cycle, unbounded recursive loader or >max fan-out | reject before executing excessive I/O or resource allocations |
| R-08 | tenant A loads relation belonging to tenant B | denied under real PostgreSQL app role with FORCE RLS, including direct SQL bypass attempts |
| R-09 | inherited association with duplicate composite keys | no duplicate rows or suppressed records |
| R-10 | untrusted `ORDER BY`/projection name from request | rejected; not concatenated to SQL |
| R-11 | 63-byte vs 64-byte name; Unicode confusable; NUL | same fail-closed identifier boundary before any driver call |
| R-12 | raw legacy `QueryPlan` or `pg.table` passed to normal repo executor | rejected unless a distinct explicit privileged trusted-SQL capability was granted |

## Migrations and evidence

- Compare schema-first and entity-first manifests: identical canonical table/column/type/constraint graph -> identical checksums, stable across repeated builds.
- Type/default/nullability drift must produce a reviewed migration diff and refuse silent backfill.
- Simulate transactional migration failure: rollback exactly once. Simulate nontransactional DDL interruption: report partial operation and require explicit replay plan.
- Confirm migration lock, checksum/lineage drift, destructive-change approvals, and staging against disposable PostgreSQL.
- Preserve exact branch HEAD, tree, compiler SOURCE_REF, guest executable/artifact hash, SQL+bind receipts, PostgreSQL version, app-role RLS policies, job IDs and actual nonzero job steps.
- A host-only verifier may check fixtures and golden shapes; it **must not** emit `native PASS` or claim driver/tenant proof.

**Release gate:** no merge based on these textual cases alone. Required implementations and real runs must exist at the exact revision; keep draft until then.
