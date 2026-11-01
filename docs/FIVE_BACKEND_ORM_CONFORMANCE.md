# Five-backend ORM source and guest admission (draft; no release approval)

This project contains two independent Oreslang modules:
`src/schema.ores` (runtime-neutral structural catalog, diff, review-only
preview) and `src/pg.ores` (PostgreSQL-specific data-only SQL plans,
typed values, actor-lease state checks). It has **no certified cross-backend
live PostgreSQL driver**. The fact that one backend can run a signed-i64
expression does not prove that either ORM module compiles or executes.

## Current audit, November 1, 2026

| Toolchain | Known implementation boundary | Full ORM compiled guest |
| --- | --- | --- |
| Java/GraalVM | ORM's native guest harness targets a pinned Java 25 compiler; existing negative and positive source fixtures | **NOT VERIFIED** on this exact ORM head |
| LLVM | Requires equivalent class/module imports, `Array<T>`, `Result<T,E>`, checked string and borrow semantics; native compiler code must execute the same source | **NOT VERIFIED** |
| Wasm | Existing wasm32 scalar path can delegate to an LLVM compiler, but ORM class/Result/Array imports and worker-safe memory ownership must be proven on an actual Wasm guest | **NOT VERIFIED** |
| Cranelift | The Rust stage-0 frontend currently parses a scalar `fnc main` expression and i64 parameters; it cannot admit the ORM's module imports, classes, arrays, string operations or Result yet | **UNSUPPORTED for full ORM**, not a pass |
| .NET | Structured frontend/CIL/AOT subsets exist, but classes, collections, Result and full ORM source/actor authority must have independent compiled evidence | **NOT VERIFIED** |

No implicit stub, interpreter fallback, generated host-language arithmetic,
altered source syntax, skipped test, or exit-only smoke is permitted as a
substitute for an unchanged ORM guest. In particular, Cranelift cannot be
described as ORM-compatible merely because its experimental scalar JIT
produces integer 42.

## Executable fixture contract (source-only until run)

`contracts/orm-five-backend-gate.v1.json` binds each of the five backends
to the same four actual ORM fixtures:

- `tests/plans.ores`: imports and exercises `src/pg.ores`, including typed
  DDL, query binds and connection ownership state; exact PostgreSQL planner
  success sentinel.
- `tests/schema-plans.ores`: imports `src/schema.ores`; catalog, diff and
  preview output.
- `tests/schema-adversarial.ores`: rejects invalid stable IDs, unsafe
  operations and drift.
- `tests/schema-invariants.ores`: deterministic, metamorphic and three-way
  snapshot checks.

There are **20 required backend/case outcomes** (5 × 4). The manifest is
always `NOT_VERIFIED` regardless of how many fixtures are authored.
`scripts/verify-orm-five-backend-receipts.py` is a **local-only,
stdlib-only receipt-shape validator**, not an Oreslang compiler:

```bash
python3 scripts/verify-orm-five-backend-receipts.py
# NOT_VERIFIED: 5 toolchains x 4 suites = 20 compiled guest receipts required
```

After independent authorized toolchain execution, receipt artifacts may
be checked against one **clean, exact ORM Git HEAD**:

```bash
python3 scripts/verify-orm-five-backend-receipts.py \
  --orm-head <reviewed-40-hex-ORM-commit> \
  --receipts /private/local/verified-orm-receipts
```

For each named backend/case, a distinct UTF-8 JSON receipt named
`backend--case.json` is required. It must record exact compiler HEAD,
compiler/runner/guest artifact SHA-256 identifiers, exact source SHA-256,
both ORM module SHA-256 values, clean ORM HEAD, compiler success,
executed guest success, no skip, exact stdout and empty stderr.
The checker also requires stable compiler/runner identity across all four
cases for a backend. Unrecognized keys, missing/extra receipts,
duplicate JSON keys, stale source, invalid exit-code types or mock-only
`run_kind` are rejected.

Even a completely valid receipt *shape* is **not independent proof**
that the compiler really built/ran guest code: a forged JSON file can
claim hashes. A reviewer must separately verify original compile/link
commands, executable artifact hashes, workflow steps, independent process
exits, and exact binary/source provenance before promoting anything.
There is deliberately **no** `VERIFIED`/green claim emitted by this checker.

## Backend-specific completion sequence

1. Fix or authorize source-org runner admission, and capture jobs with
   `runner_id`/step names, exact source/PR HEAD and real compiler logs.
   The unresolved private-source incident forbids cross-organization
   Git-tree mirrors even if they require no stored PAT.
2. Java: JDK 25 with pinned `SOURCE_REF`; actually run
   `scripts/verify-native-plans` and the four unchanged source fixtures.
3. LLVM: build the native compiler/runtime, then compile **both** ORM
   modules and all four fixtures; prove data layouts, immutable snapshots,
   Result propagation, borrow checking and exact native output.
4. Wasm: build a pinned wasm32 guest with no unauthorized host capabilities;
   record the imported frontend/compiler SHA separately from the Wasm
   guest, and actually run all four suites in isolation.
5. Cranelift: implement typed class/Array/Result/module/string/borrow
   frontend/runtime and full source imports before attempting these
   fixtures. An i64-only gate must fail for full ORM parity.
6. .NET: compile the same sources to checked CIL, execute independent
   CLR tests, then run a **separate** NativeAOT executable check;
   tenant-isolate/actor memory remains a distinct requirement.
7. Independently complete PostgreSQL 17 live typed-parameter and
   transaction/RLS/lock/rollback tests. Source planning is not database
   execution; no backend may bypass actor-owned lease and tenant checks.

Do not broaden the runtime-neutral schema planner to SQL execution or
an auto-approved migration. Immutable plan data and absence of SQL
fragments are not, by themselves, Sendable or Serializable proofs.
LLVM should maintain actor-owned zero-GC arenas; Java should minimize
GC with explicit ownership; Wasm/.NET/Cranelift need independently
verified sandbox/tenant boundaries. All unimplemented capabilities
remain **fail-closed**, not downgraded to equivalent host tests.
