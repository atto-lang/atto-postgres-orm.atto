#!/usr/bin/env bash
# SQL-only PostgreSQL 17 E2E; not an Oreslang driver or DPM migration.
set -euo pipefail
fail() { printf 'PG_CATALOG_E2E_NOT_VERIFIED: %s\n' "$*" >&2; exit 1; }
[[ "${PG_TEST_DISPOSABLE:-}" == I_ACKNOWLEDGE_DISPOSABLE_DATABASE ]] ||
  fail 'explicit disposable test database opt-in required'
[[ -n "${PG_TEST_DSN:-}" ]] || fail 'PG_TEST_DSN missing'
command -v psql >/dev/null 2>&1 || fail 'psql unavailable'
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
fixture="$root/tests/pg17-catalog-readback-e2e.sql"
[[ -r "$fixture" ]] || fail 'SQL catalog fixture missing'
major="$(psql -X -qAt -v ON_ERROR_STOP=1 "$PG_TEST_DSN" -c 'SHOW server_version_num')" ||
  fail 'PostgreSQL version probe failed'
[[ "$major" =~ ^17[0-9]{4}$ ]] || fail 'PostgreSQL 17 server required'
schema="ores_catalog_"$RANDOM"_"$RANDOM"_$$"
[[ "$schema" =~ ^[a-z0-9_]{1,63}$ ]] || fail 'invalid temporary schema name'
result="$(psql -X -qAt -v ON_ERROR_STOP=1 -v "fixture_schema=$schema" "$PG_TEST_DSN" -f "$fixture")" ||
  fail 'live catalog SQL failed; transaction not certified'
[[ "$result" == "$(printf 'PG17_CATALOG_E2E_OK\n0')" ]] ||
  fail "catalog result or rollback check mismatch: $result"
printf '%s\n' 'PG_CATALOG_E2E_SQL_ONLY_PASS'
