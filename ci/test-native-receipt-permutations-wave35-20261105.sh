#!/usr/bin/env bash
# HOST ONLY: text-receipt policy tests, not AttoLang compilation or execution.
set -euo pipefail
export LC_ALL=C
root="$(cd "$(dirname "$0")/.." && pwd -P)"
checker="$root/ci/verify-native-harness-receipts.sh"
manifest="$root/ci/native-harness-cases.txt"
temp="$(mktemp -d)"
trap 'rm -rf -- "$temp"' EXIT
chmod 700 "$temp"
mapfile -t cases < "$manifest"
[[ ${#cases[@]} -eq 6 ]] || exit 1

# An authenticated six-case set may arrive in a different event order.
valid="$temp/reversed.out"
for ((i=${#cases[@]} - 1; i >= 0; i--)); do
    printf 'ORES_TEST|PASS|%s|\n' "${cases[i]}" >> "$valid"
done
printf 'ORES_TEST|SUMMARY|total=6|passed=6|failed=0|skipped=0|filtered=0\n' >> "$valid"
bash "$checker" "$manifest" "$valid"
reject() {
    if bash "$checker" "$1" "$2" > "$temp/stdout" 2> "$temp/stderr"; then
        printf 'HOST_RECEIPT_MUTATION_MISSED: %s\n' "$3" >&2
        exit 1
    fi
    grep -Fq 'ORES_RECEIPT_REJECTED:' "$temp/stderr"
}
cp "$valid" "$temp/mutant"
sed -i '1s/|PASS|/|pass|/' "$temp/mutant"
reject "$manifest" "$temp/mutant" lowercased_result
cp "$valid" "$temp/mutant"
sed -i '7s/|SUMMARY|/|summary|/' "$temp/mutant"
reject "$manifest" "$temp/mutant" lowercased_summary
cp "$valid" "$temp/mutant"
sed -i '1s@|$@ |@' "$temp/mutant"
reject "$manifest" "$temp/mutant" blank_detail
cp "$valid" "$temp/mutant"
sed -i '7s/total=6/total=06/' "$temp/mutant"
reject "$manifest" "$temp/mutant" noncanonical_total
cp "$manifest" "$temp/invalid-manifest"
printf 'invalid.case\n' > "$temp/invalid-manifest"
tail -n +2 "$manifest" >> "$temp/invalid-manifest"
reject "$temp/invalid-manifest" "$valid" invalid_manifest_path_segment
printf 'HOST_ONLY_ORM_RECEIPT_ORDER_AND_MUTATIONS_PASS negatives=5; NOT_COMPILER_EXECUTION\n'
