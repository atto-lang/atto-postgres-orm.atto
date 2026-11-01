#!/usr/bin/env bash
# PG17 SQL-only metadata preservation and drift checks on a disposable DB.
# Does NOT compile Oreslang, validate DPM files or grant DDL authorization.
set -euo pipefail
fail() { printf 'PG_METADATA_E2E_NOT_VERIFIED: %s\n' "$*" >&2; exit 1; }
[[ "${PG_TEST_DISPOSABLE:-}" == I_ACKNOWLEDGE_DISPOSABLE_DATABASE ]] ||
  fail 'disposable database opt-in required'
[[ -n "${PG_TEST_DSN:-}" ]] || fail 'PG_TEST_DSN missing'
command -v psql >/dev/null 2>&1 || fail 'psql unavailable'
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
fixture="$root/tests/pg17-catalog-metadata-e2e.sql"
[[ -r "$fixture" ]] || fail 'metadata fixture missing'
version="$(psql -X -qAt -v ON_ERROR_STOP=1 "$PG_TEST_DSN" -c 'SHOW server_version_num')" ||
  fail 'server version probe failed'
[[ "$version" =~ ^17[0-9]{4}$ ]] || fail 'PostgreSQL 17 required'
schema="ores_meta_${RANDOM}_${RANDOM}_$$"
[[ "$schema" =~ ^[a-z0-9_]{1,63}$ ]] || fail 'invalid temporary schema'
result="$(psql -X -qAt -v ON_ERROR_STOP=1 -v "fixture_schema=$schema" "$PG_TEST_DSN" -f "$fixture")" ||
  fail 'metadata SQL failed; rollback cannot be certified'
[[ "$result" == "$(printf 'PG17_METADATA_E2E_OK\n0')" ]] ||
  fail "metadata drift or rollback receipt mismatch: $result"
printf '%s\n' 'PG_METADATA_E2E_SQL_ONLY_PASS'
