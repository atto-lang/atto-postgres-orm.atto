# Runtime-neutral schema and migration-diff boundary (stage 1)

This adds a **pure Oreslang**, no-driver schema planner. It intentionally does
not execute migrations, read PostgreSQL, emit SQL, or claim live database
conformance. The existing PostgreSQL planner in `src/pg.ores` remains a
separate dialect-specific consumer.

## Authority

The human-authored TypeSpec contract in `contracts/orm-catalog.tsp` and
human-authored JSON Schema Draft 2020-12 contract in
`contracts/orm-catalog.schema.json` are **peers**, following
`ORESoftware/api-docs` and
`ORESoftware/typespec-json-schema-validator`. TypeSpec-generated JSON
Schema is a comparison witness only; never overwrite the JSON Schema source
or choose a source silently. Differences fail the release until reviewed.

The catalog is a language-neutral, versioned **interchange envelope**, not a
table-level user payload validation schema. It is deliberately small: table
stable identities, names, column stable identities, names, logical kinds,
and nullability. Primary keys, foreign keys, indexes, defaults, generated
columns, views, RLS, permissions, and vendor extensions are **not yet
represented**. Absence from the envelope does not mean those DB objects can
be deleted or inferred. Do not use this v1 subset as authority for a full
production database.

## Workflow

1. Independently author TypeSpec and JSON Schema; compare semantic inventory
   and differential validation witnesses using the pinned TJSV tool.
2. Normalize both peers into a pinned catalog and compare all supported
   semantics. No winner-on-mismatch fallback.
3. `introspect` is a future read-only, least-privileged adapter that captures
   a real DB catalog. It must resolve table and column `stable_id` from a
   *reviewed mapping ledger*; names alone do not prove stable identity.
4. `schema.diff_checked(desired, actual)` produces **data-only steps**:
   nullable column additions and nullable relaxations are classified `safe`;
   required additions and `SET NOT NULL` are `preflight`; type changes and
   stable-id renames are `manual`; column removal is `destructive`.
   Even `safe` means reviewable, not auto-applicable.
5. A future DPM-backed dialect adapter must diff **the full normalized DB
   catalog** against the desired catalog, generate an SQL preview and
   migration manifest, demand explicit approval for manual/destructive steps,
   use a migration-only credential, advisory locks, checksums and drift checks,
   and verify post-apply catalog readback.
6. Check generated SQL into the repository; apply only reviewed, immutable,
   checksum-locked migrations in deployments. Runtime ORM actors never have
   DDL privileges.

Recommended CLI semantics once implemented:

```text
ores orm schema check                 # both source authorities converge
ores orm db pull --read-only          # introspection to reviewable catalog
ores orm migrate diff --from-db       # proposed SQL and risk report, no apply
ores orm migrate generate             # diff against previous pinned snapshot
ores orm migrate check                # drift / checksum / policy gate
ores orm migrate apply --approved     # separate migrator role, locked + audited
```

For now, the only implemented native operations are
`schema.table_checked`, `schema.diff_checked`, and their typed immutable
snapshots. Run with the exact pinned compiler:

```sh
ORESLANG_SOURCE_DIR=../oreslang-source.java ./scripts/ores tests/schema-plans.ores
```

The pinned JDK 25 compiler and native driver must execute before claiming
native or database evidence. A JSON Schema check alone is not an Oreslang
compiler test.

## Why diff both history and DB?

Use (desired contract versus last accepted snapshot) to create reproducible,
versioned migrations without credentials, then compare desired/expected
against an introspected live catalog for drift. Direct DB-versus-desired
diffs are useful for previews, baselines and repairs, but must not erase
unmodeled objects, mistake a rename for drop+add, or auto-write production.
Never reset a DB or auto-drop out-of-scope objects.

## Backend portability

The Oreslang actor runtime shares a structural IR and typed query behavior
across Java/GraalVM, LLVM, WASM, Forge and .NET. Dialect-specific capabilities
map logical kinds (`string` -> PostgreSQL `text`, `json` -> `jsonb`, etc.),
DML, placeholders, and DDL separately. PostgreSQL's 63-byte identifier cap
is used as an intentionally narrow v1 *portable profile*. This is not proof
of support for all SQL dialects or of backend parity.

Release blocks: canonical source parity, stable-id ledger and ambiguity
handling, full-catalog coverage, live PostgreSQL 17 introspection/diff/apply
(including RLS, locks and rollback), prepared driver binds, actor leases and
transaction lifecycle, and exact-head native Oreslang CI on JDK 25.


## Pure Oreslang AOT source previews (stage 2, NOT certified)

