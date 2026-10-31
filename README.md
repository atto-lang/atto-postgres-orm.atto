# postgres-orm.ores

Native Oreslang foundation for a PostgreSQL ORM: code-first DDL composition,
quoted identifiers, admitted column types, and workspace-scoped parameterized
query plans. **This first revision does not open database connections or execute
queries.** A native DB capability/driver remains required.

```ores
import module pg from './src/pg';
val ddl = pg.table_typed_pk("workflows", arr[
  pg.column_spec("workspace_id", "uuid", false),
  pg.column_spec("id", "uuid", false),
  pg.column_spec("name", "text", false)
], arr["workspace_id", "id"]).unwrap();
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
`size` property. Only ASCII `[A-Za-z_][A-Za-z0-9_]*` identifiers
of **1–63 UTF-8 bytes** are admitted to `table_typed_pk` (including
column and primary-key names). Quotes, dots, Unicode, NUL and controls
are rejected rather than normalized or truncated. `pg.ident`,
`pg.column`, `pg.table` and `pg.find_in_workspace` remain legacy
surfaces without full admission and must not receive untrusted identifiers.

The `find_in_workspace_checked` method applies strict identifier admission
and returns the legacy `Result<Query,string>` surface, still exposing an
actor-local mutable parameter array. New code may use
`find_in_workspace_plan_checked` for a `Result<QueryPlan,string>`. The
`QueryPlan` constructor copies bound strings into a private array and exposes
only `param_count()` / `param_at(index)` (bounds checked, returning
`Result<string,string>`), plus its read-only SQL string. A transitional
`snapshot_legacy_query` helper copies a trusted legacy `Query` but does
**not** sanitize its SQL, validate tenant authority or make it executable.
Both are actor-local draft data types; no Sendable/driver capability is
established. Workspace membership and RLS must be checked independently.

### Typed UNIQUE and FOREIGN KEY constraints (draft; guest execution pending)

`table_typed_pk_constraints` extends `table_typed_pk` with data-only
`ConstraintSpec` nodes. Use `constraint_unique` and
`constraint_foreign_key` factories; no SQL expression strings are accepted:

```ores
val ddl = pg.table_typed_pk_constraints("docs", arr[
  pg.column_spec("workspace_id", "uuid", false),
  pg.column_spec("id", "uuid", false),
  pg.column_spec("external_id", "text", false)
], arr["workspace_id", "id"], arr[
  pg.constraint_unique(arr["workspace_id", "external_id"]),
  pg.constraint_foreign_key(arr["workspace_id"], "workspaces", arr["id"])
]);
```

The shared renderer emits PK, UNIQUE and FK in a **single direct pass**.
There is no finished-statement terminator replacement; duplicate rendered
clauses are compared for exact equality. `ConstraintSpec` copies both input arrays upon construction
into private fields, and its `local_columns()` / `referenced_columns()`
accessors return new copies. Source-array and returned-array mutation cannot
alter saved identifiers. These values remain actor-local until independent
`Sendable`/runtime ownership verification. The builder validates local-column existence, FK arity,
identifier admission, duplicate column names and constraint identity, with
limits of 64 columns, 32 PK fields, 32 additional constraints and 32 local
columns per constraint. Remote table/column existence,
unique-index suitability and cross-schema ownership **cannot be verified
without a database**; PostgreSQL must validate them during DDL execution.
There are no raw CHECK expressions, arbitrary referential actions, deferrable
modes or custom SQL names in this restricted surface. The rule arrays are
data-only and must remain actor-local during synchronous planning.

This newly authored code and fixtures have **not** been compiled or executed
by the pinned native Oreslang compiler. They are not release evidence.

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
the legacy admission boundary now rejects ASCII C0, NUL and DEL but still lacks PostgreSQL's UTF-8 byte-length check
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

For a **fresh, fail-closed release gate** (preferred over manually running
one positive fixture), invoke `./scripts/verify-native-plans` on a clean,
reviewed exact-head checkout using Java 25 and an authorized private compiler:

```sh
EXPECTED_ORM_SHA=<reviewed-40-hex-commit> \
ORESLANG_SOURCE_DIR=/absolute/path/to/oreslang-source.java \
ORES_JAVA=/absolute/path/to/jdk25/bin/java \
./scripts/verify-native-plans
```

The harness rebuilds the pinned compiler, records source and artifact SHA-256
identity, runs one positive and three independent negative guest processes, and
refuses to certify a negative failure unless the guest printed its own runtime
start sentinel before the expected panic. The evidence files are stored outside
the repo and **cannot substitute for independently executed CI job steps**.
See [guest acceptance gates](tests/ACCEPTANCE.md). No native guest execution
is claimed for this PR until real receipts and job logs are reviewed.

The compiler must first be built with Maven, including a `target/classpath.txt`:
`mvn -q -DskipTests package dependency:build-classpath -Dmdep.outputFile=target/classpath.txt`.
The launcher now **fails closed** if an explicitly chosen `ORES_JAVA` is
missing or is not Java 25, if the compiler SHA differs from `SOURCE_REF`,
if compiler source is dirty/untracked/ignored, or if compiled
`OresMain.class` or its generated classpath is missing. It never silently
falls back from a supplied `ORES_JAVA` to an arbitrary system runtime.

Run host-only launcher preflight tests with
`bash tests/verify-launcher-host.bash`; eight mocked test cases passed
locally against the exact launcher and test blobs. This is **not**
Oreslang guest execution or PostgreSQL integration evidence.

Next: typed DbValue/DbRow and error surfaces, actor-confined prepared statements,
transactions and cancellation, bounded row streams, pool ownership, generated
row codecs, and live PostgreSQL driver conformance. No unsupported driver is
presented as implemented.

### C0/DEL legacy identifier hardening (guest execution pending)

`invalid_identifier_surface`, `ident` and `column` now reject all 32 ASCII
C0 controls (including NUL) and DEL before building SQL. The independent
`tests/plans.ores` catalog checks all 33 inputs, and
`tests/negative/control_identifier.ores` requires a separate guest panic
with the precise start marker. `scripts/verify-native-plans` now binds and
hashes that fourth guest's input. These source-level checks were inspected,
but the modified native/host guest suite has not been executed at this head.
Legacy quoted identifiers still lack complete PostgreSQL 63-byte UTF-8
validation and remain **trusted-only**.
