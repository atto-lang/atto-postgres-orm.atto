"""Host-only validation of portable catalog fixtures. Not native Oreslang proof.

The TypeSpec/JSON Schema peer-semantic comparison is a separate TJSV gate;
these tests deliberately do not claim to replace it.
"""
import copy
import json
import pathlib
import os
import shutil
import subprocess
import tempfile
import unittest

from jsonschema import Draft202012Validator, ValidationError

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


class CatalogContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = load("contracts/orm-catalog.schema.json")
        Draft202012Validator.check_schema(cls.schema)
        cls.validator = Draft202012Validator(cls.schema)
        cls.current = load("contracts/examples/current.catalog.json")
        cls.desired = load("contracts/examples/desired.catalog.json")

    def test_fixture_validation(self):
        for candidate in (self.current, self.desired):
            with self.subTest(candidate=candidate["tables"][0]["name"]):
                self.validator.validate(candidate)

    def test_unknown_top_level_field_refused(self):
        candidate = copy.deepcopy(self.current)
        candidate["engine"] = "postgresql"
        with self.assertRaises(ValidationError):
            self.validator.validate(candidate)

    def test_invalid_kind_refused(self):
        candidate = copy.deepcopy(self.current)
        candidate["tables"][0]["columns"][0]["kind"] = "uuid; DROP TABLE users"
        with self.assertRaises(ValidationError):
            self.validator.validate(candidate)

    def test_confusable_and_qualified_identifier_refused(self):
        for bad in ("é", "schema.users", "name|other", "", "a" * 64):
            candidate = copy.deepcopy(self.current)
            candidate["tables"][0]["columns"][0]["name"] = bad
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                self.validator.validate(candidate)

    def test_valid_63_byte_name_admitted(self):
        candidate = copy.deepcopy(self.current)
        candidate["tables"][0]["columns"][0]["name"] = "a" * 63
        self.validator.validate(candidate)

    def test_required_and_closed_fields(self):
        for bad_change in ("remove_field", "extra_field", "wrong_nullability"):
            candidate = copy.deepcopy(self.current)
            col = candidate["tables"][0]["columns"][0]
            if bad_change == "remove_field":
                del col["stable_id"]
            elif bad_change == "extra_field":
                col["sql"] = "DROP TABLE users"
            else:
                col["nullable"] = "false"
            with self.subTest(bad_change=bad_change), self.assertRaises(ValidationError):
                self.validator.validate(candidate)

    def test_unknown_schema_version_refused(self):
        candidate = copy.deepcopy(self.current)
        candidate["schema_version"] = "ores.orm.catalog/v2"
        with self.assertRaises(ValidationError):
            self.validator.validate(candidate)

    def test_empty_columns_refused(self):
        candidate = copy.deepcopy(self.current)
        candidate["tables"][0]["columns"] = []
        with self.assertRaises(ValidationError):
            self.validator.validate(candidate)

    def test_authority_surface_smoke_not_semantic_proof(self):
        tsp = (ROOT / "contracts/orm-catalog.tsp").read_text(encoding="utf-8")
        for declaration in ("enum ColumnKind", "model Column", "model Table", "model Catalog"):
            self.assertIn(declaration, tsp)
        for kind in self.schema["$defs"]["ColumnKind"]["enum"]:
            self.assertIn(f'{kind}: "{kind}"', tsp)
        self.assertIn('"ores.orm.catalog/v1"', tsp)


    def test_codegen_guest_contract_source_only(self):
        """Source shape only; not compiler execution or generated Oreslang parse."""
        source = (ROOT / "src/schema.ores").read_text(encoding="utf-8")
        guest = (ROOT / "tests/schema-plans.ores").read_text(encoding="utf-8")
        self.assertIn("pub fnc table_descriptor_source_preview_checked(", source)
        self.assertIn("pub fnc model_source_preview_checked(", source)
        self.assertIn('if column.nullable then', source)
        self.assertIn('if native_type == "" then', source)
        self.assertIn("if !admitted_name(model_name) then", source)
        self.assertIn("if !admitted_name(member) then", source)
        self.assertIn("schema.model_source_preview_checked(rt borrow labels)", guest)
        self.assertIn("UUID silently lowered to unvalidated string", guest)
        self.assertIn("public-constructor forged identifier entered codegen", guest)


    def test_full_catalog_guest_contract_source_only(self):
        """Host source-presence check, not a native Oreslang or DPM test."""
        source = (ROOT / "src/schema.ores").read_text(encoding="utf-8")
        guest = (ROOT / "tests/schema-plans.ores").read_text(encoding="utf-8")
        for marker in (
            "pub define class SchemaCatalog as",
            "pub fnc catalog_checked(",
            "pub fnc diff_catalog_checked(",
            "if tables.size > 256 then",
            "duplicate catalog table stable identity",
            "duplicate catalog physical table name",
            "physical table name conflicts with stable identity",
            '"review_create_table"',
            '"review_drop_table"',
        ):
            self.assertIn(marker, source)
        for marker in (
            "forged public catalog admitted",
            "table drop silently authorized",
            "post-admission array mutation modified catalog",
        ):
            self.assertIn(marker, guest)


    def test_migration_review_manifest_only(self):
        """Schema/negative inputs only, NOT DPM or pure Oreslang execution."""
        schema = load("contracts/orm-plan-preview.schema.json")
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        approved = load("contracts/examples/plan-preview.json")
        validator.validate(approved)
        for name, mutate in (
            ("attempt-approval", lambda p: p.update(approved=True)),
            ("status-promotion", lambda p: p.update(status="proceed")),
            ("unknown-step", lambda p: p["steps"][0].update(op="DROP TABLE users")),
            ("risk-downgrade", lambda p: p["steps"][0].update(risk="safe")),
            ("identifier-injection", lambda p: p["steps"][0].update(table_id='users";DROP')),
            ("extra-sql", lambda p: p["steps"][0].update(sql="DELETE FROM users")),
            ("wrong-table-scope", lambda p: p["steps"][0].update(column_id="payload")),
        ):
            with self.subTest(name=name):
                candidate = copy.deepcopy(approved)
                mutate(candidate)
                with self.assertRaises(ValidationError):
                    validator.validate(candidate)
        source = (ROOT / "src/schema.ores").read_text(encoding="utf-8")
        self.assertIn("pub fnc review_manifest_preview_checked(", source)
        self.assertIn("forged or inconsistent schema review operation", source)
        self.assertIn("unadmitted review column stable ID", source)


    def test_portable_catalog_size_bounds(self):
        """Host-only Draft 2020-12 bounds, not Oreslang catalog execution."""
        template = copy.deepcopy(self.current["tables"][0])
        legal = copy.deepcopy(self.current)
        legal["tables"] = []
        for i in range(256):
            candidate = copy.deepcopy(template)
            candidate["stable_id"] = f"table_{i:03d}"
            candidate["name"] = f"table_{i:03d}"
            legal["tables"].append(candidate)
        self.validator.validate(legal)
        illegal = copy.deepcopy(legal)
        illegal["tables"].append(copy.deepcopy(template))
        with self.assertRaises(ValidationError):
            self.validator.validate(illegal)

    def test_column_count_limits(self):
        """Closed bounded catalog, no implicit migration of excess fields."""
        current = copy.deepcopy(self.current)
        sample = copy.deepcopy(current["tables"][0]["columns"][0])
        columns = []
        for i in range(64):
            c = copy.deepcopy(sample)
            c["stable_id"] = f"col_{i:02d}"
            c["name"] = f"col_{i:02d}"
            columns.append(c)
        current["tables"][0]["columns"] = columns
        self.validator.validate(current)
        current["tables"][0]["columns"].append(copy.deepcopy(sample))
        with self.assertRaises(ValidationError):
            self.validator.validate(current)
        current["tables"][0]["columns"] = []
        with self.assertRaises(ValidationError):
            self.validator.validate(current)

    def test_column_identity_and_kind_mutation_matrix(self):
        """12 distinct malformed field mutations with exact Draft 2020-12 oracle."""
        mutations = [
            ("stable_id", ""), ("stable_id", "9bad"), ("stable_id", "a.b"),
            ("stable_id", "a b"), ("stable_id", "name|scope"),
            ("stable_id", "x" * 64), ("stable_id", "é"),
            ("name", ""), ("name", "0start"), ("name", "a;DROP"),
            ("kind", "UUID"), ("kind", "varchar(25)"),
        ]
        for key, value in mutations:
            with self.subTest(field=key, value=value):
                candidate = copy.deepcopy(self.current)
                candidate["tables"][0]["columns"][0][key] = value
                with self.assertRaises(ValidationError):
                    self.validator.validate(candidate)

    def test_review_manifest_all_ten_operation_risk_pairs(self):
        """A valid preview is always stopped, never approval to apply."""
        schema = load("contracts/orm-plan-preview.schema.json")
        validator = Draft202012Validator(schema)
        table_ops = ("review_table_rename", "review_create_table", "review_drop_table")
        risk_for_op = {
            "review_table_rename": "manual",
            "review_create_table": "manual",
            "review_drop_table": "destructive",
            "review_column_rename": "manual",
            "review_type_change": "manual",
            "drop_not_null": "safe",
            "add_nullable_column": "safe",
            "set_not_null": "preflight",
            "add_required_column": "preflight",
            "drop_column": "destructive",
        }
        base = load("contracts/examples/plan-preview.json")
        for operation, risk in risk_for_op.items():
            with self.subTest(operation=operation):
                candidate = copy.deepcopy(base)
                candidate["steps"] = [
                    {"op": operation, "table_id": "docs",
                     "column_id": "" if operation in table_ops else "field",
                     "risk": risk}
                ]
                validator.validate(candidate)
                self.assertIs(candidate["approved"], False)
                self.assertEqual(candidate["status"], "STOPPED_FOR_EVALUATION")
                for wrong_risk in {"safe", "preflight", "manual", "destructive"} - {risk}:
                    wrong = copy.deepcopy(candidate)
                    wrong["steps"][0]["risk"] = wrong_risk
                    with self.assertRaises(ValidationError):
                        validator.validate(wrong)

    def test_review_manifest_wrong_scope_and_injection_matrix(self):
        schema = load("contracts/orm-plan-preview.schema.json")
        validator = Draft202012Validator(schema)
        base = load("contracts/examples/plan-preview.json")
        bad_table_ids = ("", "9bad", "a.b", "a;DROP", "é", "a" * 64)
        for value in bad_table_ids:
            with self.subTest(field="table_id", value=value):
                candidate = copy.deepcopy(base)
                candidate["steps"][0]["table_id"] = value
                with self.assertRaises(ValidationError):
                    validator.validate(candidate)
        for bad_col in ("field", "field2", "name_a"):
            with self.subTest(field="table-only-column", value=bad_col):
                candidate = copy.deepcopy(base)
                candidate["steps"][0]["column_id"] = bad_col
                with self.assertRaises(ValidationError):
                    validator.validate(candidate)
        for bad_col in ("", "9bad", "a.b", "x;DROP", "é", "x" * 64):
            with self.subTest(field="column-id", value=bad_col):
                candidate = copy.deepcopy(base)
                candidate["steps"] = [{"op": "drop_column", "table_id": "docs",
                                       "column_id": bad_col, "risk": "destructive"}]
                with self.assertRaises(ValidationError):
                    validator.validate(candidate)

    def test_review_manifest_2048_step_bound(self):
        validator = Draft202012Validator(load("contracts/orm-plan-preview.schema.json"))
        manifest = load("contracts/examples/plan-preview.json")
        step = copy.deepcopy(manifest["steps"][0])
        manifest["steps"] = [{**step, "table_id": f"tbl_{i}"} for i in range(2048)]
        validator.validate(manifest)
        manifest["steps"].append(copy.deepcopy(step))
        with self.assertRaises(ValidationError):
            validator.validate(manifest)

    def test_native_adversarial_suite_is_required_by_exact_head_harness(self):
        """Host source guard only: does not claim native compiler execution."""
        script = (ROOT / "scripts/verify-native-plans").read_text(encoding="utf-8")
        guest = (ROOT / "tests/schema-adversarial.ores").read_text(encoding="utf-8")
        mock = (ROOT / "tests/verify-native-plans-host.bash").read_text(encoding="utf-8")
        for marker in (
            "run_guest schema-plans tests/schema-plans.ores schema-positive",
            "run_guest schema-adversarial tests/schema-adversarial.ores schema-adversarial-positive",
            "required_cases=", "native guest receipt row count mismatch",
            "tests/schema-adversarial.ores",
        ):
            self.assertIn(marker, script)
        self.assertIn("Pure Oreslang adversarial schema contracts passed", guest)
        self.assertIn("missing-schema-adversarial-oracle", mock)
        self.assertIn("missing-schema-invariants-oracle", mock)
        self.assertIn("MOCK_HOST_GATE_SCENARIOS=17/17 PASS", mock)


    def test_metamorphic_guest_receipt_is_required(self):
        """Only check source registration; does not claim guest execution."""
        verifier = (ROOT / "scripts/verify-native-plans").read_text(encoding="utf-8")
        guest = (ROOT / "tests/schema-invariants.ores").read_text(encoding="utf-8")
        mock = (ROOT / "tests/verify-native-plans-host.bash").read_text(encoding="utf-8")
        self.assertIn(
            "run_guest schema-invariants tests/schema-invariants.ores schema-invariants-positive",
            verifier,
        )
        self.assertIn("schema-invariants", verifier)
        self.assertIn("native guest receipt row count mismatch", verifier)
        self.assertIn(' -eq 8 ]]', verifier)
        self.assertIn("Pure Oreslang schema invariant and metamorphic contracts passed", guest)
        self.assertIn("MOCK_SKIP_SCHEMA_INVARIANTS", mock)
        self.assertIn("missing-schema-invariants-oracle", mock)
        self.assertIn("MOCK_HOST_GATE_SCENARIOS=17/17 PASS", mock)

    def test_metamorphic_semantic_invariants_are_authored(self):
        """Source-only suite coverage guard, never an Oreslang test result."""
        guest = (ROOT / "tests/schema-invariants.ores").read_text(encoding="utf-8")
        for marker in (
            "table permutation emitted DDL",
            "cross-table physical-name collision admitted",
            "rename bypassed human review",
            "reverse drop risk not destructive",
            "same model preview was nondeterministic",
            "unsupported nullable class lowered",
            "forged table in descriptor",
            "UUID mapped without nominal codec",
            "empty review status missing",
            "executable SQL op forged into review",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, guest)
        self.assertGreaterEqual(guest.count("panic("), 55)

    def test_catalog_boundaries_and_closed_models(self):
        for target, mutate in (
            ("too-many-tables", lambda c: c.update(tables=c["tables"] * 257)),
            ("too-many-columns", lambda c: c["tables"][0].update(columns=c["tables"][0]["columns"] * 22)),
            ("illegal-table-name", lambda c: c["tables"][0].update(name="9starts_digit")),
            ("illegal-table-stable-id", lambda c: c["tables"][0].update(stable_id="éx")),
            ("illegal-column-stable-id", lambda c: c["tables"][0]["columns"][0].update(stable_id="a/b")),
            ("forged-table-sql", lambda c: c["tables"][0].update(sql="DROP TABLE users")),
            ("unknown-column-metadata", lambda c: c["tables"][0]["columns"][0].update(default_sql="1")),
            ("missing-table-columns", lambda c: c["tables"][0].pop("columns")),
        ):
            with self.subTest(target=target):
                candidate = copy.deepcopy(self.current)
                mutate(candidate)
                with self.assertRaises(ValidationError):
                    self.validator.validate(candidate)

    def test_all_review_ops_have_exact_risk_and_scope(self):
        schema = load("contracts/orm-plan-preview.schema.json")
        validator = Draft202012Validator(schema)
        risk = {
            "review_table_rename": "manual",
            "review_create_table": "manual",
            "review_drop_table": "destructive",
            "review_column_rename": "manual",
            "review_type_change": "manual",
            "drop_not_null": "safe",
            "add_nullable_column": "safe",
            "set_not_null": "preflight",
            "add_required_column": "preflight",
            "drop_column": "destructive",
        }
        self.assertEqual(set(schema["$defs"]["Step"]["properties"]["op"]["enum"]), set(risk))
        table_ops = {"review_table_rename", "review_create_table", "review_drop_table"}
        for op, expected in risk.items():
            with self.subTest(op=op):
                base = load("contracts/examples/plan-preview.json")
                base["steps"] = [{"op": op, "table_id": "users",
                                  "column_id": "" if op in table_ops else "name",
                                  "risk": expected}]
                validator.validate(base)
                for bad_risk in set(risk.values()) - {expected}:
                    tampered = copy.deepcopy(base)
                    tampered["steps"][0]["risk"] = bad_risk
                    with self.assertRaises(ValidationError):
                        validator.validate(tampered)
                tampered = copy.deepcopy(base)
                tampered["steps"][0]["column_id"] = "name" if op in table_ops else ""
                with self.assertRaises(ValidationError):
                    validator.validate(tampered)

    def test_duplicate_review_steps_denied(self):
        schema = load("contracts/orm-plan-preview.schema.json")
        validator = Draft202012Validator(schema)
        original = load("contracts/examples/plan-preview.json")
        original["steps"].append(copy.deepcopy(original["steps"][0]))
        with self.assertRaises(ValidationError):
            validator.validate(original)

    def test_review_manifest_is_never_an_execution_capability(self):
        schema = load("contracts/orm-plan-preview.schema.json")
        validator = Draft202012Validator(schema)
        for mutate in (
            lambda x: x.update(approved=True),
            lambda x: x.update(status="APPROVED"),
            lambda x: x.update(scope="full_database"),
            lambda x: x.update(migration_sql="ALTER TABLE users DROP COLUMN id"),
            lambda x: x.update(execution_token="admin"),
            lambda x: x["steps"][0].update(approved=True),
        ):
            candidate = load("contracts/examples/plan-preview.json")
            mutate(candidate)
            with self.assertRaises(ValidationError):
                validator.validate(candidate)

    def test_three_way_drift_implementation_is_guest_not_host_oracle(self):
        source = (ROOT / "src/schema.ores").read_text(encoding="utf-8")
        guest = (ROOT / "tests/schema-plans.ores").read_text(encoding="utf-8")
        self.assertIn("pub fnc plan_from_snapshot_checked(", source)
        self.assertIn("diff_catalog_checked(rt borrow accepted, rt borrow observed)", source)
        self.assertIn("observed catalog drift; stop for evaluation", source)
        self.assertIn("duplicate review operation", source)
        for guard in (
            "untracked observed table bypassed baseline drift gate",
            "observed desired-state drift silently adopted",
            "observed type drift silently adopted",
            "observed stable-ID conflict silently adopted",
            "forged observed catalog bypassed trust boundary",
            "duplicated destructive review operation admitted",
            "non-semantic observed column reordering caused false drift",
        ):
            self.assertIn(guard, guest)


    def test_portable_catalog_exhaustive_boundary_mutations(self):
        """Host-only JSON Schema checks; no Oreslang compiler or SQL invoked."""
        table = self.current["tables"][0]
        for field in ("stable_id", "name"):
            for name in ("_", "a", "Z_9", "a" * 63):
                candidate = copy.deepcopy(self.current)
                candidate["tables"][0][field] = name
                with self.subTest(field=field, name=name):
                    self.validator.validate(candidate)
            for name in ("", "9bad", "-dash", "a b", "a.b", "a\\tb",
                         "é", "Ω", "a|b", "a;DROP", "a" * 64):
                candidate = copy.deepcopy(self.current)
                candidate["tables"][0][field] = name
                with self.subTest(field=field, name=name), self.assertRaises(ValidationError):
                    self.validator.validate(candidate)
        for field in ("stable_id", "name"):
            for name in ("_", "a", "Z_9", "a" * 63):
                candidate = copy.deepcopy(self.current)
                candidate["tables"][0]["columns"][0][field] = name
                with self.subTest(field=field, name=name):
                    self.validator.validate(candidate)
            for name in ("", "9bad", "-dash", "a b", "a.b", "a\\tb",
                         "é", "Ω", "a|b", "a;DROP", "a" * 64):
                candidate = copy.deepcopy(self.current)
                candidate["tables"][0]["columns"][0][field] = name
                with self.subTest(field=field, name=name), self.assertRaises(ValidationError):
                    self.validator.validate(candidate)
        # Do not claim this schema checks duplicate stable IDs: JSON Schema
        # uniqueItems cannot express uniqueness by selected object properties.
        self.assertEqual(len(table["columns"]), 3)

    def test_schema_unknown_scalar_type_mutations(self):
        for kind in self.schema["$defs"]["ColumnKind"]["enum"]:
            candidate = copy.deepcopy(self.current)
            candidate["tables"][0]["columns"][0]["kind"] = kind
            with self.subTest(kind=kind):
                self.validator.validate(candidate)
        for kind in ("UUID", "varchar(64)", "text", "serial", "int", "float",
                     "vector(3)", "null", "", "bytea", "int8", "timestampz"):
            candidate = copy.deepcopy(self.current)
            candidate["tables"][0]["columns"][0]["kind"] = kind
            with self.subTest(kind=kind), self.assertRaises(ValidationError):
                self.validator.validate(candidate)

    def test_review_envelope_non_authorization_cross_product(self):
        plan_schema = load("contracts/orm-plan-preview.schema.json")
        Draft202012Validator.check_schema(plan_schema)
        validator = Draft202012Validator(plan_schema)
        fixture = load("contracts/examples/plan-preview.json")
        for operation in plan_schema["$defs"]["Step"]["properties"]["op"]["enum"]:
            table_op = operation in ("review_table_rename", "review_create_table", "review_drop_table")
            risk = {
                "review_table_rename": "manual", "review_create_table": "manual",
                "review_drop_table": "destructive", "review_column_rename": "manual",
                "review_type_change": "manual", "drop_not_null": "safe",
                "add_nullable_column": "safe", "set_not_null": "preflight",
                "add_required_column": "preflight", "drop_column": "destructive",
            }[operation]
            base = copy.deepcopy(fixture)
            base["steps"] = [{"op": operation, "table_id": "users",
                              "column_id": "" if table_op else "id", "risk": risk}]
            validator.validate(base)
            for forged in (
                lambda p: p.update(approved=True),
                lambda p: p.update(status="APPROVED"),
                lambda p: p.update(scope="full_catalog"),
                lambda p: p.update(sql="DROP TABLE users"),
                lambda p: p["steps"][0].update(sql="DROP TABLE users"),
                lambda p: p["steps"][0].update(approved=True),
            ):
                candidate = copy.deepcopy(base)
                forged(candidate)
                with self.subTest(operation=operation, forged=str(forged)), self.assertRaises(ValidationError):
                    validator.validate(candidate)

    def test_metamorphic_drift_guest_suite_is_part_of_required_oracle(self):
        """Source hook only; executed guest evidence must be a separate gate."""
        guest = (ROOT / "tests/schema-adversarial.ores").read_text(encoding="utf-8")
        launcher = (ROOT / "scripts/verify-native-plans").read_text(encoding="utf-8")
        for check in (
            "repeat review generated different bytes",
            "table enumeration order created phantom drift",
            "type/nullability change lost an independent operation",
            "same physical column name with new stable ID bypassed mapping",
            "physical table name reuse silently inferred stable identity",
            "safe-only review gained execution approval",
            "duplicate destructive table operation admitted",
            "empty catalog incorrectly reported drift",
        ):
            self.assertIn(check, guest)
        self.assertIn("run_guest schema-adversarial tests/schema-adversarial.ores schema-adversarial-positive", launcher)

    def test_native_harness_rejects_false_positive_mock_outputs(self):
        """Source-level gates only; a mock cannot provide native guest evidence."""
        harness = (ROOT / "tests/verify-native-plans-host.bash").read_text(encoding="utf-8")
        required = (
            "bad-positive-stdout", "bad-positive-exit",
            "launcher-exit-69", "negative-zero-exit",
            "negative-extra-stdout", "MOCK_HOST_GATE_SCENARIOS=17/17 PASS",
        )
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, harness)
        verifier = (ROOT / "scripts/verify-native-plans").read_text(encoding="utf-8")
        self.assertIn('cmp -s "$evidence/$label.expected-stdout"', verifier)
        self.assertIn('"$rc" -ne 69', verifier)
        self.assertIn('"$rc" -ne 0', verifier)
        # A negative test must fail for the *expected oracle*, not because
        # the mock checkout was left dirty by an earlier failure case.
        self.assertLess(harness.index("run_case bad-positive-stdout reject"),
                        harness.index("run_case dirty-worktree reject"))
        self.assertIn("guest oracle failed for schema-plans", harness)
        self.assertIn("guest oracle failed for schema-invariants", harness)
        self.assertIn("guest oracle failed for empty-identifier", harness)
        self.assertIn("guest oracle failed for control-identifier", harness)
        self.assertIn("guest oracle failed for empty-table", harness)

    def test_three_way_oracle_in_seventh_guest(self):
        """Presence-only: Oreslang execution remains a separate release gate."""
        fixture = (ROOT / "tests/schema-invariants.ores").read_text(encoding="utf-8")
        for marker in (
            "fresh accepted-observed baseline rejected",
            "observed-only nullable addition bypassed drift gate",
            "observed-only table drop bypassed drift gate",
            "observed rename bypassed drift gate",
            "stale baseline equal to desired bypassed drift gate",
        ):
            self.assertIn(marker, fixture)


    def test_pg17_e2e_script_bash_syntax(self):
        """Actual host Bash parser; not PostgreSQL execution."""
        shell = shutil.which("bash")
        if shell is None:
            self.skipTest("bash missing")
        for name in ("pg17-catalog-readback-e2e.bash", "pg17-migration-lock-e2e.bash",
                     "pg17-migration-lock-abort-e2e.bash"):
            with self.subTest(name=name):
                proc = subprocess.run(
                    [shell, "-n", str(ROOT / "tests" / name)],
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_pg17_e2e_rejects_missing_disposable_opt_in_without_db_contact(self):
        """Verify guard rejects before invoking psql, with an isolated fake PATH."""
        shell = shutil.which("bash")
        if shell is None:
            self.skipTest("bash missing")
        with tempfile.TemporaryDirectory() as tmp:
            marker = pathlib.Path(tmp) / "psql-called"
            fake = pathlib.Path(tmp) / "psql"
            fake.write_text(
                '#!/bin/sh\nprintf "CALLED\\n" >> "$PG_MOCK_CONTACT"\n'
                'printf "170001\\n"\n', encoding="utf-8")
            fake.chmod(0o755)
            env = os.environ.copy()
            env["PATH"] = tmp + os.pathsep + env.get("PATH", "")
            env["PG_MOCK_CONTACT"] = str(marker)
            env["PG_TEST_DSN"] = "postgresql://dummy@invalid/test"
            env.pop("PG_TEST_DISPOSABLE", None)
            for name in ("pg17-catalog-readback-e2e.bash", "pg17-migration-lock-e2e.bash",
                     "pg17-migration-lock-abort-e2e.bash"):
                with self.subTest(script=name):
                    proc = subprocess.run(
                        [shell, str(ROOT / "tests" / name)],
                        capture_output=True, text=True, env=env, check=False,
                    )
                    self.assertNotEqual(proc.returncode, 0)
                    self.assertIn("NOT_VERIFIED:", proc.stderr)
                    self.assertFalse(marker.exists(), "unauthorized DB contact")

    def test_pg17_e2e_refuses_wrong_server_versions(self):
        """Fake psql version only. Never claim a PostgreSQL E2E pass."""
        shell = shutil.which("bash")
        if shell is None:
            self.skipTest("bash missing")
        with tempfile.TemporaryDirectory() as tmp:
            fake = pathlib.Path(tmp) / "psql"
            fake.write_text('#!/bin/sh\nprintf "%s\\n" "$PG_MOCK_VERSION"\n',
                            encoding="utf-8")
            fake.chmod(0o755)
            env = os.environ.copy()
            env["PATH"] = tmp + os.pathsep + env.get("PATH", "")
            env["PG_TEST_DISPOSABLE"] = "I_ACKNOWLEDGE_DISPOSABLE_DATABASE"
            env["PG_TEST_DSN"] = "postgresql://dummy@invalid/test"
            for version in ("160017", "180001", "seventeen", "1700"):
                env["PG_MOCK_VERSION"] = version
                for name in ("pg17-catalog-readback-e2e.bash", "pg17-migration-lock-e2e.bash",
                     "pg17-migration-lock-abort-e2e.bash"):
                    with self.subTest(version=version, script=name):
                        proc = subprocess.run(
                            [shell, str(ROOT / "tests" / name)], capture_output=True,
                            text=True, env=env, check=False,
                        )
                        self.assertNotEqual(proc.returncode, 0)
                        self.assertIn("PostgreSQL 17", proc.stderr)

    def test_pg17_e2e_sql_scope_and_ci_registration(self):
        """Host-only source inventory, NOT actual live catalog verification."""
        sql = (ROOT / "tests/pg17-catalog-readback-e2e.sql").read_text(encoding="utf-8")
        catalog = (ROOT / "tests/pg17-catalog-readback-e2e.bash").read_text(encoding="utf-8")
        lock = (ROOT / "tests/pg17-migration-lock-e2e.bash").read_text(encoding="utf-8")
        workflow = (ROOT / ".github/workflows/pg17-ddl-integration.yml").read_text(
            encoding="utf-8")
        for marker in (
            "pg_catalog.pg_attribute", "CREATE SCHEMA",
            "ALTER TABLE accounts ADD COLUMN notes text", "CATALOG_SHAPE_DRIFT",
            "TYPE_DRIFT_NOT_CAUGHT", "RENAME_DRIFT_NOT_CAUGHT",
            "EXTRA_COLUMN_NOT_CAUGHT", "ROLLBACK;",
            "SELECT count(*) FROM pg_catalog.pg_namespace",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, sql)
        self.assertIn("PG_TEST_DISPOSABLE", catalog)
        self.assertIn("PG_TEST_DSN", catalog)
        self.assertIn("pg_advisory_xact_lock", lock)
        self.assertIn("pg_try_advisory_xact_lock", lock)
        self.assertIn("transaction advisory lock not released", lock)
        aborted = (ROOT / "tests/pg17-migration-lock-abort-e2e.bash").read_text(
            encoding="utf-8")
        self.assertIn("ROLLBACK;", aborted)
        self.assertIn("transaction advisory lock not released on ROLLBACK", aborted)
        for script in ("tests/pg17-catalog-readback-e2e.bash",
                       "tests/pg17-migration-lock-e2e.bash",
                       "tests/pg17-migration-lock-abort-e2e.bash"):
            self.assertIn(script, workflow)

    def test_catalog_nested_unknown_fields_and_missing_keys(self):
        """Host-only closed-envelope regression, no SQL/DDL interpretation."""
        selectors = (
            ("catalog", lambda doc: doc, ("schema_version", "tables")),
            ("table", lambda doc: doc["tables"][0], ("stable_id", "name", "columns")),
            ("column", lambda doc: doc["tables"][0]["columns"][0],
             ("stable_id", "name", "kind", "nullable")),
        )
        for level, select, required in selectors:
            with self.subTest(level=level, mutation="unknown-field"):
                candidate = copy.deepcopy(self.current)
                select(candidate)["migration_sql"] = "DROP TABLE users"
                with self.assertRaises(ValidationError):
                    self.validator.validate(candidate)
            for field in required:
                with self.subTest(level=level, mutation="missing", field=field):
                    candidate = copy.deepcopy(self.current)
                    del select(candidate)[field]
                    with self.assertRaises(ValidationError):
                        self.validator.validate(candidate)


    def test_catalog_scalar_type_confusion_is_not_coerced(self):
        """JSON booleans, numbers, arrays and null cannot masquerade as text."""
        probes = (
            (lambda d: d, "schema_version", (None, 0, False, [], {})),
            (lambda d: d["tables"][0], "stable_id", (None, 0, True, [], {})),
            (lambda d: d["tables"][0], "name", (None, 1, False, [], {})),
            (lambda d: d["tables"][0]["columns"][0], "kind",
             (None, 0, False, [], {}, "UUID", "text")),
            (lambda d: d["tables"][0]["columns"][0], "nullable",
             (None, 0, 1, "true", "false", [], {})),
        )
        for select, field, values in probes:
            for value in values:
                with self.subTest(field=field, value=repr(value)):
                    candidate = copy.deepcopy(self.current)
                    select(candidate)[field] = value
                    with self.assertRaises(ValidationError):
                        self.validator.validate(candidate)


    def test_identifier_bypass_matrix_at_every_catalog_level(self):
        """Every schema identity slot rejects control, confusable and SQL shapes."""
        bad = (
            "", "9start", "with space", "a.b", "a/b", "a-b", "a|b",
            "a\\x00b", "a\\nb", "a\\tb", "a\\x7fb", "é", "e\\u0301",
            "ｕsers", "a\\u200db", "a\\u202eb", "a;DROP", "a\\\"b",
            "a" * 64,
        )
        selectors = (
            (lambda d: d["tables"][0], "stable_id"),
            (lambda d: d["tables"][0], "name"),
            (lambda d: d["tables"][0]["columns"][0], "stable_id"),
            (lambda d: d["tables"][0]["columns"][0], "name"),
        )
        for select, field in selectors:
            for value in bad:
                with self.subTest(field=field, bad=repr(value)):
                    candidate = copy.deepcopy(self.current)
                    select(candidate)[field] = value
                    with self.assertRaises(ValidationError):
                        self.validator.validate(candidate)
            for value in ("_", "A_0", "x" * 63):
                with self.subTest(field=field, good=value[:12]):
                    candidate = copy.deepcopy(self.current)
                    select(candidate)[field] = value
                    self.validator.validate(candidate)


    def test_structural_schema_does_not_certify_identity_uniqueness(self):
        """Duplicate IDs/names need the native checked-catalog admission gate.

        JSON Schema v1 is a structural envelope, not a stable-ID reconciliation
        ledger. If it accepts a duplicate, demand explicit native rejection
        code; an accepted JSON fixture must never become a migration approval.
        """
        base = self.current
        duplicates = []
        for field in ("stable_id", "name"):
            candidate = copy.deepcopy(base)
            second = copy.deepcopy(candidate["tables"][0])
            second[field] = candidate["tables"][0][field]
            second["stable_id" if field == "name" else "name"] = "distinct"
            candidate["tables"].append(second)
            duplicates.append(("table-" + field, candidate))
        for field in ("stable_id", "name"):
            candidate = copy.deepcopy(base)
            second = copy.deepcopy(candidate["tables"][0]["columns"][0])
            second[field] = candidate["tables"][0]["columns"][0][field]
            second["stable_id" if field == "name" else "name"] = "distinct"
            candidate["tables"][0]["columns"].append(second)
            duplicates.append(("column-" + field, candidate))
        native = (ROOT / "src/schema.ores").read_text(encoding="utf-8")
        guards = (
            "duplicate catalog table stable identity",
            "duplicate catalog physical table name",
            "duplicate schema column stable id",
            "duplicate schema column name",
        )
        for (kind, candidate), guard in zip(duplicates, guards):
            with self.subTest(kind=kind):
                # If future JSON Schema adds a uniqueness extension, this
                # assertion is still valid: native admission must remain.
                self.assertIn(guard, native)
                if self.validator.is_valid(candidate):
                    self.assertIn("pub fnc catalog_checked(", native)
                    self.assertIn("pub fnc table_checked(", native)


    def test_unmodelled_database_objects_are_not_catalog_authority(self):
        """v1 cannot authorize dropping PostgreSQL objects it cannot express."""
        self.validator.validate({"schema_version": "ores.orm.catalog/v1", "tables": []})
        for level, key in (
            ("catalog", "roles"), ("catalog", "permissions"),
            ("table", "primary_key"), ("table", "indexes"),
            ("table", "foreign_keys"), ("table", "policies"),
            ("table", "rls_enabled"), ("column", "default"),
            ("column", "generated"), ("column", "sql_type"),
        ):
            with self.subTest(level=level, key=key):
                candidate = copy.deepcopy(self.current)
                target = (candidate if level == "catalog" else
                          candidate["tables"][0] if level == "table" else
                          candidate["tables"][0]["columns"][0])
                target[key] = "trusted?"
                with self.assertRaises(ValidationError):
                    self.validator.validate(candidate)


    def test_review_preview_rejects_approval_and_sql_capability_fields(self):
        """Reject injected authority at manifest and step levels."""
        validator = Draft202012Validator(load("contracts/orm-plan-preview.schema.json"))
        base = load("contracts/examples/plan-preview.json")
        for key, value in (
            ("sql", "DROP TABLE users"), ("approval", "operator"),
            ("approved_by", "admin"), ("checksum", "forged"),
            ("migration_role", "postgres"), ("execution_token", "yes"),
            ("rollback_sql", "SELECT 1"), ("drift_accepted", True),
        ):
            for level in ("manifest", "step"):
                with self.subTest(level=level, key=key):
                    candidate = copy.deepcopy(base)
                    target = (candidate if level == "manifest" else
                              candidate["steps"][0])
                    target[key] = value
                    with self.assertRaises(ValidationError):
                        validator.validate(candidate)
        for field, values in (
            ("approved", (True, None, 0, 1, "false", [], {})),
            ("status", ("APPROVED", "APPLY", "", 0, None)),
            ("scope", ("full_catalog", "sql", "", None, 0)),
        ):
            for value in values:
                with self.subTest(field=field, value=repr(value)):
                    candidate = copy.deepcopy(base)
                    candidate[field] = value
                    with self.assertRaises(ValidationError):
                        validator.validate(candidate)


    def test_review_preview_step_type_and_required_field_matrix(self):
        validator = Draft202012Validator(load("contracts/orm-plan-preview.schema.json"))
        base = load("contracts/examples/plan-preview.json")
        for field in ("op", "table_id", "column_id", "risk"):
            candidate = copy.deepcopy(base)
            del candidate["steps"][0][field]
            with self.subTest(missing=field), self.assertRaises(ValidationError):
                validator.validate(candidate)
        for field in ("op", "table_id", "column_id", "risk"):
            for value in (None, False, 0, [], {}):
                candidate = copy.deepcopy(base)
                candidate["steps"][0][field] = value
                with self.subTest(field=field, value=repr(value)):
                    with self.assertRaises(ValidationError):
                        validator.validate(candidate)
        # All table-scoped operations forbid a synthetic column ID.
        for op, risk in (("review_table_rename", "manual"),
                         ("review_create_table", "manual"),
                         ("review_drop_table", "destructive")):
            candidate = copy.deepcopy(base)
            candidate["steps"] = [{"op": op, "table_id": "docs",
                                   "column_id": "forged", "risk": risk}]
            with self.subTest(op=op), self.assertRaises(ValidationError):
                validator.validate(candidate)


    def test_safe_risk_never_promotes_review_preview(self):
        """Even risk=safe remains a stopped, non-executable proposal."""
        validator = Draft202012Validator(load("contracts/orm-plan-preview.schema.json"))
        for op in ("add_nullable_column", "drop_not_null"):
            candidate = {
                "schema": "ores.orm.plan-preview/v1",
                "status": "STOPPED_FOR_EVALUATION",
                "approved": False,
                "scope": "column_shapes_only",
                "steps": [{"op": op, "table_id": "docs",
                           "column_id": "field", "risk": "safe"}],
            }
            with self.subTest(op=op):
                validator.validate(candidate)
                promoted = copy.deepcopy(candidate)
                promoted["approved"] = True
                with self.assertRaises(ValidationError):
                    validator.validate(promoted)
                promoted = copy.deepcopy(candidate)
                promoted["status"] = "APPROVED"
                with self.assertRaises(ValidationError):
                    validator.validate(promoted)


    def test_contract_schemas_only_use_local_references(self):
        """Validation must not require fetching arbitrary remote schema refs."""
        for path in ("contracts/orm-catalog.schema.json",
                     "contracts/orm-plan-preview.schema.json"):
            schema = load(path)
            Draft202012Validator.check_schema(schema)
            self.assertEqual(schema["$schema"],
                             "https://json-schema.org/draft/2020-12/schema")
            def walk(value):
                if isinstance(value, dict):
                    if "$ref" in value:
                        self.assertTrue(value["$ref"].startswith("#/$defs/"),
                                        (path, value["$ref"]))
                    for nested in value.values():
                        walk(nested)
                elif isinstance(value, list):
                    for nested in value:
                        walk(nested)
            walk(schema)



    def test_pg17_history_shell_syntax_and_sql_gate(self):
        """Host-only shell/SQL shape check; no PostgreSQL backend was called."""
        shell = shutil.which("bash")
        if shell is None:
            self.skipTest("bash unavailable")
        script = ROOT / "tests/pg17-migration-history-e2e.bash"
        proc = subprocess.run([shell, "-n", str(script)],
                              capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        sql = (ROOT / "tests/pg17-migration-history-e2e.sql").read_text(encoding="utf-8")
        for marker in (
            "BEGIN;", "ROLLBACK;", "CREATE TABLE applied_migrations",
            "CREATE FUNCTION record_migration", "MIGRATION_CHECKSUM_DRIFT",
            "MIGRATION_ORDER_DRIFT", "INVALID_MIGRATION_IDENTITY",
            "FORGED_REPLAY_NOT_REJECTED", "OUT_OF_ORDER_NOT_REJECTED",
            "INVALID_VERSION_NOT_REJECTED", "INVALID_DIGEST_NOT_REJECTED",
            "pg_catalog.pg_namespace", "GET STACKED DIAGNOSTICS",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, sql)
        self.assertNotIn("\nCOMMIT;", sql, "test must be rollback-only")
        workflow = (ROOT / ".github/workflows/pg17-ddl-integration.yml").read_text(
            encoding="utf-8")
        self.assertIn("tests/pg17-migration-history-e2e.bash", workflow)

    def test_pg17_history_missing_opt_in_never_contacts_psql(self):
        """A false success without explicit disposable opt-in is forbidden."""
        shell = shutil.which("bash")
        if shell is None:
            self.skipTest("bash unavailable")
        with tempfile.TemporaryDirectory() as tmp:
            directory = pathlib.Path(tmp)
            called = directory / "psql-called"
            fake = directory / "psql"
            fake.write_text(
                '#!/bin/sh\nprintf "called\\n" >> "$PG_MOCK_CONTACT"\n'
                'exit 0\n', encoding="utf-8")
            fake.chmod(0o755)
            env = os.environ.copy()
            env["PATH"] = str(directory) + os.pathsep + env.get("PATH", "")
            env["PG_MOCK_CONTACT"] = str(called)
            env["PG_TEST_DSN"] = "postgresql://invalid/db"
            env.pop("PG_TEST_DISPOSABLE", None)
            process = subprocess.run(
                [shell, str(ROOT / "tests/pg17-migration-history-e2e.bash")],
                env=env, capture_output=True, text=True, check=False)
            self.assertNotEqual(process.returncode, 0)
            self.assertIn("PG_HISTORY_E2E_NOT_VERIFIED:", process.stderr)
            self.assertFalse(called.exists(), "unauthorized database contacted")

    def test_pg17_history_fake_psql_receipt_mutations(self):
        """Real subprocess tests of parser gates; fake psql is not PG17."""
        shell = shutil.which("bash")
        if shell is None:
            self.skipTest("bash unavailable")
        with tempfile.TemporaryDirectory() as tmp:
            directory = pathlib.Path(tmp)
            fake = directory / "psql"
            fake.write_text(
                '#!/bin/sh\n'
                'case " $* " in\n'
                '  *" -c "*) printf "%s\\n" "$PG_MOCK_VERSION"; exit 0;;\n'
                'esac\n'
                'printf "%s\\n" "$PG_MOCK_RECEIPT"\n'
                'exit "${PG_MOCK_EXIT:-0}"\n',
                encoding="utf-8")
            fake.chmod(0o755)
            env = os.environ.copy()
            env["PATH"] = str(directory) + os.pathsep + env.get("PATH", "")
            env["PG_TEST_DSN"] = "postgresql://invalid/db"
            env["PG_TEST_DISPOSABLE"] = "I_ACKNOWLEDGE_DISPOSABLE_DATABASE"
            sep = chr(10)
            expected = sep.join(("APPLIED", "REPLAY_OK", "APPLIED", "2", "1",
                                 "PG17_MIGRATION_HISTORY_E2E_OK", "0"))
            script = str(ROOT / "tests/pg17-migration-history-e2e.bash")
            for version in ("160001", "180001", "seventeen", "17"):
                env["PG_MOCK_VERSION"] = version
                env["PG_MOCK_RECEIPT"] = expected
                with self.subTest(version=version):
                    proc = subprocess.run([shell, script], env=env,
                                          capture_output=True, text=True)
                    self.assertNotEqual(proc.returncode, 0)
                    self.assertIn("PG_HISTORY_E2E_NOT_VERIFIED:", proc.stderr)
            env["PG_MOCK_VERSION"] = "170001"
            for label, receipt, code in (
                ("correct-mock", expected, 0),
                ("missing-replay", expected.replace("REPLAY_OK" + sep, ""), 1),
                ("truncated", expected.rsplit(sep, 1)[0], 1),
                ("wrong-count", expected.replace(sep + "2" + sep + "1" + sep, sep + "3" + sep + "1" + sep), 1),
                ("unexpected-success", "APPROVED", 1),
            ):
                env["PG_MOCK_RECEIPT"] = receipt
                env["PG_MOCK_EXIT"] = "0"
                with self.subTest(case=label):
                    proc = subprocess.run([shell, script], env=env,
                                          capture_output=True, text=True)
                    self.assertEqual(proc.returncode == 0, code == 0, proc.stderr)
                    if code != 0:
                        self.assertIn("PG_HISTORY_E2E_NOT_VERIFIED:", proc.stderr)
            env["PG_MOCK_RECEIPT"] = expected
            env["PG_MOCK_EXIT"] = "42"
            proc = subprocess.run([shell, script], env=env,
                                  capture_output=True, text=True)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("PG_HISTORY_E2E_NOT_VERIFIED:", proc.stderr)



    def test_pg17_lock_host_fault_injection_commit_and_rollback(self):
        """Run fake two-process lock failures, never a real PG17 server."""
        shell = shutil.which("bash")
        if shell is None:
            self.skipTest("bash unavailable")
        with tempfile.TemporaryDirectory() as tmp:
            home = pathlib.Path(tmp)
            fake = home / "psql"
            fake.write_text("""#!/usr/bin/env bash
set -euo pipefail
if [[ "$*" == *'SHOW server_version_num'* ]]; then
  echo 170005
  exit 0
fi
query="$(cat)"
if [[ "$query" == *'SELECT pg_advisory_xact_lock('* ]]; then
  touch "$MOCK_LOCK_STARTED" "$MOCK_LOCK_FILE"
  sleep 0.25
  rm -f "$MOCK_LOCK_FILE"
  exit "${MOCK_HOLDER_EXIT:-0}"
fi
if [[ "$query" == *'SELECT pg_try_advisory_xact_lock('* ]]; then
  # Synchronize the fake holder before injecting a bogus result, so a
  # nonzero result cannot pass merely because the holder never started.
  for _ in {1..100}; do
    if [[ -f "$MOCK_LOCK_STARTED" ]]; then break; fi
    sleep 0.01
  done
  if [[ "${MOCK_BAD_TRY:-}" == yes ]]; then echo invalid; exit 0; fi
  if [[ "${MOCK_STUCK_LOCK:-}" == yes || -f "$MOCK_LOCK_FILE" ]]; then
    echo f
  else
    echo t
  fi
  exit 0
fi
echo UNEXPECTED_FAKE_SQL >&2
exit 99
""", encoding="utf-8")
            fake.chmod(0o755)
            env_base = os.environ.copy()
            env_base["PATH"] = str(home) + os.pathsep + env_base.get("PATH", "")
            env_base["PG_TEST_DSN"] = "postgresql://fake/db"
            env_base["PG_TEST_DISPOSABLE"] = "I_ACKNOWLEDGE_DISPOSABLE_DATABASE"
            env_base["MOCK_LOCK_FILE"] = str(home / "active-lock")
            env_base["MOCK_LOCK_STARTED"] = str(home / "lock-started")
            scripts = ("pg17-migration-lock-e2e.bash",
                       "pg17-migration-lock-abort-e2e.bash")
            cases = (
                ("commit-or-rollback-release", {}, True),
                ("holder-failure", {"MOCK_HOLDER_EXIT": "41"}, False),
                ("unrecognized-try-lock-result", {"MOCK_BAD_TRY": "yes"}, False),
                ("lock-not-released", {"MOCK_STUCK_LOCK": "yes"}, False),
            )
            for script in scripts:
                for label, overrides, accepted in cases:
                    with self.subTest(script=script, case=label):
                        for marker in ("active-lock", "lock-started"):
                            (home / marker).unlink(missing_ok=True)
                        env = env_base.copy()
                        env.update(overrides)
                        proc = subprocess.run(
                            [shell, str(ROOT / "tests" / script)],
                            env=env, capture_output=True, text=True,
                            check=False, timeout=20,
                        )
                        self.assertEqual(proc.returncode == 0, accepted,
                                         proc.stderr)
                        self.assertTrue((home / "lock-started").exists(),
                                        "mock holder never started")
                        if accepted:
                            self.assertIn("_SQL_ONLY_PASS", proc.stdout)
                        else:
                            self.assertIn("PG_LOCK_E2E_NOT_VERIFIED:", proc.stderr)

    def test_pg17_history_savepoint_recovery_contract_is_authored(self):
        """Source-level coverage only; cannot certify SQL execution."""
        source = (ROOT / "tests/pg17-migration-history-e2e.sql").read_text(
            encoding="utf-8")
        for marker in (
            "SAVEPOINT aborted_migration;",
            "ROLLBACK TO SAVEPOINT aborted_migration;",
            "RELEASE SAVEPOINT aborted_migration;",
            "TRANSIENT_APPLY_NOT_NEW",
            "TRANSIENT_REPLAY_NOT_STABLE",
            "ABORTED_LEDGER_ROW_SURVIVED",
            "ABORTED_LEDGER_VERSION_SURVIVED",
            "RECOVERY_PROBE_LEFT_LEDGER_ROW",
            "UNDO_RECOVERY_PROBE",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)
        self.assertEqual(source.count("\nROLLBACK;\n"), 1)

if __name__ == "__main__":
    unittest.main()
