#!/usr/bin/env bash
# Real PostgreSQL 17 prepared-statement contract, SQL-only. NOT Oreslang guest
# execution, an actor-owned wire driver, or tenant capability/RLS proof.
set -euo pipefail
fail() { printf 'PG_PREPARED_BINDS_NOT_VERIFIED: %s\n' "$*" >&2; exit 1; }
[[ "${PG_TEST_DISPOSABLE:-}" == I_ACKNOWLEDGE_DISPOSABLE_DATABASE ]] ||
  fail 'disposable database opt-in required'
[[ -n "${PG_TEST_DSN:-}" ]] || fail 'PG_TEST_DSN missing'
command -v psql >/dev/null 2>&1 || fail 'psql unavailable'
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
grep -Fq 'WHERE workspace_id = $1::uuid AND id = $2::uuid' "$root/tests/plans.ores" ||
  fail 'Oreslang guest SQL template drift'
grep -Fq 'typed workspace value aliased caller array' "$root/tests/plans.ores" ||
  fail 'guest array-alias oracle drift'
major="$(psql -X -qAt -v ON_ERROR_STOP=1 "$PG_TEST_DSN" -c 'SHOW server_version_num')" ||
  fail 'server version probe failed'
[[ "$major" =~ ^17[0-9]{4}$ ]] || fail 'PostgreSQL 17 required'
schema="ores_pg_prepared_${RANDOM}_${RANDOM}_$$"
[[ "$schema" =~ ^[a-z0-9_]{1,63}$ ]] || fail 'invalid temporary schema name'
result="$({ psql -X -qAt -v ON_ERROR_STOP=1 -v "contract_schema=$schema" "$PG_TEST_DSN" <<'SQL'
BEGIN;
CREATE SCHEMA :"contract_schema";
SET LOCAL search_path TO :"contract_schema", pg_catalog;
CREATE TABLE records (workspace_id uuid NOT NULL, id uuid NOT NULL,
  payload text NOT NULL, PRIMARY KEY (workspace_id, id));
INSERT INTO records VALUES
 ('00000000-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000010','record-a'),
 ('00000000-0000-0000-0000-000000000002',
  '00000000-0000-0000-0000-000000000010','record-b');
PREPARE workspace_lookup(uuid, uuid) AS
  SELECT payload FROM records WHERE workspace_id = $1::uuid AND id = $2::uuid;
EXECUTE workspace_lookup('00000000-0000-0000-0000-000000000001',
                         '00000000-0000-0000-0000-000000000010');
EXECUTE workspace_lookup('00000000-0000-0000-0000-000000000002',
                         '00000000-0000-0000-0000-000000000010');
PREPARE payload_lookup(text) AS
  SELECT count(*) FROM records WHERE payload = $1::text;
EXECUTE payload_lookup('record-a'' OR true--');
EXECUTE payload_lookup('');
DEALLOCATE workspace_lookup;
DEALLOCATE payload_lookup;
ROLLBACK;
SELECT count(*) FROM pg_namespace WHERE nspname = :'contract_schema';
SQL
} 2>&1)" || fail 'prepared statement SQL failed'
expected="$(printf 'record-a\nrecord-b\n0\n0\n0')"
[[ "$result" == "$expected" ]] ||
  fail "unexpected result / rollback state: $result"
printf '%s\n' 'PG_PREPARED_BINDS_SQL_ONLY_PASS'
