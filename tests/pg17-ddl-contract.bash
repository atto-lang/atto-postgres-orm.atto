#!/usr/bin/env bash
# Executes the source-authored SQL golden against a disposable PostgreSQL DB.
# Not native Oreslang, not an ORM driver, not an RLS/tenant authorization test.
set -euo pipefail

fail() { printf 'PG_DDL_CONTRACT_NOT_VERIFIED: %s\n' "$*" >&2; exit 1; }
[[ "\${PG_TEST_DISPOSABLE:-}" == 'I_ACKNOWLEDGE_DISPOSABLE_DATABASE' ]] ||
  fail 'explicit PG_TEST_DISPOSABLE opt-in required'
[[ -n "\${PG_TEST_DSN:-}" ]] || fail 'PG_TEST_DSN must point to an isolated disposable test database'
command -v psql >/dev/null 2>&1 || fail 'psql unavailable'

# Require a recognizable fixture golden before making any database connection.
# The SQL below is an independent PostgreSQL execution fixture, not emitted by
# the Oreslang compiler. If the planner fixture changes, stop for human review.
root="$(cd "$(dirname "\${BASH_SOURCE[0]}")/.." && pwd -P)"
fixture="$root/tests/plans.ores"
[[ -f "$fixture" ]] || fail 'native plan fixture missing'
expected='CREATE TABLE \"docs\" (\n  \"workspace_id\" uuid NOT NULL,\n  \"id\" uuid NOT NULL,\n  \"external_id\" text NOT NULL,\n  PRIMARY KEY (\"workspace_id\", \"id\"),\n  UNIQUE (\"workspace_id\", \"external_id\"),\n  FOREIGN KEY (\"workspace_id\") REFERENCES \"workspaces\" (\"id\")\n);\n'
grep -Fq -- "$expected" "$fixture" || fail 'authored Oreslang DDL golden has drifted'

# A new, random, bounded simple-ASCII schema name per invocation. All changes
# remain inside a transaction that ends with ROLLBACK; an error disconnects and
# automatically rolls the transaction back. No existing schema is touched.
schema="ores_pg_contract_\${RANDOM}_\${RANDOM}_$$"
[[ "$schema" =~ ^[a-z0-9_]{1,63}$ ]] || fail 'invalid ephemeral schema name'
result="$({ psql -X -q -A -t -v ON_ERROR_STOP=1 -v "contract_schema=$schema" "$PG_TEST_DSN" <<'SQL'
BEGIN;
CREATE SCHEMA :"contract_schema";
SET LOCAL search_path TO :"contract_schema", pg_catalog;

CREATE TABLE "workspaces" (
  "id" uuid NOT NULL,
  PRIMARY KEY ("id")
);
-- Byte-for-byte SQL emitted by the typed-constraint golden in tests/plans.ores.
CREATE TABLE "docs" (
  "workspace_id" uuid NOT NULL,
  "id" uuid NOT NULL,
  "external_id" text NOT NULL,
  PRIMARY KEY ("workspace_id", "id"),
  UNIQUE ("workspace_id", "external_id"),
  FOREIGN KEY ("workspace_id") REFERENCES "workspaces" ("id")
);

INSERT INTO "workspaces" ("id") VALUES ('00000000-0000-0000-0000-000000000001');
INSERT INTO "docs" ("workspace_id", "id", "external_id")
VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000010', 'ext-a');

DO $contract$
BEGIN
  -- Exact duplicate workspace/external ID must be rejected by UNIQUE.
  BEGIN
    INSERT INTO "docs" ("workspace_id", "id", "external_id")
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', 'ext-a');
    RAISE EXCEPTION 'unique contract was not enforced';
  EXCEPTION WHEN unique_violation THEN NULL;
  END;
  -- Missing referenced workspace must be rejected by FK.
  BEGIN
    INSERT INTO "docs" ("workspace_id", "id", "external_id")
    VALUES ('00000000-0000-0000-0000-000000000099', '00000000-0000-0000-0000-000000000012', 'ext-b');
    RAISE EXCEPTION 'foreign-key contract was not enforced';
  EXCEPTION WHEN foreign_key_violation THEN NULL;
  END;
  -- A nullable flag of false must be enforced by NOT NULL.
  BEGIN
    INSERT INTO "docs" ("workspace_id", "id", "external_id")
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000013', NULL);
    RAISE EXCEPTION 'not-null contract was not enforced';
  EXCEPTION WHEN not_null_violation THEN NULL;
  END;
  -- Exact composite primary-key reuse must be rejected independently.
  BEGIN
    INSERT INTO "docs" ("workspace_id", "id", "external_id")
    VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000010', 'ext-c');
    RAISE EXCEPTION 'primary-key contract was not enforced';
  EXCEPTION WHEN unique_violation THEN NULL;
  END;
END
$contract$;
ROLLBACK;
-- Schema must not exist after rollback; fail closed if a name collision or
-- unintended commit leaves a schema behind.
SELECT count(*) FROM pg_namespace WHERE nspname = :'contract_schema';
SQL
} 2>&1)" || fail 'psql contract execution failed (no success certificate)'
[[ "$result" == 0 ]] || fail "unexpected PostgreSQL output or non-rollback state: $result"
printf '%s\n' 'PG_DDL_CONTRACT_SQL_ONLY_PASS: typed SQL golden constraints enforced and transaction rolled back'
