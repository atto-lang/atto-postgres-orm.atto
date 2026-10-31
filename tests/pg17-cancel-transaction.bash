#!/usr/bin/env bash
# PostgreSQL 17 cancellation/transaction rollback contract, SQL-only.
# NOT proof of Oreslang cancellation delivery or actor-owned transaction cleanup.
set -euo pipefail
fail() { printf 'PG_CANCEL_NOT_VERIFIED: %s\n' "$*" >&2; exit 1; }
[[ "${PG_TEST_DISPOSABLE:-}" == I_ACKNOWLEDGE_DISPOSABLE_DATABASE ]] ||
  fail 'disposable database opt-in required'
[[ -n "${PG_TEST_DSN:-}" ]] || fail 'PG_TEST_DSN missing'
command -v psql >/dev/null 2>&1 || fail 'psql unavailable'

major="$(psql -X -qAt -v ON_ERROR_STOP=1 "$PG_TEST_DSN" -c 'SHOW server_version_num')" ||
  fail 'server version probe failed'
[[ "$major" =~ ^17[0-9]{4}$ ]] || fail 'PostgreSQL 17 required'

suffix="${RANDOM}_${RANDOM}_$$"
schema="ores_cancel_${suffix}"
app="ores_cancel_${suffix}"
[[ "$schema" =~ ^[a-z0-9_]{1,63}$ ]] || fail 'invalid generated schema'
[[ "$app" =~ ^[a-z0-9_]{1,63}$ ]] || fail 'invalid generated application name'
tmp="$(mktemp -d)"
cleanup() {
  set +e
  [[ -n "${client_pid:-}" ]] && kill "$client_pid" >/dev/null 2>&1
  psql -X -q -v ON_ERROR_STOP=0 -v "contract_schema=$schema" "$PG_TEST_DSN" >/dev/null 2>&1 <<'SQL'
DROP SCHEMA IF EXISTS :"contract_schema" CASCADE;
SQL
  rm -rf "$tmp"
}
trap cleanup EXIT

psql -X -q -v ON_ERROR_STOP=1 -v "contract_schema=$schema" "$PG_TEST_DSN" <<'SQL'
CREATE SCHEMA :"contract_schema";
CREATE TABLE :"contract_schema".cancel_probe (
  id integer PRIMARY KEY,
  note text NOT NULL
);
SQL

PGAPPNAME="$app" psql -X -q -v ON_ERROR_STOP=1 \
  -v "contract_schema=$schema" "$PG_TEST_DSN" >"$tmp/stdout" 2>"$tmp/stderr" <<'SQL' &
\set VERBOSITY verbose
BEGIN;
INSERT INTO :"contract_schema".cancel_probe VALUES (1, 'must-roll-back');
SELECT pg_sleep(30);
COMMIT;
SQL
client_pid=$!

backend_pid=""
for _ in $(seq 1 60); do
  backend_pid="$(psql -X -qAt -v ON_ERROR_STOP=1 -v "app=$app" "$PG_TEST_DSN" \
    -c "SELECT pid FROM pg_stat_activity WHERE application_name = :'app' AND state = 'active' AND query LIKE '%pg_sleep%' ORDER BY pid LIMIT 1")" || true
  [[ "$backend_pid" =~ ^[0-9]+$ ]] && break
  sleep 0.2
done
[[ "$backend_pid" =~ ^[0-9]+$ ]] || fail 'sleeping backend was not observed'

cancelled="$(psql -X -qAt -v ON_ERROR_STOP=1 -v "target_pid=$backend_pid" "$PG_TEST_DSN" \
  -c "SELECT pg_cancel_backend(:'target_pid'::int)")" ||
  fail 'pg_cancel_backend call failed'
[[ "$cancelled" == "t" ]] || fail "backend cancellation returned: $cancelled"

set +e
wait "$client_pid"
status=$?
set -e
client_pid=""
[[ $status -ne 0 ]] || fail 'cancelled transaction session unexpectedly succeeded'
grep -Fq '57014' "$tmp/stderr" || fail 'cancelled session lacked SQLSTATE 57014'
grep -Fq 'canceling statement due to user request' "$tmp/stderr" ||
  fail 'cancelled session lacked cancellation diagnostic'

count="$(psql -X -qAt -v ON_ERROR_STOP=1 -v "contract_schema=$schema" "$PG_TEST_DSN" \
  -c 'SELECT count(*) FROM :"contract_schema".cancel_probe')" ||
  fail 'rollback verification query failed'
[[ "$count" == "0" ]] || fail "cancelled transaction committed data: $count"

probe="$(psql -X -qAt -v ON_ERROR_STOP=1 "$PG_TEST_DSN" -c 'SELECT 1')" ||
  fail 'database unusable after cancellation'
[[ "$probe" == "1" ]] || fail "post-cancel probe returned: $probe"

printf '%s\n' 'PG_CANCEL_ROLLBACK_SQL_ONLY_PASS'
