# postgres-orm.ores

Native Oreslang foundation for a PostgreSQL ORM: code-first DDL composition,
quoted identifiers, admitted column types, and workspace-scoped parameterized
query plans. **This first revision does not open database connections or execute
queries.** A native DB capability/driver remains required.

```ores
import module pg from './src/pg';
val sql = pg.table("workflows", arr[
  pg.column("workspace_id", "uuid", false).unwrap(),
  pg.column("id", "uuid", false).unwrap(),
  pg.column("name", "text", false).unwrap()
], arr["PRIMARY KEY (workspace_id, id)"]);
val query = pg.find_in_workspace("workflows", workspace_id, workflow_id);
// Adapter executes query.sql and binds query.params separately.
```

## Typed DDL path (draft; compiler execution pending)

For tables with a primary key, prefer `table_typed_pk` over raw column and
constraint fragments. `column_spec` carries names/types/nullability as data;
the builder checks the type allowlist, nonempty column/table/key names, duplicate
columns and primary-key entries, nullable primary-key columns, and primary-key\nreferences to declared columns.
It returns `Result<string,string>` rather than silently accepting those errors.

```ores
val ddl = pg.table_typed_pk("workflows", arr[
  pg.column_spec("workspace_id", "uuid", false),
  pg.column_spec("id", "uuid", false),
  pg.column_spec("payload", "jsonb", true)
], arr["workspace_id", "id"]);
```

This **does not** establish safe database execution. PostgreSQL identifier
admission (NUL, control characters, UTF-8 byte-length limits), other DDL
constraints, tenant capabilities, connection driver, transactions, RLS and live
PostgreSQL tests remain release blockers. Callers must not feed untrusted
identifiers or mutable query plans to an execution adapter.

The legacy `table(name, columns, trusted_constraints)` method is retained only
for source-authored trusted fragments and backward compatibility. It is unsafe
for inputs influenced by a tenant or request, even when identifiers are quoted.
There is no implicit migration from that API to the typed builder.

Constraint strings and pre-rendered column strings are explicitly **trusted, source-authored SQL**. They must never receive user input or be treated as a SQL-injection security boundary. Identifiers are quoted (including embedded quotes), and empty identifiers are now rejected; types are admitted from a closed list. The driver/admission layer must additionally reject NUL/control characters, enforce PostgreSQL's 63-byte identifier limit, and reject unsafe or ambiguous qualified identifiers before executing DDL. That stronger identifier policy is **not implemented by this planner** and remains a release blocker.
Query values never become SQL text. UUID parameters are cast by PostgreSQL rather
than interpolated. `Query.params` is an actor-local array; do not share mutable
plans across execution domains.

The workflow application is the first consumer and owns a compiled Oreslang model,
real PostgreSQL invariant tests, and checksum/advisory-lock migration tooling:
[oreslang-n8n-make-zapier-app](https://github.com/ores-truffle-oreslang/oreslang-n8n-make-zapier-app).

Run the native contracts with JDK 25 and the clean compiler commit in `SOURCE_REF`:

```sh
ORESLANG_SOURCE_DIR=../oreslang-source.java ./scripts/ores tests/plans.ores
```

The compiler must first be built with Maven, including a `target/classpath.txt`:
`mvn -q -DskipTests package dependency:build-classpath -Dmdep.outputFile=target/classpath.txt`.
The launcher verifies the revision and rejects tracked compiler modifications.

Next: typed DbValue/DbRow and error surfaces, actor-confined prepared statements,
transactions and cancellation, bounded row streams, pool ownership, generated
row codecs, and live PostgreSQL driver conformance. No unsupported driver is
presented as implemented.
