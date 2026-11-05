#!/usr/bin/env bash
# HOST ONLY: synthetic PostgreSQL ORM receipts cannot prove compiler/guest execution.
set -euo pipefail
export LC_ALL=C
repo="$(cd "$(dirname "$0")/.." && pwd -P)"
checker="$repo/ci/verify-native-harness-receipts.sh"
tmp="$(mktemp -d)"
trap 'rm -rf -- "$tmp"' EXIT
chmod 700 "$tmp"
cp "$repo/ci/native-harness-cases.txt" "$tmp/manifest"
[[ $(wc -l < "$tmp/manifest") -eq 6 ]] || { echo 'invalid fixture count' >&2; exit 1; }
base="$tmp/valid"
while IFS= read -r id; do printf 'ORES_TEST|PASS|%s|\n' "$id" >> "$base"; done < "$tmp/manifest"
printf 'ORES_TEST|SUMMARY|total=6|passed=6|failed=0|skipped=0|filtered=0\n' >> "$base"
bash "$checker" "$tmp/manifest" "$base" || {
  echo 'HOST_RECEIPT_BASELINE_FAILED' >&2; exit 1;
}
reject() {
  if bash "$checker" "$1" "$2" >"$tmp/out" 2>"$tmp/err"; then
    printf 'HOST_RECEIPT_MUTATION_MISSED: %s\n' "$3" >&2
    exit 1
  fi
  grep -Fq ORES_RECEIPT_REJECTED "$tmp/err"
}
ln -s "$tmp/manifest" "$tmp/symlink-manifest"
reject "$tmp/symlink-manifest" "$base" symlinked_manifest
ln -s "$base" "$tmp/symlink-output"
reject "$tmp/manifest" "$tmp/symlink-output" symlinked_stdout

cp "$base" "$tmp/mutant"
printf '\000' >> "$tmp/mutant"
reject "$tmp/manifest" "$tmp/mutant" embedded_nul
cp "$base" "$tmp/mutant"
sed -i '1s@|PASS|@|SKIP|@' "$tmp/mutant"
reject "$tmp/manifest" "$tmp/mutant" skipped_case
cp "$base" "$tmp/mutant"
printf 'ALREADY_VERIFIED\n' >> "$tmp/mutant"
reject "$tmp/manifest" "$tmp/mutant" extra_line
cp "$base" "$tmp/mutant"
truncate -s -1 "$tmp/mutant"
reject "$tmp/manifest" "$tmp/mutant" missing_final_newline
cp "$base" "$tmp/mutant"
printf '%8193s' ' ' >> "$tmp/mutant"
reject "$tmp/manifest" "$tmp/mutant" unbounded_stdout

cp "$tmp/manifest" "$tmp/dupe"
first="$(head -n 1 "$tmp/manifest")"
sed -i "2c$first" "$tmp/dupe"
reject "$tmp/dupe" "$base" duplicate_manifest
printf 'HOST_ONLY_ORM_RECEIPT_FENCES_PASS negatives=8; NOT_COMPILER_EXECUTION\n'