The existing stable-ID schema module now exposes
\`schema.table_descriptor_source_preview_checked\` and
\`schema.model_source_preview_checked\`. They operate entirely in Oreslang,
have no I/O or SQL execution, and revalidate publicly constructed schema
tables. Source preview is deterministic for the same ordered validated input;
it never asserts accepted TypeSpec/JSON parity or produces a publishable
compiled artifact.

The descriptor preview preserves *all* eight logical kind tags, stable IDs,
physical names and nullability without rewriting a schema to SQL. A
separate deliberately narrow nominal model preview supports **only**
nonnullable \`string\` and \`boolean\` fields, yielding an Oreslang class with
explicit \`pub val\` fields and a constructor. For example, a stable-id
\`labels\` table becomes \`orm_labels\` with members \`field_label\` and
\`field_enabled\`. Prefixing stable IDs distinguishes generated source names
from reserved language tokens and avoids silently using mutable physical
database names. Added prefixes are checked against the portable 63-byte
limit; no truncation, collisions or silent renaming.

Nullable/Option, UUID, integer-width, JSON, bytes and timestamp mappings
are **fail-closed until their nominal Oreslang types and wire codecs exist**.
In particular, UUID is never silently cast to \`string\`, and NULL is not
silently converted to an omittable value. A production compiler integration
must consume *admitted, exact-digest Contract IR* plus a reviewed DPM catalog,
materialize generated files atomically, and independently compile them.
No runtime ORM or user-supplied string can bless a source preview.

\`tests/schema-plans.ores\` adds positive exact-source determinism and
negative tests for wrong type mapping, nullable loss, prefix-length
overflow, and forged public table objects. These are authored guest
assertions until a pinned Oreslang compiler runs them.


## Whole-catalog stable-ID reconciliation (stage 3; guest not executed)

\`SchemaCatalog\` holds an array-copied snapshot of up to 256 validated
tables (the peer Catalog TypeSpec/JSON Schema maximum). The pure
\`schema.catalog_checked\` rejects duplicate stable IDs, duplicate physical
table names and malformed directly-constructed tables.
\`schema.diff_catalog_checked\` preserves ordered per-table diffs and
classifies new tables as \`review_create_table/manual\`, removed tables as
\`review_drop_table/destructive\`, and same-physical-name/different-stable-ID
as an error. A matching stable ID with a changed physical name still yields
a manual rename-review step, never an inferred migration.

This is deliberately a subset of the full DPM catalog: constraints, RLS,
grants and indexes do not disappear merely because the portable projection
cannot represent them. Both planners emit proposals only. Tests for
duplicate/colliding table IDs, create/drop, forged public catalogs and
array-copy isolation are authored in \`tests/schema-plans.ores\`; they still
require a real Oreslang guest run.


## Versioned, review-only migration handoff preview (stage 4)

\`schema.review_manifest_preview_checked\` emits bounded, stable-ID JSON
**data**, not SQL. Public \`SchemaStep\` constructors are revalidated
against an exact operation→risk allowlist; table-only operations must have
no column ID; all IDs must satisfy the conservative ASCII identifier
policy. The output always includes
\`"status":"STOPPED_FOR_EVALUATION"\`, \`"approved":false\` and
\`"scope":"column_shapes_only"\`. The source text cannot be made an
authorization token merely by receiving a \`safe\` operation.

\`contracts/orm-plan-preview.schema.json\` is a closed Draft 2020-12
structural schema for this review envelope and prohibits risk downgrades
and unreviewed SQL. Its matching example and negative mutation tests
are host-only; \`tests/schema-plans.ores\` includes exact output and
adversarial guest checks. **Not a DPM migration plan**: DPM must bind
approved peer-authority digests, complete desired/observed catalog
identities, independent SQL candidates, engine/extension/version pins,
execution lease, operator authorization and post-apply read-back before
any actual migration is planned or applied.


## Three-way snapshot drift gate (stage 5, non-executable)

`schema.plan_from_snapshot_checked(desired, accepted, observed)` first
compares the **accepted catalog snapshot** with the **observed catalog
projection**. On any modeled change (column/type/nullability, table identity
or physical-name drift, added or removed table) it returns an error and does
not create a desired-state plan. If they match, it produces the same scoped
review plan as `schema.diff_catalog_checked(desired, accepted)`.
Column enumeration order is not a v1 semantic difference.

This gate does **NOT** introspect PostgreSQL, check metadata beyond the v1
shape envelope, compare SQL, verify RLS/grants/indexes, or authorize a
migration. A real application must not treat a no-drift result here as
full-database equivalence or readiness to apply. The complete, independently
validated DPM catalog and its locks, roles, approvals and readback remain
separate mandatory gates.

Publicly constructed review plans now reject duplicate operation/table/column
triples. The closed JSON Schema preview also rejects exact duplicate step
objects. Distinct legitimate operations on one stable column remain allowed.
Both layers always preserve `approved: false` and
`STOPPED_FOR_EVALUATION`.

The new Oreslang guest fixture covers baseline freshness, observed-only
tables, type/name changes, stable-ID collisions, forged public objects,
harmless column reorder, and repeated destructive steps. Additional
host-only tests cover complete op-to-risk mapping, scoped column IDs, schema
bounds and non-authorizing review envelopes. The host-only tests are **not**
evidence of native Oreslang execution.


## Metamorphic schema-ORM regression extension (stage 6; native not run)

The existing native `tests/schema-adversarial.ores` fixture now checks repeat
planning byte stability, idempotent empty catalogs, harmless multi-table order
changes, independent type/nullability changes in both directions, stable-ID
name takeovers, physical name reuse across different stable identities,
duplicate destructive table reviews, and permanently denied review status
for all-safe proposals. The exact-head harness already requires this fixture.

Host-only JSON Schema regression tests additionally exercise the 63-byte
ASCII identifier admission boundary, complete eight-kind whitelist, rejected
SQL/database type strings, and every operation's inability to add SQL,
approval flags, or expanded scope. These are validator/source-level checks,
not PostgreSQL, TypeSpec or native Oreslang execution evidence.


## Host admission oracle mutation cases (stage 7, awaiting runner)

The exact-head mock harness now authors 17 distinct cases including five
new failure injections for valid-looking but untrustworthy guest stdout,
nonzero positive exits, reserved launcher exit 69, false-success negative
exits and surplus negative stdout. These are deliberately **fake compiler
oracles** and can only validate harness fail-closed wiring once executed.
No mock pass counts as native Oreslang execution. The seventh guest includes
independent three-way migration snapshot assertions; the suite remains
blocked until a private-source-authorized JDK 25 runner executes the pinned
compiler and all seven required guest oracles.
