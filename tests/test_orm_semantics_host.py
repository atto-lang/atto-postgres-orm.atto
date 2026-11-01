"""Host-only cross-item semantic tests; NOT native, DPM or PostgreSQL proof."""
import copy
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
from orm_semantics_host import check_catalog_semantics, check_review_semantics


def step(op, table="accounts", column="name"):
    risks = {
        "review_table_rename": "manual", "review_create_table": "manual",
        "review_drop_table": "destructive", "review_column_rename": "manual",
        "review_type_change": "manual", "drop_not_null": "safe",
        "add_nullable_column": "safe", "set_not_null": "preflight",
        "add_required_column": "preflight", "drop_column": "destructive",
    }
    if op.startswith("review_") and op in {
        "review_table_rename", "review_create_table", "review_drop_table"
    }:
        column = ""
    return {"op": op, "table_id": table, "column_id": column,
            "risk": risks[op]}


def plan(*steps):
    return {"schema": "ores.orm.plan-preview/v1",
            "status": "STOPPED_FOR_EVALUATION", "approved": False,
            "scope": "column_shapes_only", "steps": list(steps)}


def catalog():
    return {"schema_version": "ores.orm.catalog/v1", "tables": [
        {"stable_id": "accounts", "name": "accounts", "columns": [
            {"stable_id": "id", "name": "id", "kind": "uuid", "nullable": False},
            {"stable_id": "name", "name": "name", "kind": "string", "nullable": True},
        ]}
    ]}


class PortableSemanticHostTests(unittest.TestCase):
    def test_valid_catalog_and_reordering(self):
        obj = catalog()
        check_catalog_semantics(obj)
        obj["tables"][0]["columns"].reverse()
        check_catalog_semantics(obj)

    def test_duplicate_table_stable_id_and_physical_name(self):
        for field in ("stable_id", "name"):
            obj = catalog()
            duplicate = copy.deepcopy(obj["tables"][0])
            duplicate["stable_id"] = "different_id"
            duplicate["name"] = "different_name"
            duplicate[field] = obj["tables"][0][field]
            obj["tables"].append(duplicate)
            with self.subTest(field=field), self.assertRaises(ValueError):
                check_catalog_semantics(obj)

    def test_duplicate_column_stable_id_and_physical_name(self):
        for field in ("stable_id", "name"):
            obj = catalog()
            duplicate = copy.deepcopy(obj["tables"][0]["columns"][0])
            duplicate["stable_id"] = "other_id"
            duplicate["name"] = "other_name"
            duplicate[field] = obj["tables"][0]["columns"][0][field]
            obj["tables"][0]["columns"].append(duplicate)
            with self.subTest(field=field), self.assertRaises(ValueError):
                check_catalog_semantics(obj)

    def test_exclusive_table_operations_are_order_independent(self):
        for op in ("review_create_table", "review_drop_table"):
            for other in ("review_table_rename", "review_type_change", "review_drop_table"):
                if op == other:
                    continue
                for pair in ((step(op), step(other)), (step(other), step(op))):
                    with self.subTest(op=op, other=other), self.assertRaises(ValueError):
                        check_review_semantics(plan(*pair))

    def test_exclusive_column_operations_are_order_independent(self):
        for op in ("drop_column", "add_nullable_column", "add_required_column"):
            for other in ("review_column_rename", "review_type_change", "drop_not_null", "set_not_null"):
                for pair in ((step(op), step(other)), (step(other), step(op))):
                    with self.subTest(op=op, other=other), self.assertRaises(ValueError):
                        check_review_semantics(plan(*pair))

    def test_opposite_nullability_and_duplicate_steps(self):
        for pair in ((step("drop_not_null"), step("set_not_null")),
                     (step("set_not_null"), step("drop_not_null")),
                     (step("drop_column"), step("drop_column"))):
            with self.assertRaises(ValueError):
                check_review_semantics(plan(*pair))

    def test_legitimate_multi_change_and_independent_tables(self):
        check_review_semantics(plan(step("review_table_rename"),
                                    step("review_column_rename"),
                                    step("review_type_change"),
                                    step("set_not_null")))
        check_review_semantics(plan(step("review_drop_table", "legacy"),
                                    step("review_create_table", "new_accounts")))
        check_review_semantics(plan(step("drop_column", "accounts", "old"),
                                    step("review_column_rename", "accounts", "name")))

    def test_empty_manifest_and_catalog_admitted(self):
        check_review_semantics(plan())
        check_catalog_semantics({"schema_version": "ores.orm.catalog/v1", "tables": []})


if __name__ == "__main__":
    unittest.main()
