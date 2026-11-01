// Host-only Rust source guard. This never compiles Oreslang or touches a DB.
// Every real migration/back-end receipt is a separate promotion gate.
const SOURCE: &str = include_str!("../src/schema.ores");
const GUEST: &str = include_str!("schema-invariants.ores");
const VERIFIER: &str = include_str!("../scripts/verify-native-plans");
const POLICY: &str = include_str!("../docs/MIGRATION_BACKEND_PARITY.md");

fn section<'a>(source: &'a str, start: &str, end: &str) -> &'a str {
    source
        .split_once(start)
        .unwrap_or_else(|| panic!("missing start: {start}"))
        .1
        .split_once(end)
        .unwrap_or_else(|| panic!("missing end: {end}"))
        .0
}

#[test]
fn zero_database_dependencies_in_shared_schema_source() {
    for forbidden in [
        "import module pg", "psql", "postgresql://", "execute_sql(",
        "connection.open", "migration.apply", "sql_exec(",
    ] {
        assert!(!SOURCE.contains(forbidden), "portable source gained: {forbidden}");
    }
}

#[test]
fn checked_summary_uses_exact_review_admission() {
    let body = section(
        SOURCE,
        "pub fnc risk_summary_checked(",
        "// Source-code generation is a preview only",
    );
    assert!(body.contains("review_manifest_preview_checked(rt borrow plan)"));
    assert!(body.contains("if validated.is_err() then"));
    assert!(body.contains("return Err(\"unadmitted schema risk summary\")"));
    assert!(body.contains("return Ok(new SchemaRiskSummary("));
}

#[test]
fn summary_is_data_only_with_four_explicit_risks() {
    let body = section(
        SOURCE,
        "pub fnc risk_summary_checked(",
        "// Source-code generation is a preview only",
    );
    for risk in ["safe", "preflight", "manual", "destructive"] {
        assert!(body.contains(&format!("step.risk == \"{risk}\"")));
        assert!(body.contains(&format!("{risk}_count = {risk}_count + 1")));
    }
    for forbidden in ["approved = true", "execute_sql", "ALTER TABLE", "DROP TABLE"] {
        assert!(!body.contains(forbidden), "summary accidentally gained SQL authority");
    }
}

#[test]
fn public_step_risk_downgrade_blocks_advisory_helper() {
    let body = section(SOURCE, "pub has_blockers(): bool", "pub define class SchemaRiskSummary");
    assert!(body.contains("if step.risk != \"safe\" then return true"));
    assert!(body.contains("step.op != \"add_nullable_column\""));
    assert!(body.contains("step.op != \"drop_not_null\""));
    assert!(GUEST.contains("forged safe drop marked nonblocking"));
    assert!(GUEST.contains("forged safe drop risk summary admitted"));
}

#[test]
fn review_manifest_never_authorizes_execution() {
    let body = section(
        SOURCE,
        "pub fnc review_manifest_preview_checked(",
        "pub fnc risk_summary_checked(",
    );
    assert!(body.contains("STOPPED_FOR_EVALUATION"));
    assert!(body.contains("approved\\\":false"));
    assert!(body.contains("column_shapes_only"));
    assert!(body.contains("too many review steps"));
    assert!(body.contains("forged or inconsistent schema review operation"));
    assert!(!body.contains("execute_sql("));
}

#[test]
fn native_guest_has_positive_and_hostile_risk_oracles() {
    for oracle in [
        "safe risk summary rejected",
        "safe risk count wrong",
        "mixed preflight count wrong",
        "mixed destructive count wrong",
        "empty risk summary rejected",
        "forged risk summary admitted",
        "forged table scope risk summary admitted",
        "invalid identity risk summary admitted",
    ] {
        assert!(GUEST.contains(oracle), "guest risk oracle missing: {oracle}");
    }
    assert!(GUEST.contains("Pure Oreslang schema invariant and metamorphic contracts passed"));
}

#[test]
fn verifier_retains_all_eight_real_guest_oracles() {
    for input in [
        "run_guest positive tests/plans.ores positive",
        "run_guest schema-plans tests/schema-plans.ores schema-positive",
        "run_guest schema-adversarial tests/schema-adversarial.ores schema-adversarial-positive",
        "run_guest schema-invariants tests/schema-invariants.ores schema-invariants-positive",
        "run_guest combined-orm tests/orm-cross-backend.ores combined-positive",
        "run_guest empty-identifier tests/negative/empty_identifier.ores",
        "run_guest empty-table tests/negative/empty_table.ores",
        "run_guest control-identifier tests/negative/control_identifier.ores",
    ] {
        assert!(VERIFIER.contains(input), "required guest invocation missing: {input}");
    }
    assert!(VERIFIER.contains("-eq 9"));
    assert!(VERIFIER.contains("native guest receipt contains non-PASS result"));
    assert!(VERIFIER.contains("NOT_VERIFIED: native guest verification incomplete"));
}

#[test]
fn matched_catalog_diff_avoids_placeholder_heap_object() {
    let diff = section(
        SOURCE,
        "pub fnc diff_catalog_checked(",
        "// A stable-ID *review* manifest",
    );
    assert!(!diff.contains("new SchemaTable(\"placeholder\""));
    assert!(!diff.contains("existing_match = existing"));
    assert!(diff.contains("diff_checked(rt borrow wanted, rt borrow existing)"));
    assert!(diff.contains("if !matched then"));
    for oracle in [
        "two matched table diff lost a change",
        "first matched table order changed",
        "second matched table order changed",
        "second matched table risk changed",
    ] {
        assert!(GUEST.contains(oracle), "missing multi-table oracle: {oracle}");
    }
}

#[test]
fn portable_profile_caps_enforced_in_source() {
    assert!(SOURCE.contains("columns.size > 64"));
    assert!(SOURCE.contains("tables.size > 256"));
    assert!(SOURCE.contains("all_steps.size > 2048"));
    assert!(SOURCE.contains("duplicate catalog table stable identity"));
    assert!(SOURCE.contains("duplicate catalog physical table name"));
    assert!(SOURCE.contains("schema column name mapped to a different stable identity"));
    assert!(SOURCE.contains("physical table name conflicts with stable identity"));
}

#[test]
fn six_toolchains_have_independent_evidence_requirements() {
    for label in ["Java/GraalVM", "LLVM", "WASM", "Cranelift", ".NET", "Forge"] {
        assert!(POLICY.contains(label), "missing backend promotion rule: {label}");
    }
    assert!(POLICY.contains("UNVERIFIED for this exact guest module"));
    assert!(POLICY.contains("UNSUPPORTED"));
    assert!(POLICY.contains("not a deployment approval"));
}

#[test]
fn python_host_suites_are_not_mislabeled_as_rust_parity() {
    assert!(POLICY.contains("coverage-preserving Rust replacement"));
    assert!(POLICY.contains("do not count the new"));
    assert!(POLICY.contains("Python"));
}
