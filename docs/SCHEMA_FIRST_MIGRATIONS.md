# Schema-first pure Oreslang ORM and declarative migrations

**Status:** A narrow pure-Oreslang, non-executing column-shape diff is authored,
but **native compiler execution, TypeSpec/JSON parity, DPM application, and
database catalog convergence are NOT VERIFIED**.

## One accepted schema, two independently authored authorities

- [oresoftware/api-docs](https://github.com/oresoftware/api-docs) specifies
  TypeSpec and JSON Schema/OpenAPI as **peer, human-authored** authorities.
  Neither wins automatically; discrepancies halt for evaluation.
- [typespec-json-schema-validator](https://github.com/oresoftware/typespec-json-schema-validator)
  can publish downstream Contract IR only with full pinned TypeSpec compiler,
  exact input digests, declaration inventory, generated witness comparison,
  differential instance validation and zero unexplained discrepancies.
  `contracts/peer-authority.v1.json` explicitly records **not_executed**.
- [declarative-migrations](https://github.com/declarative-migrations/declarative-postgres-migrate.rs)
  (DPM) is the **only** planner and applier of live SQL migrations. The ORM
  never synchronizes tables during startup or uses a DDL role.

```text
authored TypeSpec --------------------\
                                      > parity receipt -> derived Contract IR
authored JSON Schema + OpenAPI -------/          |
                                        + reviewed storage overlay
                                                 |
                                       AOT nominal .ores models
                                                 |
observed database -> DPM full catalog introspect |
          |                                      |
          +---- compare with BOTH independently produced, equal SQL catalogs
                      |
                 DPM reviewable migration files
                      |
          shadow apply -> re-introspect -> equivalence proof
                      |
          approved DPM migrator lease, fresh catalog read-back, apply
```

The two authored examples are `contracts/typespec/document.tsp` and
`contracts/json-schema/document-row.schema.json`. They are **not certified
equivalent** by the TypeSpec compiler yet. Any TypeSpec-emitted JSON Schema
is a *diagnostic witness*, never the independently authored peer source.
`contracts/storage/document.storage.v1.json` is the separately reviewed,
non-executable database overlay. It records composite PK and tenant key;
indexes, FK, policy bodies, grants and extensions remain pending design.

**Required on a JSON row is not the same as SQL NOT NULL.**
The `DocumentRow.note` key is present in read models and may be JSON null;
the database `note` column is nullable. An INSERT field may be omittable
or defaulted separately. Runtime JSON payload validation is not a complete
SQL catalog or tenant-authorization contract.

## Pure Oreslang implementation

`src/orm_schema.ores` contains only guest source:
`OrmColumn`, `OrmTable`, `OrmCatalog`, `OrmSchemaChange`,
`OrmSchemaProposal` and `orm_schema.diff_checked`.

- Data-only, no reflection, host calls, I/O, SQL strings or migration execution.
- Copies array inputs, revalidates public descriptors and bounds catalogs to
  32 tables with 64 fields/table; conservative ASCII identifiers.
- Uses neutral logical families `uuid/string/boolean/int32/int64/json/timestamp/bytes`;
  exact DB type widths/precision/collation are separate reviewed mappings.
- Proposes adding a table or a nullable field only for *review*.
- Blocks added required fields (backfill), type/nullability changes, and
  removed columns/tables (rename versus destructive drop ambiguous).
- Equal columns produce `column_shapes_equal_only`, **not full DB parity**.
  Default expressions, checks, keys, indexes, policies, privileges, extensions,
  generated columns, triggers and other DB objects are outside this slice.

Native guest assertions are authored in `tests/schema_diff.ores` and must
execute using the exact pinned Oreslang compiler to become evidence.
Host-only `tests/verify-schema-authority-host.mjs` checks authored examples
and unsafe mutations; it does NOT run the TypeSpec compiler, JSON Schema's
entire vocabulary, Oreslang source, or DPM.

## Database-first and migration generation

**Yes, generate migration files from a DB diff—but not by blindly taking the
database as intended truth.** Read and normalize the observed database
catalog with DPM; construct the desired catalog from two *converged*
independently generated SQL candidates plus reviewed database overlays;
compare and generate a versioned, reviewable DPM plan. A brownfield baseline
is special: capture live engine version, extensions, policies, grants,
constraints and native schema-only DDL; author both authorities independently
and converge before emitting any change.

For a new migration, require checksums over both authority trees, generators,
approved Contract IR, overlays, current/desired catalogs, SQL candidates,
and DPM plan. Keep rename/drop decisions explicit; never infer rename from
one missing and one new field. Backfills, NOT NULL, unique constraints and
casts require a rehearsed data migration plan. Rehearse in disposable DBs;
re-introspect and require zero unexpected drift; check tenant RLS with
least-privilege application roles. After DPM acquires a migration lease,
re-read the live catalog and abort if the reviewed baseline changed.

Do NOT run an ORM `push`/automatic `synchronize` command in production.
Runtime Oreslang actors receive separate read/write credentials with no DDL
capabilities. Any future migration emitter belongs to DPM, not the ORM.

## Release gate matrix

| Gate | Current proof |
| --- | --- |
| Pure Oreslang column-diff source + guest fixtures | Authored, **not compiled** |
| Independently authored TypeSpec + JSON Schema examples | Authored, **not compiler-parity-certified** |
| Storage overlay, PK + tenant column | Draft review intent only |
| Host-only structural/adversarial example checks | Only after executable CI result |
| Two SQL-candidate generators and exact catalog parity | Not materialized |
| DPM live introspection / migration file generation / shadow apply | Not executed |
| Native async PostgreSQL actor/codec/RLS | Not implemented |
