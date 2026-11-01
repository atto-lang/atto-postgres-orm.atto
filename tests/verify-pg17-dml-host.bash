#!/usr/bin/env bash
# Host-only mock admission/rollback tests for pg17-dml-contract.bash.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
script="$root/tests/pg17-dml-contract.bash"
work="$(mktemp -d "${TMPDIR:-/tmp}/pg-dml-mock.XXXXXXXX")"
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/bin" "$work/drift/tests"
cat > "$work/bin/psql" <<'MOCK'
#!/usr/bin/env bash
set -euo pipefail
if [[ -n "${PG_MOCK_CALLS:-}" ]]; then printf '%s\n' "$*" >> "$PG_MOCK_CALLS"; fi
if [[ "$*" == *"SHOW server_version_num"* ]]; then
  printf '%s\n' "${PG_MOCK_VERSION:-170005}"
  exit "${PG_MOCK_VERSION_EXIT:-0}"
fi
cat > "$PG_MOCK_SQL"
printf '%s\n' "${PG_MOCK_RESULT:-0}"
exit "${PG_MOCK_EXIT:-0}"
MOCK
chmod +x "$work/bin/psql"
export PATH="$work/bin:$PATH" PG_TEST_DSN="postgresql://temporary-disposable"
export PG_MOCK_SQL="$work/test.sql" PG_MOCK_CALLS="$work/calls.txt"
reject() {
  local label="$1" target="${2:-$script}"
  if bash "$target" > "$work/$label.out" 2>&1; then
    echo "PG_DML_HOST_FAIL: $label accepted invalid state" >&2; exit 1
  fi
  grep -q '^PG_DML_NOT_VERIFIED:' "$work/$label.out" ||
    { echo "PG_DML_HOST_FAIL: $label no fail-closed marker" >&2; exit 1; }
  printf 'PG_DML_HOST_CASE=%s PASS\n' "$label"
}
unset PG_TEST_DISPOSABLE
reject missing-disposable-opt-in
export PG_TEST_DISPOSABLE=I_ACKNOWLEDGE_DISPOSABLE_DATABASE
unset PG_TEST_DSN
reject missing-dsn
export PG_TEST_DSN="postgresql://temporary-disposable"
cp "$script" "$work/drift/tests/pg17-dml-contract.bash"
printf 'DRIFTED, NOT NATIVE SQL\n' > "$work/drift/tests/plans.ores"
: > "$PG_MOCK_CALLS"
reject fixture-drift-before-db "$work/drift/tests/pg17-dml-contract.bash"
[[ ! -s "$PG_MOCK_CALLS" ]] ||
  { echo "PG_DML_HOST_FAIL: drift caused DB contact" >&2; exit 1; }
[[ "$(bash "$script")" == PG_DML_SQL_ONLY_PASS:* ]] ||
  { echo "PG_DML_HOST_FAIL: expected controlled mock pass" >&2; exit 1; }
for marker in 'BEGIN;' 'CREATE SCHEMA :"test_schema"' 'PREPARE insert_doc' \
  'PREPARE update_doc' 'RETURNING id;' 'DO $check$' 'ROLLBACK;' \
  "SELECT count(*) FROM pg_namespace"; do
  grep -Fq "$marker" "$PG_MOCK_SQL" ||
    { echo "PG_DML_HOST_FAIL: missing SQL receipt marker $marker" >&2; exit 1; }
done
printf 'PG_DML_HOST_CASE=normal-mock-and-sql-shape PASS\n'
export PG_MOCK_RESULT=1
reject rollback-nonzero
unset PG_MOCK_RESULT
export PG_MOCK_EXIT=47
reject sql-process-failure
unset PG_MOCK_EXIT
export PG_MOCK_VERSION=160014
reject postgres16-rejected
export PG_MOCK_VERSION=180000
reject postgres18-rejected
export PG_MOCK_VERSION=17.0
reject malformed-version-rejected
unset PG_MOCK_VERSION
export PG_MOCK_VERSION_EXIT=47
reject version-probe-failure
unset PG_MOCK_VERSION_EXIT
printf 'PG_DML_HOST_MOCKS=10/10 PASS (NO DATABASE OR NATIVE GUEST)\n'
