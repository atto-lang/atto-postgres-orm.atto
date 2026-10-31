# postgres-orm.ores

Native Oreslang foundation for a PostgreSQL ORM: code-first DDL composition,
quoted identifiers, admitted column types, and workspace-scoped parameterized
query plans. **This first revision does not open database connections or execute
queries.** A native DB capability/driver remains required.

```ores
import module pg from './src/pg';
val sql = pg.table_typed_pk("workflows", arr[
  pg.column_spec("workspace_id", "uuid", false),
  pg.column_spec("id", "uuid", false),
  pg.column_spec("name", "text", false)
], arr["workspace_id", "id"]);
val query = pg.find_in_workspace_checked("workflows", workspace_id, workflow_id).unwrap();
// Adapter executes query.sql and binds query.params separately.
```

## Typed DDL path (draft; compiler execution pending)

For tables with a primary key, prefer `table_typed_pk` over raw column and
constraint fragments. `column_spec` carries names/types/nullability as data;
the builder checks the type allowlist, nonempty column/table/key names, duplicate
columns and primary-key entries, nullable primary-key columns, and primary-key
references to declared columns.
It returns `Result<string,string>` rather than silently accepting those errors.

```ores
val ddl = pg.table_typed_pk("workflows", arr[
  pg.column_spec("workspace_id", "uuid", false),
  pg.column_spec("id", "uuid", false),
  pg.column_spec("payload", "jsonb", true)
], arr["workspace_id", "id"]);
```

The new `admitted_identifier` uses the pinned Java compiler's
`is_identifier`, `replace_literal`, `split_literal` and collection
`length` operations. Only ASCII `[A-Za-z_][A-Za-z0-9_]*` identifiers
of **1–63 UTF-8 bytes** are admitted to `table_typed_pk` (including
column and primary-key names). Quotes, dots, Unicode, NUL and controls
are rejected rather than normalized or truncated. `pg.ident`,
`pg.column`, `pg.table` and `pg.find_in_workspace` remain legacy
surfaces without full admission and must not receive untrusted identifiers.

The new `find_in_workspace_checked` method applies the same strict identifier
policy to workspace-query table names and returns `Result<Query,string>`. It
still exposes an actor-local mutable parameter array and does not validate
workspace membership. The legacy `find_in_workspace` remains for compatibility.

**This does not establish safe database execution.** SQL names, even
admitted names, are not tenant authority. Other constraints, capabilities,
connection drivers, transactions, RLS and live PostgreSQL tests remain release
blockers. Do not share mutable query plans across execution domains.

The legacy `table(name, columns, trusted_constraints)` method is retained only
for source-authored trusted fragments and backward compatibility. It is unsafe
for inputs influenced by a tenant or request, even when identifiers are quoted.
There is no implicit migration from that API to the typed builder.

Constraint strings and pre-rendered column strings are explicitly **trusted,
source-authored SQL**. They must never receive user input. The restricted
typed DDL path has stronger identifier admission than the legacy string API;
the legacy admission boundary still requires NUL/C0 and UTF-8-length checks
before executing arbitrary quoted names.
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
