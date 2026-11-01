"""Deterministic host-only differential tests for the review-only ORM contracts.

This is structural JSON Schema testing, not TypeSpec compiler, native Oreslang,
PostgreSQL driver, RLS, or migration-executor evidence. In particular, catalog
identity uniqueness requires separate native admission checks.
"""
import copy
import json
import pathlib
import random
import re
import unittest

from jsonschema import Draft202012Validator

ROOT = pathlib.Path(__file__).resolve().parents[1]
NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
KINDS = frozenset(("uuid", "string", "int32", "int64", "boolean", "json", "timestamp", "bytes"))
RISKS = {
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
TABLE_OPS = frozenset(("review_table_rename", "review_create_table", "review_drop_table"))


def exact_keys(obj, expected):
    return type(obj) is dict and set(obj) == set(expected)


def admitted_name(value):
    return type(value) is str and 1 <= len(value) <= 63 and NAME.fullmatch(value) is not None


def column_oracle(col):
    return (exact_keys(col, ("stable_id", "name", "kind", "nullable"))
            and admitted_name(col["stable_id"]) and admitted_name(col["name"])
            and type(col["kind"]) is str and col["kind"] in KINDS
            and type(col["nullable"]) is bool)


def table_oracle(table):
    return (exact_keys(table, ("stable_id", "name", "columns"))
            and admitted_name(table["stable_id"]) and admitted_name(table["name"])
            and type(table["columns"]) is list
            and 1 <= len(table["columns"]) <= 64
            and all(column_oracle(col) for col in table["columns"]))


def catalog_oracle(catalog):
    return (exact_keys(catalog, ("schema_version", "tables"))
            and catalog["schema_version"] == "ores.orm.catalog/v1"
            and type(catalog["schema_version"]) is str
            and type(catalog["tables"]) is list
            and len(catalog["tables"]) <= 256
            and all(table_oracle(table) for table in catalog["tables"]))


def preview_oracle(manifest):
    if not exact_keys(manifest, ("schema", "status", "approved", "scope", "steps")):
        return False
    if (manifest["schema"] != "ores.orm.plan-preview/v1"
            or manifest["status"] != "STOPPED_FOR_EVALUATION"
            or manifest["approved"] is not False
            or manifest["scope"] != "column_shapes_only"
            or type(manifest["steps"]) is not list or len(manifest["steps"]) > 2048):
        return False
    for step in manifest["steps"]:
        if not exact_keys(step, ("op", "table_id", "column_id", "risk")):
            return False
        op = step["op"]
        if type(op) is not str or op not in RISKS or step["risk"] != RISKS[op]:
            return False
        if not admitted_name(step["table_id"]):
            return False
        if op in TABLE_OPS:
            if step["column_id"] != "" or type(step["column_id"]) is not str:
                return False
        elif not admitted_name(step["column_id"]):
            return False
    return True


class DifferentialHostOracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def read(path):
            return json.loads((ROOT / path).read_text(encoding="utf-8"))
        cls.catalog_schema = read("contracts/orm-catalog.schema.json")
        cls.preview_schema = read("contracts/orm-plan-preview.schema.json")
        Draft202012Validator.check_schema(cls.catalog_schema)
        Draft202012Validator.check_schema(cls.preview_schema)
        cls.catalog_validator = Draft202012Validator(cls.catalog_schema)
        cls.preview_validator = Draft202012Validator(cls.preview_schema)
        cls.catalog_example = read("contracts/examples/current.catalog.json")
        cls.preview_example = read("contracts/examples/plan-preview.json")

    def check_catalog(self, candidate, label):
        self.assertEqual(self.catalog_validator.is_valid(candidate), catalog_oracle(candidate), label)

    def check_preview(self, candidate, label):
        self.assertEqual(self.preview_validator.is_valid(candidate), preview_oracle(candidate), label)

    def test_catalog_deterministic_mutation_oracle(self):
        rng = random.Random(0xC0A7A10)
        values = ("", "_", "valid_9", "a" * 63, "a" * 64, "ok\n", "ok\r\n",
                  "x\u2028", "x\u200d", "é", "\x00", "x.y", "x;DROP", True,
                  False, None, 0, 1, [], {}, "uuid", "UTF8")
        for index in range(700):
            candidate = copy.deepcopy(self.catalog_example)
            table = candidate["tables"][0]
            column = table["columns"][0]
            mutation = rng.randrange(15)
            value = copy.deepcopy(rng.choice(values))
            if mutation == 0:
                candidate["schema_version"] = value
            elif mutation == 1:
                candidate["tables"] = value
            elif mutation == 2:
                candidate["schema_sql"] = value
            elif mutation == 3:
                table["stable_id"] = value
            elif mutation == 4:
                table["name"] = value
            elif mutation == 5:
                table["columns"] = value
            elif mutation == 6:
                table["primary_key"] = value
            elif mutation == 7:
                column["stable_id"] = value
            elif mutation == 8:
                column["name"] = value
            elif mutation == 9:
                column["kind"] = value
            elif mutation == 10:
                column["nullable"] = value
            elif mutation == 11:
                column["sql"] = value
            elif mutation == 12:
                del column[rng.choice(tuple(column))]
            elif mutation == 13:
                del table[rng.choice(tuple(table))]
            else:
                # Duplicates are structurally valid: this is NOT a stable-ID ledger.
                table["columns"].append(copy.deepcopy(table["columns"][0]))
            with self.subTest(seed="C0A7A10", case=index, mutation=mutation):
                self.check_catalog(candidate, (index, mutation, repr(value)))

    def test_preview_exhaustive_operation_risk_and_scope_oracle(self):
        for operation in RISKS:
            for risk in ("safe", "preflight", "manual", "destructive"):
                for column_id in ("", "field", "field\n", "a" * 64):
                    for table_id in ("valid", "valid\n"):
                        candidate = copy.deepcopy(self.preview_example)
                        candidate["steps"] = [{"op": operation, "risk": risk,
                                               "table_id": table_id,
                                               "column_id": column_id}]
                        with self.subTest(op=operation, risk=risk,
                                          column=repr(column_id), table=repr(table_id)):
                            self.check_preview(candidate, (operation, risk, column_id, table_id))

    def test_preview_deterministic_authority_fuzz(self):
        rng = random.Random(0xA99A0)
        payloads = (True, False, None, 0, 1, "APPROVED", "STOPPED_FOR_EVALUATION",
                    "column_shapes_only", "full_catalog", "", [], {},
                    "DROP TABLE users", "x\n")
        for index in range(500):
            candidate = copy.deepcopy(self.preview_example)
            mutation = rng.randrange(13)
            value = copy.deepcopy(rng.choice(payloads))
            if mutation == 0:
                candidate["approved"] = value
            elif mutation == 1:
                candidate["status"] = value
            elif mutation == 2:
                candidate["scope"] = value
            elif mutation == 3:
                candidate["schema"] = value
            elif mutation == 4:
                candidate["steps"] = value
            elif mutation == 5:
                candidate["sql"] = value
            elif mutation == 6:
                candidate["execution_token"] = value
            elif mutation == 7:
                candidate["steps"][0]["op"] = value
            elif mutation == 8:
                candidate["steps"][0]["risk"] = value
            elif mutation == 9:
                candidate["steps"][0]["table_id"] = value
            elif mutation == 10:
                candidate["steps"][0]["column_id"] = value
            elif mutation == 11:
                candidate["steps"][0]["sql"] = value
            else:
                del candidate["steps"][0][rng.choice(tuple(candidate["steps"][0]))]
            with self.subTest(seed="A99A0", case=index, mutation=mutation):
                self.check_preview(candidate, (index, mutation, repr(value)))

    def test_legal_empty_review_remains_non_authorizing(self):
        empty = copy.deepcopy(self.preview_example)
        empty["steps"] = []
        self.check_preview(empty, "empty-review-valid-but-never-approved")
        for field, value in (("approved", True), ("status", "APPLY"),
                             ("scope", "full_catalog"),
                             ("sql", "DROP TABLE users")):
            changed = copy.deepcopy(empty)
            changed[field] = value
            with self.subTest(field=field):
                self.check_preview(changed, "empty-review-unauthorized-" + field)
                self.assertFalse(self.preview_validator.is_valid(changed))

    def test_duplicate_stable_ids_are_outside_structural_schema_authority(self):
        candidate = copy.deepcopy(self.catalog_example)
        candidate["tables"].append(copy.deepcopy(candidate["tables"][0]))
        self.check_catalog(candidate, "duplicates-not-validated-by-structural-contract")
        self.assertTrue(self.catalog_validator.is_valid(candidate))
        # Native schema.catalog_checked must independently reject this input.
        source = (ROOT / "src/schema.ores").read_text(encoding="utf-8")
        self.assertIn("duplicate catalog table stable identity", source)
        self.assertIn("duplicate catalog physical table name", source)
