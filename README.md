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

Constraint strings are explicitly trusted, source-authored SQL. They must never
receive user input. Identifiers are quoted; types are admitted from a closed list.
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

## Repository ownership and migration (2026-11-08)

This repo is currently `ores-truffle-oreslang/postgres-orm.ores`. The public language name is **AttoLang**; preserve `.ores` compatibility and old repo/package/CLI IDs until a separate compiler-backed and consumer-reviewed change proves replacement.

- **Belongs here:** schema-first AttoLang ORM, typed CRUD, safe migration preview and database contract tests.
- **Does not belong here:** production database operator privileges and commercial managed DB administration.
- **Organization model:** [atto-lang](https://github.com/atto-lang) owns portable language libraries, compilers, tools, tests, core/std and examples. [atto-co](https://github.com/atto-co) separately owns managed hosting, tenant/deployment control, identity, billing and SaaS. Existing similarly named `atto-*` repos should be audited for overlap but are not necessarily transfers of this source identity.
- **Initial proposed move:** this original numeric GitHub repository ID and history into `atto-lang/postgres-orm.ores` retaining the old name. Current migration wave authorizes zero direct moves into `atto-co`. Future product carve-outs require new owner/security approval.

**Safe transfer:** announce in [issue #26](https://github.com/ores-truffle-oreslang/.github/issues/26), follow [private migration draft #25](https://github.com/ores-truffle-oreslang/.github/pull/25). Record exact source SHA/tree, ID, release tags, PRs, packages, dependencies, branch/ruleset protections, target visibility and rights, Actions/runners, App/webhook permissions, secrets, Pages, rollback authority, source/target admins and independent security review. Never mirror private source without explicit authorization. After an approved GitHub ownership transfer verify unchanged ID/tree/history, restore security policy, change consumers separately and run exact-head tests with **nonzero executed steps**. `steps=[]`/`null` is `NOT_EXECUTED`; host or structural tests cannot certify AttoLang guest execution, database safety or actor parity.
