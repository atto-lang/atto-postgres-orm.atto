#!/usr/bin/env bash
# Host-only fake-compiler admission/oracle tests. NEVER native guest evidence.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
# Bind the mock oracle to the authored guest path and actual panic strings.
# This is static consistency, NOT compilation or runtime observation.
grep -Fq 'panic("invalid PostgreSQL identifier surface")' "$root/src/pg.ores"
grep -Fq 'panic("PostgreSQL table requires at least one column")' "$root/src/pg.ores"
grep -Fq 'pg.find_in_workspace("",' "$root/tests/negative/empty_identifier.ores"
grep -Fq 'pg.table("no_columns", arr[], arr[])' "$root/tests/negative/empty_table.ores"
grep -Fq 'pg.ident("bad\u0001name")' "$root/tests/negative/control_identifier.ores"
grep -Fq "run_guest control-identifier tests/negative/control_identifier.ores 'invalid PostgreSQL identifier surface'" "$root/scripts/verify-native-plans"
grep -Fq 'required_cases="$(printf' "$root/scripts/verify-native-plans"
grep -Fq '[[ "$actual_cases" == "$required_cases" ]]' "$root/scripts/verify-native-plans"
grep -Fq "fail 'native guest receipt row count mismatch'" "$root/scripts/verify-native-plans"
grep -Fq "fail 'native guest receipt contains non-PASS result'" "$root/scripts/verify-native-plans"
# Confirm source and guest maintain independent complete ASCII control catalogs.
grep -Fq 'for (val control of arr[' "$root/src/pg.ores"
grep -Fq 'for (val control of arr[' "$root/tests/plans.ores"
# An is_identifier result is not proof of the stricter ASCII-only contract.
# Verify the typed renderer rejects every character left by the ASCII map.
grep -Fq 'if name == "" || name.replace_literal("|", "") != name then return false; fi' "$root/src/pg.ores"
grep -Fq 'if mapped.replace_literal("|", "") != "" then return false; fi' "$root/src/pg.ores"
# NotSet and explicit SQL NULL are different. These are host-only source
# integrity guards, not a native guest/compiler execution result.
grep -Fq 'pub fnc admitted_field_change(FieldChange change): bool' "$root/src/pg.ores"
grep -Fq 'if !admitted_field_change(change) then' "$root/src/pg.ores"
grep -Fq 'if !admitted_field_change(edit.change) then' "$root/src/pg.ores"
grep -Fq 'if !admitted_field_change(entry.change) then' "$root/src/pg.ores"
grep -Fq 'NotSet silently conflated NULL with omission' "$root/tests/plans.ores"
grep -Fq 'if pg.admitted_identifier("nameé")' "$root/tests/plans.ores"
grep -Fq 'if pg.admitted_identifier("Ωname")' "$root/tests/plans.ores"
grep -Fq 'if pg.admitted_identifier("name|other")' "$root/tests/plans.ores"
grep -Fq "run_guest empty-identifier tests/negative/empty_identifier.ores 'invalid PostgreSQL identifier surface'" "$root/scripts/verify-native-plans"
grep -Fq "run_guest empty-table tests/negative/empty_table.ores 'PostgreSQL table requires at least one column'" "$root/scripts/verify-native-plans"
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
    if [[ "${MOCK_WRONG_DIAGNOSTIC:-}" == yes ]]; then
      echo 'empty PostgreSQL identifier' >&2
    else
      echo 'invalid PostgreSQL identifier surface' >&2
    fi
    exit 17;;
  tests/negative/empty_table.ores)
    echo PG_NEGATIVE_EMPTY_TABLE_STARTED
    echo 'PostgreSQL table requires at least one column' >&2; exit 18;;
  tests/negative/control_identifier.ores)
    echo PG_NEGATIVE_CONTROL_IDENTIFIER_STARTED
    echo 'invalid PostgreSQL identifier surface' >&2; exit 19;;
  *) echo "unexpected mocked guest $1" >&2; exit 127;;
esac
MOCK_GUEST
chmod +x "$work/orm/scripts/ores" "$work/orm/scripts/verify-native-plans"
for path in src/pg.ores tests/plans.ores tests/negative/empty_identifier.ores tests/negative/empty_table.ores tests/negative/control_identifier.ores; do
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
       && $(wc -l < "$evidence/outcomes.tsv") -eq 5
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
export MOCK_WRONG_DIAGNOSTIC=yes
run_case wrong-negative-diagnostic reject
unset MOCK_WRONG_DIAGNOSTIC
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
echo 'MOCK_HOST_GATE_SCENARIOS=10/10 PASS (NOT ORESLANG OR POSTGRESQL EXECUTION)'
