# PostgreSQL ORM hardening contract (design, not runtime certification)

Status: architecture and acceptance criteria, aligned with draft PR #4 and #6. The current src/pg.ores is a synchronous SQL planner; it does not connect to PostgreSQL, execute queries, validate tenant membership, generate compiled models, or prove multi-backend parity. None of these pending features should be described as shipped.

## Reference ideas and Oreslang decisions

| Project | Feature to learn | Oreslang translation |
| --- | --- | --- |
| Zod | schema parse/safeParse, paths and refinements | bounded Result<Validated<T>, ValidationIssues> with a structured issue path/code; no unbounded error collection, no implicit coercion |
| Zorde | Oreslang runtime refinements / annotations | use a single native validation contract for ingress, model assignment and database row decode; audit actual Zorde APIs before writing an adapter |
| Serde | derives, serialization traits and data-model separation | hygienic AOT-generated EncodePg<T>/DecodePg<T> typeclasses; no reflection, stringly shape guessing, or generic JSON for every column |
| Drizzle | SQL-first compositional expressions | typed column references, explicit joins, predicates, ordering, parameters and inspectable canonical SQL AST |
| Prisma | schema contract, typed queries and migrations | deterministic schema snapshot + generated query model, migration diff / drift detection / dry-run and destructive-change review |
| TypeORM | repositories, relations, unit-of-work/transactions | typed repository facade; explicit async calls, explicit relation load policies, no hidden network I/O or implicit lazy proxy |

## Boundaries: what may cross each interface

1. **Input -> validation.** Parse external inputs as untrusted. Differentiate missing fields, explicit PostgreSQL NULL, and present values: do not silently coerce strings to UUID/int/timestamp. Reject unknown fields by default for mutation DTOs. Zorde refinements run before storage and after row decode. Bound input bytes, recursion depth, collection lengths, and validation issue counts.
2. **Validated model -> typed query AST.** Schema-qualified identifiers and columns are values from a compiled, verified schema registry, not request strings. The existing admitted_identifier helper remains a narrow ASCII-only planner boundary, *not* table authority. Never concatenate values, WHERE fragments, ORDER BY strings, JSON paths or user-supplied type names into SQL.
3. **Typed AST -> driver binds.** Compile to canonical SQL + ordered *typed* DbValue sequence (UUID, text, integer, bigint, boolean, jsonb, timestamptz, bytea, numeric exact decimal, Option<DbValue>). Keep value/code paths separated. All identifiers must come from admitted schema objects; value placeholders must have a stable type/OID. No implicit conversions and no raw string-fragment escape hatch in ordinary repositories.
4. **Driver -> row decode.** Explicit type/OID and nullability verification; bound row/field sizes and streaming windows; decode into Result<Model, DecodeError>. Unknown enum variants, overflow, invalid UTF-8, malformed JSONB and invalid timestamps fail closed. AOT-generated codecs must be deterministic across Java/GraalVM, LLVM, .NET, WASM and Forge.
5. **Legacy escape hatches.** pg.table takes raw column/constraint strings; snapshot_legacy_query copies parameters but does not sanitize SQL. Mark both trusted-only/deprecated for ordinary application code. Do not let a driver treat a legacy QueryPlan as safe or executable solely due to a parameter snapshot.

## Runtime model and security invariants

- **Async-only I/O:** open/prepare/execute/stream/commit/rollback are async Oreslang APIs with cancellation and bounded backpressure. No hidden blocking I/O, reflection, Java/JS ORM runtime or implicit network fetch on a property getter.
- **Actor ownership:** DbConnection and Transaction handles are actor-confined, generation-fenced capabilities. Sendable data must be an immutable verified snapshot or an explicitly transferred owned value, never a shared mutable Array. Isolation is enforced by scheduler/heap semantics and driver lease receipts, not merely a string tenant field.
- **Tenant authority:** the authenticated tenant/workspace capability is not a caller-supplied workspace string. Enforce database role privileges and PostgreSQL row-level security; verify owner/BYPASSRLS exceptions and FORCE ROW LEVEL SECURITY where appropriate. Apply tenant context only in the same transaction/connection (e.g. transaction-scoped settings) and reset/revoke on close. Run cross-tenant negative tests under the real application role.
- **Transaction machine:** New -> Active -> CommitPending/RollbackPending -> Closed; a fenced lease cannot be reused after completion, timeout, cancellation or pool retirement. Roll back on task cancellation and ensure exactly-once terminal receipt; no cross-actor reentrancy across suspension.
- **Resource admission:** cap identifier input bytes before expensive normalization/replacement, bound parameter count/bytes, prepared statement cache, query depth, join count, result rows, streaming buffers, connection queues and deadline budgets. Use least-privilege roles, authenticated TLS and safe redacted error telemetry.
- **Migration safety:** stable ordered schema snapshot and checksum; advisory migration lock; explicit preconditions, drift checks, transactional rollback where supported, resumable/verified phases for nontransactional DDL, no automatic destructive changes. Maintain a human-readable SQL preview and audit log.
- **Model API:** type-checked primary/composite keys, constraints, indexes and relations; explicit insert/update/delete projections and RETURNING. No surprise auto-flush, cascade delete or lazy I/O. Pagination must use a deterministic ORDER BY/tiebreaker and tenant filter.

## P0 / P1 acceptance gates

| Priority | Requirement | Required executable evidence |
| --- | --- | --- |
| P0 | ASCII-only 1..63-byte typed identifiers and no delimiter-sentinel loophole | genuine tests/plans.ores guest execution including Unicode/confusables, 63/64 boundary and typed FK/column/query paths |
| P0 | Driver-side typed bind/row codec boundary | native guest + disposable PostgreSQL: injections in VALUES/ORDER fields, invalid UUID, nullability, numeric overflow, bytea/jsonb round-trip |
| P0 | Tenant authority, RLS and transaction fencing | two tenants, app role without bypass, forced RLS, aborted tx/cancellation, stale generation and pool reuse attempts |
| P0 | Source/proof integrity | exact ORM head/tree plus pinned compiler SOURCE_REF and compiled artifact hashes; nonzero executed workflow steps; no zero-step pass claims |
| P1 | AOT Zorde/Serde codec adapter | compile-time invalid model tests; bounded structured issues and strict decode of rows on every backend |
| P1 | Query builder and migrations | SQL golden/property tests, joins/relations, drift/destructive-change dry-runs and PostgreSQL rollback |
| P1 | Availability and operability | bounded streaming, deadlines, cancellation under load, redaction and no actor cross-heap aliasing |

## Near-term implementation order

First close the identifier residual/sentinel check and preserve the existing stacked draft APIs; next add a closed PgType/DbValue algebra, schema-owned identifiers, codec Result errors, and driver capability model. Wire a real native PostgreSQL client only after ownership/transaction semantics are executable. Once those exist, implement generated model/repository surfaces, relational predicates, and safe migrations. Keep runtime and release claims false until tests execute against an actual PostgreSQL instance.

References: https://zod.dev/basics ; https://serde.rs/data-model.html ; https://typeorm.io/docs/getting-started/ ; https://www.prisma.io/docs/orm ; https://orm.drizzle.team/docs/data-querying ; https://www.postgresql.org/docs/17/ddl-rowsecurity.html . Zorde's exact project API must be checked in its source rather than guessed.
