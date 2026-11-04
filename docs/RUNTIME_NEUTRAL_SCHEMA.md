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

## Cross-item contradiction gate (stage 6, review-only)

The pure Oreslang review manifest now refuses conflicting public
`SchemaStep` combinations: a table creation/deletion cannot coexist with
other steps for that table, a column add/drop cannot coexist with operations
for that same stable column, and opposite nullability edits cannot coexist.
Distinct table-renames, column-renames, type changes, and a single nullability
change remain reviewable together. Validation is independent of step order.

JSON Schema Draft 2020-12 `uniqueItems` only catches identical objects; it
does **not** encode key uniqueness or incompatible combinations across an
array. Host-only semantic checks exercise these extra invariants separately.
Neither the host validator nor the review preview is trusted migration
authority. Full DPM catalog verification, peer TypeSpec semantic parity,
native Oreslang compilation, and real PostgreSQL 17 tests remain blocked
release gates.

## Deterministic independent review-operation matrix (stage 7; host-only)

`tests/test_orm_pairwise_matrix_host.py` exercises a separately authored
operation-pair oracle over **all 100 ordered pairs** of the ten allowed v1
operations across three scopes: same stable table and column, different
stable tables, and distinct stable columns on one table (300 pair scenarios).
It also permutes a legitimate five-operation review bundle across 80 fixed
random seeds, verifies conflicts separated by dozens of unrelated steps,
and detects duplicated operations separated by 150 other-table entries.
These are host-only semantic tests, **not native Oreslang execution**.

`scripts/orm_semantics_host.py` deliberately accepts shape-invalid
inputs when invoked without JSON Schema validation. It is only a
cross-item checker: callers must FIRST validate the closed v1 schema,
including `approved=false`, operation-risk pairs and field bounds, then
invoke the semantic checks. Neither successful host check creates a
migration authorization or a database catalog attestation.

The host workflow now requires at least 30 schema-contract, 8 semantic,
and 10 independent matrix test methods. Missing/zero-discovered tests
must not report a green host receipt. This suite cannot substitute for
pinned native guest execution, TypeSpec emitter parity, a reviewed
stable-ID mapping ledger, full PostgreSQL catalog introspection or DPM
migration replay/rollback/locking evidence.

## Strict UTF-8 review-only JSON admission (stage 8; host-only)

The new scripts/orm_admission_host.py is a **host-only**, read-only
boundary for imported catalog and review JSON. Its fail-closed checks are:

1. Accept exact UTF-8 bytes bounded at 8 MiB. Reject malformed JSON,
   non-finite numeric constants, nested duplicate JSON keys (including
   Unicode-escaped aliases), and excessive parser nesting.
2. Validate the closed JSON Schema Draft 2020-12 envelope selected by a
   fixed kind (catalog or review).
3. Verify stable-ID and physical-name uniqueness and cross-step
   contradictions via scripts/orm_semantics_host.py.

Review-only examples (no database access or SQL):

    python scripts/orm_admission_host.py --kind catalog --input contracts/examples/current.catalog.json
    python scripts/orm_admission_host.py --kind review --input contracts/examples/plan-preview.json

The CLI exits 0 only on admitted review data and 2 on an invalid payload
or input-file I/O failure. A zero exit or ORM_HOST_REVIEW_ONLY_OK marker
**never authorizes SQL generation, approval or migration execution.**
This script contains no DB connection, DDL capability or SQL emitter.

### Portable identifier boundary correction

The original identifier ^...$ regex can match before a terminal newline,
which the pure-Oreslang admitted_name implementation rejects. The JSON
Schema catalog/preview and TypeSpec peer patterns now use an explicit
end-of-input negative lookahead, rather than relying on the $ anchor;
the optional empty column ID is also strictly anchored.

Tests reject suffixes LF, CR, U+2028 and U+2029 for catalog table and
column IDs/names and for review-step table/column IDs. This is a
peer-contract modification: TypeSpec compiler/emitter equivalence remains
a separate mandatory unverified gate.

The 23 new admission-test methods cover CLI positive/negative behavior,
duplicate keys, huge/deep inputs, review contradictions, forged approvals
and portable identifier regressions. The host CI workflow now requires
at least 71 discovered host test methods across four suites and exercises
the checked-in catalog/preview JSON files through the CLI.

None of these host results establishes pinned native Oreslang guest
execution, TypeSpec/TJSV parity, PostgreSQL 17 introspection or DPM
migration replay/rollback/locking. Do not transfer private source to
an alternate organization while the existing incident hold applies.
Keep changes in draft pending native and database execution evidence.


## Offline PostgreSQL 17 catalog projection and stable-ID ledger (stage 9)

The HOST-ONLY `scripts/orm_pg_catalog_projection_host.py` converts an
illustrative PostgreSQL-17-flavored capture plus an explicitly supplied
stable-ID ledger into the existing runtime-neutral **column-shapes-only**
catalog. It performs **no database I/O, read-only query, or SQL execution**.

The checked-in sample inputs are
`contracts/examples/pg17-capture.offline.json` and
`contracts/examples/pg17-ledger.offline.json`. They are invented fixtures,
NOT evidence of a real PostgreSQL database or a reviewed production ledger.

Fail-closed checks require PostgreSQL 17 version pinning, identical cluster
system identifier and database OID, exact one-to-one table OID and column
attnum mappings, no duplicates, an admitted public-schema ordinary table
and conservative physical identifier/type admission. A changed physical name
retains its existing stable ID **only when the same reviewed scoped OID/attnum
mapping is present**; names alone never infer identities.

No reported RLS, policies, indexes, constraints, defaults, generated columns,
identity columns, dropped columns, views, non-public schemas, partitioned
tables or other out-of-scope features are silently erased. These require
a full-catalog reconciliation and are rejected by the v1 projection.
The final normalized result is validated through the existing STRICT host
JSON Schema + cross-item admission boundary and deterministically sorted.

**Important limits:** Both input objects are untrusted. An empty reported
out-of-scope inventory CANNOT prove it is complete or independently captured.
PostgreSQL OIDs/attnums and a cluster identifier are scoped to one database
instance and may not survive dump/restore. The fixture does not attest a
real catalog, discover constraints/RLS or establish full-database parity.
No application actor receives DDL permissions and no migration manifest can
authorize SQL execution.

`tests/test_pg_catalog_projection_host.py` adds 27 host-only test methods,
covering the checked-in fixture, stale/duplicate OID and attnum ledgers,
non-ASCII names, source immutability, deterministic order, unsupported
types, RLS, defaults and other out-of-scope objects. Source CI must now
discover and execute at least 98 host methods in five suites; the actual
runner must execute steps before any PASS claim. Native Oreslang, TypeSpec
emission, PostgreSQL read-only extraction, DPM replay, actor/RLS lifecycle,
locking, rollback and backend parity all remain separate release gates.
