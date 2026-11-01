#!/usr/bin/env bash
# PostgreSQL 17 two-session transaction lock E2E; SQL-only, never production.
set -euo pipefail
fail() { printf 'PG_LOCK_E2E_NOT_VERIFIED: %s\n' "$*" >&2; exit 1; }
[[ "${PG_TEST_DISPOSABLE:-}" == I_ACKNOWLEDGE_DISPOSABLE_DATABASE ]] ||
  fail 'disposable test database opt-in required'
[[ -n "${PG_TEST_DSN:-}" ]] || fail 'PG_TEST_DSN missing'
command -v psql >/dev/null 2>&1 || fail 'psql unavailable'
major="$(psql -X -qAt -v ON_ERROR_STOP=1 "$PG_TEST_DSN" -c 'SHOW server_version_num')" ||
  fail 'PostgreSQL version probe failed'
[[ "$major" =~ ^17[0-9]{4}$ ]] || fail 'PostgreSQL 17 server required'
left=$((100000+RANDOM))
right=$((100000+RANDOM))
tmp="$(mktemp -d)"
pid=''
cleanup() {
  set +e
  if [[ -n "$pid" ]]; then kill "$pid" 2>/dev/null; wait "$pid" 2>/dev/null; fi
  rm -rf "$tmp"
}
trap cleanup EXIT
psql -X -qAt -v ON_ERROR_STOP=1 -v "left=$left" -v "right=$right" "$PG_TEST_DSN" >"$tmp/holder.out" 2>"$tmp/holder.err" <<'SQL' &
BEGIN;
DO $guard$
BEGIN
  IF current_setting('server_version_num')::integer < 170000 OR
     current_setting('server_version_num')::integer >= 180000 THEN
    RAISE EXCEPTION 'holder must use PostgreSQL 17';
  END IF;
END
$guard$;
SELECT pg_advisory_xact_lock(:left,:right);
SELECT pg_sleep(8);
COMMIT;
SQL
pid=$!
busy=0
for _ in $(seq 1 50); do
  available="$(psql -X -qAt -v ON_ERROR_STOP=1 -v "left=$left" -v "right=$right" "$PG_TEST_DSN" <<'SQL'
SELECT pg_try_advisory_xact_lock(:left,:right);
SQL
)" || fail 'independent lock probe failed'
  if [[ "$available" == f ]]; then busy=1; break; fi
  [[ "$available" == t ]] || fail "unexpected try-lock result: $available"
  sleep 0.1
done
[[ "$busy" -eq 1 ]] || fail 'never observed a competing transaction lock'
set +e
wait "$pid"
holder_status=$?
set -e
pid=''
[[ "$holder_status" -eq 0 ]] || fail 'holder transaction failed'
after="$(psql -X -qAt -v ON_ERROR_STOP=1 -v "left=$left" -v "right=$right" "$PG_TEST_DSN" <<'SQL'
SELECT pg_try_advisory_xact_lock(:left,:right);
SQL
)" || fail 'post-commit lock probe failed'
[[ "$after" == t ]] || fail 'transaction advisory lock not released on COMMIT'
printf '%s\n' 'PG_LOCK_E2E_SQL_ONLY_PASS'
