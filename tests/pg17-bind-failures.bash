#!/usr/bin/env bash
# PostgreSQL 17 negative bind coercion contract, SQL-only.
# NOT Oreslang guest execution and NOT proof of a live Oreslang driver.
set -euo pipefail
fail() { printf 'PG_BIND_FAILURES_NOT_VERIFIED: %s\n' "$*" >&2; exit 1; }
[[ "${PG_TEST_DISPOSABLE:-}" == I_ACKNOWLEDGE_DISPOSABLE_DATABASE ]] ||
  fail 'disposable database opt-in required'
[[ -n "${PG_TEST_DSN:-}" ]] || fail 'PG_TEST_DSN missing'
command -v psql >/dev/null 2>&1 || fail 'psql unavailable'

major="$(psql -X -qAt -v ON_ERROR_STOP=1 "$PG_TEST_DSN" -c 'SHOW server_version_num')" ||
  fail 'server version probe failed'
[[ "$major" =~ ^17[0-9]{4}$ ]] || fail 'PostgreSQL 17 required'

valid="$({ psql -X -qAt -v ON_ERROR_STOP=1 "$PG_TEST_DSN" <<'SQL'
PREPARE typed_valid(uuid,text,integer,bigint,boolean,jsonb,timestamptz,bytea) AS
SELECT
  $1 = '00000000-0000-0000-0000-000000000001'::uuid
  AND $2 = ''
  AND $3 = -2147483648
  AND $4 = 9223372036854775807::bigint
  AND $5 IS TRUE
  AND $6 = '{"safe":true}'::jsonb
  AND $7 = '2026-10-31T12:00:00Z'::timestamptz
  AND $8 = decode('00ff','hex');
EXECUTE typed_valid(
  '00000000-0000-0000-0000-000000000001',
  '',
  '-2147483648',
  '9223372036854775807',
  'true',
  '{"safe":true}',
  '2026-10-31T12:00:00Z',
  '\x00ff'
);
PREPARE typed_null(text) AS SELECT $1 IS NULL;
EXECUTE typed_null(NULL);
DEALLOCATE typed_valid;
DEALLOCATE typed_null;
SQL
} 2>&1)" || fail 'valid typed prepared binds failed'
[[ "$valid" == "$(printf 't\nt')" ]] || fail "unexpected valid bind result: $valid"

expect_sqlstate() {
  local state="$1"
  local label="$2"
  local sql="$3"
  local output status
  set +e
  output="$(printf '%s\n' '\set VERBOSITY verbose' "$sql" |
    psql -X -qAt -v ON_ERROR_STOP=1 "$PG_TEST_DSN" 2>&1)"
  status=$?
  set -e
  [[ $status -ne 0 ]] || fail "$label unexpectedly succeeded"
  grep -Fq "$state" <<<"$output" || fail "$label did not report SQLSTATE $state: $output"
}

expect_sqlstate 22P02 invalid_uuid \
  "PREPARE bad_uuid(uuid) AS SELECT \$1; EXECUTE bad_uuid('not-a-uuid');"
expect_sqlstate 22P02 invalid_json \
  "PREPARE bad_json(jsonb) AS SELECT \$1; EXECUTE bad_json('{bad');"
expect_sqlstate 22003 bigint_overflow \
  "PREPARE bad_bigint(bigint) AS SELECT \$1; EXECUTE bad_bigint('9223372036854775808');"
expect_sqlstate 22P02 invalid_boolean \
  "PREPARE bad_bool(boolean) AS SELECT \$1; EXECUTE bad_bool('truthy');"
expect_sqlstate 22P02 invalid_bytea \
  "PREPARE bad_bytea(bytea) AS SELECT \$1; EXECUTE bad_bytea('\x0');"

printf '%s\n' 'PG_BIND_FAILURES_SQL_ONLY_PASS'
