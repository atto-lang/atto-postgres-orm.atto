"""Host-only validation of portable catalog fixtures. Not native Oreslang proof.

The TypeSpec/JSON Schema peer-semantic comparison is a separate TJSV gate;
these tests deliberately do not claim to replace it.
"""
import copy
import json
import pathlib
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


if __name__ == "__main__":
    unittest.main()
