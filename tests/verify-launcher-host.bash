#!/usr/bin/env bash
# Host-only preflight tests with mocked JVM; never native guest evidence.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
work="$(mktemp -d "${TMPDIR:-/tmp}/pg-launcher-check.XXXXXXXX")"
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/orm/scripts" "$work/compiler/target/classes/dev/oreslang/launcher" "$work/bin"
cp "$root/scripts/ores" "$work/orm/scripts/ores"
chmod +x "$work/orm/scripts/ores"
printf 'ignored source\n' > "$work/compiler/.gitignore"
printf 'compiler dummy\n' > "$work/compiler/README"
(cd "$work/compiler" && git init -q && git config user.email mock@example.invalid && git config user.name Mock && git add README .gitignore && git commit -qm pin)
sha="$(git -C "$work/compiler" rev-parse HEAD)"
printf '%s\n' "$sha" > "$work/orm/SOURCE_REF"
printf '/mock/dependency.jar\n' > "$work/compiler/target/classpath.txt"
printf 'NOT A CLASS FILE\n' > "$work/compiler/target/classes/dev/oreslang/launcher/OresMain.class"
cat > "$work/bin/java25" <<'JAVA25'
#!/usr/bin/env bash
if [[ "${1:-}" == '-version' ]]; then echo 'openjdk version "25.0.1" 2026-10-31' >&2; exit 0; fi
echo 'MOCK_LAUNCH_EXECUTED_NOT_NATIVE'
JAVA25
cat > "$work/bin/java21" <<'JAVA21'
#!/usr/bin/env bash
if [[ "${1:-}" == '-version' ]]; then echo 'openjdk version "21.0.12" 2026-10-31' >&2; exit 0; fi
echo 'WRONG_JAVA_EXECUTED'
JAVA21
chmod +x "$work/bin/java25" "$work/bin/java21"
export ORESLANG_SOURCE_DIR="$work/compiler" ORES_JAVA="$work/bin/java25"
count=0
run_case() {
  local name="$1" expected="$2" rc=0
  set +e
  "$work/orm/scripts/ores" tests/plans.ores > "$work/$name.stdout" 2> "$work/$name.stderr"
  rc=$?
  set -e
  if [[ "$expected" == success ]]; then
    [[ "$rc" -eq 0 ]] && grep -Fxq 'MOCK_LAUNCH_EXECUTED_NOT_NATIVE' "$work/$name.stdout" ||
      { echo "HOST_LAUNCHER_TEST_FAIL: $name expected success (actual exit $rc)" >&2; exit 1; }
  else
    [[ "$rc" -eq 69 ]] && ! grep -q MOCK_LAUNCH_EXECUTED_NOT_NATIVE "$work/$name.stdout" ||
      { echo "HOST_LAUNCHER_TEST_FAIL: $name expected fail-closed (actual exit $rc)" >&2; exit 1; }
  fi
  count=$((count + 1))
  printf 'HOST_ONLY_LAUNCHER_CASE=%s EXPECTED=%s RESULT=PASS\n' "$name" "$expected"
}
run_case pinned-good-path success
export ORES_JAVA="$work/bin/missing"
run_case explicit-java-missing reject
export ORES_JAVA="$work/bin/java21"
run_case java-21-rejected reject
export ORES_JAVA="$work/bin/java25"
mv "$work/compiler/target/classpath.txt" "$work/classpath.bak"
run_case classpath-missing reject
mv "$work/classpath.bak" "$work/compiler/target/classpath.txt"
mv "$work/compiler/target/classes/dev/oreslang/launcher/OresMain.class" "$work/launcher.bak"
run_case launcher-class-missing reject
mv "$work/launcher.bak" "$work/compiler/target/classes/dev/oreslang/launcher/OresMain.class"
printf '0%.0s' {1..40} > "$work/orm/SOURCE_REF"
run_case compiler-sha-mismatch reject
printf '%s\n' "$sha" > "$work/orm/SOURCE_REF"
printf 'DIRTY\n' >> "$work/compiler/README"
run_case dirty-tracked-compiler reject
git -C "$work/compiler" checkout -- README
mkdir -p "$work/compiler/src"
printf 'src/ignored.java\n' > "$work/compiler/.gitignore"
(cd "$work/compiler" && git add .gitignore && git commit -qm ignore-rule)
# Update SOURCE_REF to reflect the clean HEAD after adding an ignore rule.
git -C "$work/compiler" rev-parse HEAD > "$work/orm/SOURCE_REF"
printf 'IGNORED BUILD INPUT\n' > "$work/compiler/src/ignored.java"
run_case ignored-compiler-input reject
[[ "$count" -eq 8 ]] || { echo "Expected 8 cases; got $count" >&2; exit 1; }
echo 'HOST_ONLY_LAUNCHER_TESTS=8/8 PASS (NO NATIVE EXECUTION)'
