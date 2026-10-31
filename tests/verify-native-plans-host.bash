#!/usr/bin/env bash
# Host-only fake-compiler admission/oracle tests. NEVER native guest evidence.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
work="$(mktemp -d "${TMPDIR:-/tmp}/ores-pg-harness-mock.XXXXXXXX")"
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/orm/scripts" "$work/orm/src" "$work/orm/tests/negative" "$work/compiler" "$work/bin"
cp "$root/scripts/verify-native-plans" "$work/orm/scripts/verify-native-plans"
cat > "$work/orm/scripts/ores" <<'MOCK_GUEST'
#!/usr/bin/env bash
set -eu
case "$1" in
  tests/plans.ores)
    echo 'Postgres SQL planning contracts passed'; exit 0;;
  tests/negative/empty_identifier.ores)
    if [[ "${MOCK_SKIP_SENTINEL:-}" != yes ]]; then echo PG_NEGATIVE_EMPTY_IDENTIFIER_STARTED; fi
    echo 'empty PostgreSQL identifier' >&2; exit 17;;
  tests/negative/empty_table.ores)
    echo PG_NEGATIVE_EMPTY_TABLE_STARTED
    echo 'PostgreSQL table requires at least one column' >&2; exit 18;;
  *) echo "unexpected mocked guest $1" >&2; exit 127;;
esac
MOCK_GUEST
chmod +x "$work/orm/scripts/ores" "$work/orm/scripts/verify-native-plans"
for path in src/pg.ores tests/plans.ores tests/negative/empty_identifier.ores tests/negative/empty_table.ores; do
  echo 'MOCK PLACEHOLDER, NOT ORESLANG SOURCE' > "$work/orm/$path"
done
cat > "$work/bin/java" <<'MOCK_JAVA'
#!/usr/bin/env bash
printf 'openjdk version "25.0.1" 2026-10-31\n' >&2
MOCK_JAVA
cat > "$work/bin/mvn" <<'MOCK_MAVEN'
#!/usr/bin/env bash
set -e
if [[ "${1:-}" == '-version' ]]; then
  printf 'Apache Maven 3.9.9\nJava version: %s, vendor: Mock\n' "${MOCK_MAVEN_VERSION:-25.0.1}"
else
  mkdir -p target/classes/dev/oreslang/launcher
  printf 'MOCK CLASS, NOT REAL GUEST\n' > target/classes/dev/oreslang/launcher/OresMain.class
  printf 'MOCK DEPENDENCY\n' > deps.jar
  printf '%s/deps.jar\n' "$PWD" > target/classpath.txt
fi
MOCK_MAVEN
chmod +x "$work/bin/mvn" "$work/bin/java"
printf 'target/\ndeps.jar\nsrc/ignored-compiler.java\n' > "$work/compiler/.gitignore"
(cd "$work/compiler" && git init -q && git config user.email mock@example.test && git config user.name mock && git add .gitignore && git commit -qm init)
pinned="$(git -C "$work/compiler" rev-parse HEAD)"
printf '%s\n' "$pinned" > "$work/orm/SOURCE_REF"
# This ignored source path must not be exempted from guest provenance.
printf 'tests/negative/ignored-guest.ores\n' > "$work/orm/.gitignore"
(cd "$work/orm" && git init -q && git config user.email mock@example.test && git config user.name mock && git add . && git commit -qm init)
head="$(git -C "$work/orm" rev-parse HEAD)"
export PATH="$work/bin:$PATH" ORESLANG_SOURCE_DIR="$work/compiler" ORES_JAVA="$work/bin/java" EXPECTED_ORM_SHA="$head"
run_case() {
  local scenario="$1" expectation="$2" rc=0
  local output="$work/output-$scenario" evidence="$work/evidence-$scenario"
  mkdir -p "$evidence"
  set +e
  EVIDENCE_DIR="$evidence" "$work/orm/scripts/verify-native-plans" > "$output.stdout" 2> "$output.stderr"
  rc=$?
  set -e
  if [[ "$expectation" == pass ]]; then
    [[ "$rc" -eq 0 && "$(cut -f3 "$evidence/outcomes.tsv" | tail -n+2 | sort -u)" == PASS
       && $(wc -l < "$evidence/outcomes.tsv") -eq 4
       && "$(cat "$evidence/RESULT.txt")" == VERIFIED:* ]] ||
      { echo "MOCK HARNESS $scenario unexpected rejection (exit $rc)" >&2; cat "$output.stderr" >&2; exit 1; }
  else
    [[ "$rc" -ne 0 ]] || { echo "MOCK HARNESS $scenario accepted invalid execution" >&2; exit 1; }
    if [[ "$scenario" != stale-directory ]]; then
      grep -q '^NOT_VERIFIED:' "$evidence/RESULT.txt" ||
        { echo "MOCK HARNESS $scenario failed without negative receipt" >&2; exit 1; }
    fi
  fi
  printf 'MOCK_HARNESS_CASE=%s EXPECTED=%s STATUS=PASS EXIT=%s\n' "$scenario" "$expectation" "$rc"
}
run_case normal-mocked-oracles pass
export MOCK_SKIP_SENTINEL=yes
run_case missing-negative-sentinel reject
unset MOCK_SKIP_SENTINEL
export MOCK_MAVEN_VERSION=21.0.12
run_case wrong-maven-java reject
unset MOCK_MAVEN_VERSION
mkdir -p "$work/evidence-stale-directory"
printf 'VERIFIED: old garbage\n' > "$work/evidence-stale-directory/RESULT.txt"
run_case stale-directory reject
export EXPECTED_ORM_SHA="$(printf '0%.0s' {1..40})"
run_case incorrect-reviewed-head reject
export EXPECTED_ORM_SHA="$head"
printf 'UNTRACKED MOCK GUEST\n' > "$work/orm/tests/negative/untracked.ores"
run_case untracked-guest-input reject
rm "$work/orm/tests/negative/untracked.ores"
printf 'IGNORED MOCK GUEST\n' > "$work/orm/tests/negative/ignored-guest.ores"
run_case ignored-guest-input reject
rm "$work/orm/tests/negative/ignored-guest.ores"
mkdir -p "$work/compiler/src"
printf 'IGNORED MOCK COMPILER INPUT\n' > "$work/compiler/src/ignored-compiler.java"
run_case ignored-compiler-input reject
rm "$work/compiler/src/ignored-compiler.java"
printf '\nDIRTY\n' >> "$work/orm/src/pg.ores"
run_case dirty-worktree reject
echo 'MOCK_HOST_GATE_SCENARIOS=9/9 PASS (NOT ORESLANG OR POSTGRESQL EXECUTION)'
