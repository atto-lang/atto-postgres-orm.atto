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
