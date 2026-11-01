#!/usr/bin/env bash
# PostgreSQL 17 disposable SQL-only migration ledger replay contract.
# No native Oreslang driver, DPM migration file, production DB or approval.
set -euo pipefail
fail() { printf 'PG_HISTORY_E2E_NOT_VERIFIED: %s\n' "$*" >&2; exit 1; }
[[ "${PG_TEST_DISPOSABLE:-}" == I_ACKNOWLEDGE_DISPOSABLE_DATABASE ]] ||
  fail 'explicit disposable database opt-in required'
[[ -n "${PG_TEST_DSN:-}" ]] || fail 'PG_TEST_DSN required'
command -v psql >/dev/null 2>&1 || fail 'psql required'
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
fixture="$root/tests/pg17-migration-history-e2e.sql"
[[ -r "$fixture" ]] || fail 'migration-history fixture missing'
version="$(psql -X -qAt -v ON_ERROR_STOP=1 "$PG_TEST_DSN" -c 'SHOW server_version_num')" ||
  fail 'PostgreSQL server version probe failed'
[[ "$version" =~ ^17[0-9]{4}$ ]] || fail 'PostgreSQL 17 server required'
schema="ores_history_"$RANDOM"_"$RANDOM"_$$"
[[ "$schema" =~ ^[a-z0-9_]{1,63}$ ]] || fail 'unsafe generated schema identity'
receipt="$(psql -X -qAt -v ON_ERROR_STOP=1 -v "fixture_schema=$schema" "$PG_TEST_DSN" -f "$fixture")" ||
  fail 'migration-history SQL transaction failed'
expected="$(printf 'APPLIED\nREPLAY_OK\nAPPLIED\n2\n1\nPG17_MIGRATION_HISTORY_E2E_OK\n0')"
[[ "$receipt" == "$expected" ]] || fail 'migration-history receipt mismatch or rollback failed'
printf '%s\n' 'PG_HISTORY_E2E_SQL_ONLY_PASS'
