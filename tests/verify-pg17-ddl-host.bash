#!/usr/bin/env bash
# Host-only fail-closed checks with a fake psql. Not PostgreSQL execution.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
script="$root/tests/pg17-ddl-contract.bash"
work="$(mktemp -d "${TMPDIR:-/tmp}/ores-pg-ddl-mock.XXXXXXXX")"
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/bin"
cat > "$work/bin/psql" <<'MOCK'
#!/usr/bin/env bash
set -euo pipefail
if [[ -n "${PG_MOCK_CALLS:-}" ]]; then printf '%s\n' "$*" >> "$PG_MOCK_CALLS"; fi
if [[ "$*" == *"SHOW server_version_num"* ]]; then
  printf '%s\n' "${PG_MOCK_SERVER_VERSION:-170005}"
  exit "${PG_MOCK_VERSION_EXIT:-0}"
fi
cat > "$PG_MOCK_STDIN"
printf '%s\n' "${PG_MOCK_RESULT:-0}"
exit "${PG_MOCK_EXIT:-0}"
MOCK
chmod +x "$work/bin/psql"
export PATH="$work/bin:$PATH" PG_TEST_DSN='postgresql://test@disposable/db' PG_MOCK_STDIN="$work/input.sql"
check_reject() {
  local label="$1" target="${2:-$script}"
  if bash "$target" > "$work/$label.out" 2>&1; then
    echo "HOST_DDL_MOCK_FAIL: $label was accepted" >&2; exit 1
  fi
  grep -q '^PG_DDL_CONTRACT_NOT_VERIFIED:' "$work/$label.out" ||
    { echo "HOST_DDL_MOCK_FAIL: $label missing failure marker" >&2; exit 1; }
  printf 'HOST_DDL_MOCK_CASE=%s PASS\n' "$label"
}
unset PG_TEST_DISPOSABLE
check_reject missing-disposable-opt-in
export PG_TEST_DISPOSABLE=I_ACKNOWLEDGE_DISPOSABLE_DATABASE
unset PG_TEST_DSN
check_reject missing-dsn
export PG_TEST_DSN='postgresql://test@disposable/db'
# A drifted guest SQL golden must fail before contacting any database.
mkdir -p "$work/drifted/tests"
cp "$script" "$work/drifted/tests/pg17-ddl-contract.bash"
printf '%s\n' 'DRIFTED FIXTURE: NO SQL GOLDEN' > "$work/drifted/tests/plans.ores"
export PG_MOCK_CALLS="$work/psql-calls.txt"
: > "$PG_MOCK_CALLS"
check_reject altered-golden-rejected-before-db "$work/drifted/tests/pg17-ddl-contract.bash"
[[ ! -s "$PG_MOCK_CALLS" ]] || { echo 'HOST_DDL_MOCK_FAIL: drift caused database contact' >&2; exit 1; }
[[ "$(bash "$script")" == PG_DDL_CONTRACT_SQL_ONLY_PASS:* ]] ||
  { echo 'HOST_DDL_MOCK_FAIL: expected mock pass' >&2; exit 1; }
for marker in 'BEGIN;' "current_setting('server_version_num')" 'CREATE SCHEMA :"contract_schema";' 'UNIQUE ("workspace_id", "external_id")' 'FOREIGN KEY ("workspace_id") REFERENCES "workspaces" ("id")' 'WHEN unique_violation' 'WHEN foreign_key_violation' 'WHEN not_null_violation' 'ROLLBACK;' 'SELECT count(*) FROM pg_namespace'; do
  grep -Fq "$marker" "$work/input.sql" || { echo "HOST_DDL_MOCK_FAIL: missing SQL guard $marker" >&2; exit 1; }
done
printf '%s\n' 'HOST_DDL_MOCK_CASE=normal-mock PASS'
export PG_MOCK_RESULT=1
check_reject nonrollback-detection
unset PG_MOCK_RESULT
export PG_MOCK_EXIT=41
check_reject psql-command-failure
unset PG_MOCK_EXIT
export PG_MOCK_SERVER_VERSION=160017
check_reject rejects-postgresql-16
export PG_MOCK_SERVER_VERSION=180000
check_reject rejects-postgresql-18
export PG_MOCK_SERVER_VERSION=17.0
check_reject rejects-malformed-version
unset PG_MOCK_SERVER_VERSION
export PG_MOCK_VERSION_EXIT=41
check_reject version-probe-failure
unset PG_MOCK_VERSION_EXIT
printf '%s\n' 'HOST_DDL_MOCK_SCENARIOS=10/10 PASS (NOT POSTGRESQL OR ORESLANG EXECUTION)'
