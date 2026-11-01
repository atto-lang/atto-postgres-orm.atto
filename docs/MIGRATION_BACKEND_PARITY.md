# Migration planner portability and promotion gate (draft)

This repository's `src/schema.ores` is the **single portable Oreslang source**
for **review-only**, bounded catalog diffs, stable-ID reconciliation, risk
classification and stopped migration previews. It is not a DPM SQL generator,
a PostgreSQL driver, a migration runner, or a security approval capability.

## Backend status (November 1, 2026)

All rows below remain **UNVERIFIED for this exact guest module**; a common
source path and source-level tests are not compiler/runtime execution.

| Backend | Required independent native evidence |
| --- | --- |
| Java/GraalVM | Pin `SOURCE_REF` + JDK 25; build clean compiler; execute the exact-head eight guest oracles. |
| LLVM | Build its independent AOT compiler and zero-GC runtime; compile and run the **same unmodified** guest, compare stdout/exit/diagnostics and memory safety with ASan/UBSan. |
| WASM | Pin native LLVM frontend and Wasm bridge; compile that guest to Wasm; validate module, instantiate and execute it; do not claim driver access in zero-import profile. |
| Cranelift | Expand the independent Rust frontend beyond its currently scalar-only subset (imports/classes/arrays/Result/borrow); compile **the same guest** before claiming parity. |
| .NET | Expand native-AOT compiler beyond scalar-only shipping syntax; compile and execute the same guest without runtime JIT or dynamic compilation. |
| Forge | Expand independent C++ bootstrap beyond scalar subset; do not relabel Forge as Cranelift or reuse another backend's guest receipt. |

The required target contract includes the first five named backends and
Forge as an additional independent toolchain. A backend without source support
must return **UNSUPPORTED**, never a synthetic PASS.

## Shared, backend-neutral behavior

- Stable IDs and physical SQL names are distinct. No inferred rename and
  no duplicate stable-ID/physical-name collision is accepted.
- `diff_checked` and `diff_catalog_checked` emit data-only proposal steps.
- `SchemaPlan.has_blockers()` is an advisory helper, not a validated plan,
  and it fails closed on unknown or mismatched safe operations.
- `schema.risk_summary_checked` validates public operation/risk/identity
  shapes via `review_manifest_preview_checked`, then counts four risk tiers.
  A summary **never authorizes migration execution**, including an all-safe
  summary and an empty plan.
- Every review preview is `STOPPED_FOR_EVALUATION`, `approved=false`,
  `scope=column_shapes_only`. No SQL or DDL is emitted or executed.
- The v1 catalog lacks keys, indexes, defaults, RLS, policies, views and grants;
  it cannot authorize full database migration or deletion of unmodeled objects.
- No backend-specific conditionals, FFI, sockets or PostgreSQL calls may be
  added to this portable module. Native variants must preserve observable
  semantics; backend-specific database adapters are separate.

## Evidence classes and exact admission order

1. **Static source guard (host only):** `rustc --edition=2021 --test tests/migration_portability.rs -o /tmp/orm-migration-source-tests && /tmp/orm-migration-source-tests`.
   This only checks source and test registration; it does not compile Oreslang.
2. **Pinned Java compiler guest:** run `scripts/verify-native-plans` on the
   exact immutable ORM head with the JDK 25 compiler pinned by `SOURCE_REF`.
   Require eight real guest outputs, correct negative diagnostics and raw,
   digest-bound job/build/runtime evidence.
3. **Per-backend executable guest:** run the identical `.ores` fixtures through
   each toolchain with independent compiler hashes, real process exit and
   raw stdout/stderr. Explicitly reject unsupported syntax/feature paths.
4. **Independent TypeSpec/TJSV contract check:** compare independently compiled
   TypeSpec semantics against the authored Draft 2020-12 JSON Schema. Neither
   schema is silently overwritten on mismatch.
5. **PostgreSQL 17 SQL-only:** rerun on a stepful disposable DB, retaining
   rollback, cancellation and RLS evidence as **SQL-only**.
6. **Driver and live migration:** separately prove least-privileged actor-owned
   connections, bind codecs, tenant RLS, rollback/fencing, then a separately
   authorized migrator with independent DPM full-catalog SQL, locks,
   checksums, drift checks and post-apply readback. A `safe` risk label is
   not a deployment approval.

## Non-promotion rules

- No source-org zero-step job, host oracle, Rust static test, hash, fixture
  registration or synthetic interpreter is proof of actual backend parity.
- No cross-organization private-source mirroring without authorization;
  runner-admission failure must be diagnosed before alternative carriers.
- Keep PR #13 **draft** and reconcile overlapping name-only schema PR #8
  before merging its parent #12 stack.
- Org tooling policy prohibits Python. Existing Python host tests in this
  draft need a coverage-preserving Rust replacement; do not count the new
  Rust source guard as a port of the JSON Schema differential suites.
