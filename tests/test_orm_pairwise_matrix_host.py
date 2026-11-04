"""Deterministic host-only metamorphic matrix for ORM v1 review semantics.

An independent pairwise oracle is used to test the Python semantic checker.
It does NOT execute Oreslang, TypeSpec, PostgreSQL, or migration SQL.
"""

import copy
import itertools
import pathlib
import random
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
from orm_semantics_host import check_catalog_semantics, check_review_semantics

# Independent table of 10 versioned operations (not imported from the checker).
RISK = {
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
TABLE_ONLY = ("review_table_rename", "review_create_table", "review_drop_table")


def step(operation, table="one", column="field"):
    return {"op": operation, "table_id": table,
            "column_id": "" if operation in TABLE_ONLY else column,
            "risk": RISK[operation]}


def manifest(steps):
    return {"schema": "ores.orm.plan-preview/v1",
            "status": "STOPPED_FOR_EVALUATION", "approved": False,
            "scope": "column_shapes_only", "steps": copy.deepcopy(steps)}


def oracle_conflict(a, b):
    """Independent operation-pair policy, without using checker constants."""
    if a["table_id"] != b["table_id"]:
        return False
    if a["op"] == b["op"] and a["column_id"] == b["column_id"]:
        return True
    if a["op"] in ("review_create_table", "review_drop_table"):
        return True
    if b["op"] in ("review_create_table", "review_drop_table"):
        return True
    if not a["column_id"] or a["column_id"] != b["column_id"]:
        return False
    if a["op"] in ("drop_column", "add_nullable_column", "add_required_column"):
        return True
    if b["op"] in ("drop_column", "add_nullable_column", "add_required_column"):
        return True
    return {a["op"], b["op"]} == {"drop_not_null", "set_not_null"}


class ReviewOperationMatrixTests(unittest.TestCase):
    def assert_policy(self, steps, conflict):
        before = copy.deepcopy(steps)
        if conflict:
            with self.assertRaises(ValueError):
                check_review_semantics(manifest(steps))
        else:
            self.assertIsNone(check_review_semantics(manifest(steps)))
        self.assertEqual(steps, before, "caller-provided steps were mutated")

    def test_complete_ordered_ten_by_ten_same_table_same_column(self):
        for left, right in itertools.product(RISK, repeat=2):
            a, b = step(left), step(right)
            with self.subTest(left=left, right=right):
                self.assert_policy([a, b], oracle_conflict(a, b))

    def test_complete_ordered_ten_by_ten_independent_tables(self):
        for left, right in itertools.product(RISK, repeat=2):
            a, b = step(left, "table_a"), step(right, "table_b")
            with self.subTest(left=left, right=right):
                self.assert_policy([a, b], False)

    def test_complete_ordered_ten_by_ten_different_columns(self):
        for left, right in itertools.product(RISK, repeat=2):
            a, b = step(left, column="col_a"), step(right, column="col_b")
            with self.subTest(left=left, right=right):
                self.assert_policy([a, b], oracle_conflict(a, b))

    def test_legal_rename_type_nullability_and_drop_other_column(self):
        bundle = [step("review_table_rename"), step("review_column_rename"),
                  step("review_type_change"), step("set_not_null"),
                  step("drop_column", column="obsolete")]
        for seed in range(80):
            sample = copy.deepcopy(bundle)
            random.Random(seed).shuffle(sample)
            with self.subTest(seed=seed):
                self.assert_policy(sample, False)

    def test_conflict_detection_does_not_depend_on_step_distance(self):
        noise = [step("review_type_change", "noise_" + str(i)) for i in range(60)]
        cases = [
            (step("review_drop_table"), step("review_type_change")),
            (step("add_nullable_column"), step("drop_column")),
            (step("drop_not_null"), step("set_not_null")),
            (step("review_create_table"), step("review_table_rename")),
        ]
        for a, b in cases:
            for reverse in (False, True):
                ordered = [b, *noise, a] if reverse else [a, *noise, b]
                with self.subTest(a=a["op"], b=b["op"], reverse=reverse):
                    self.assert_policy(ordered, True)

    def test_duplicate_cannot_hide_after_other_tables(self):
        first = step("review_column_rename", "one", "field")
        others = [step("review_column_rename", "table_" + str(i)) for i in range(150)]
        self.assert_policy([first, *others, copy.deepcopy(first)], True)

    def test_review_host_checker_is_not_an_approval_or_shape_validator(self):
        # An unsafe risk, malformed identifier, or forged approval is handled
        # by JSON Schema admission, NOT check_review_semantics(). Never treat
        # successful semantic-only validation as migration authorization.
        forged = manifest([step("drop_column")])
        forged["steps"][0]["risk"] = "safe"
        forged["approved"] = True
        self.assertIsNone(check_review_semantics(forged))
        self.assertTrue(forged["approved"])

    def test_empty_and_disjoint_review_sets_are_legal(self):
        self.assert_policy([], False)
        independent = [step("review_drop_table", "drop_" + str(i)) for i in range(150)]
        self.assert_policy(independent, False)

    def test_table_stable_ids_and_physical_names_are_scoped(self):
        original = {"tables": [{"stable_id": "t1", "name": "one",
                                "columns": [{"stable_id": "id", "name": "id"}]},
                               {"stable_id": "t2", "name": "two",
                                "columns": [{"stable_id": "id", "name": "id"}]}]}
        check_catalog_semantics(original)
        for table_key in ("stable_id", "name"):
            candidate = copy.deepcopy(original)
            candidate["tables"][1][table_key] = candidate["tables"][0][table_key]
            with self.subTest(table_key=table_key), self.assertRaises(ValueError):
                check_catalog_semantics(candidate)

    def test_column_stable_ids_and_physical_names_are_independent(self):
        original = {"tables": [{"stable_id": "t1", "name": "one",
                                "columns": [{"stable_id": "id", "name": "id"},
                                            {"stable_id": "name", "name": "name"}]}]}
        check_catalog_semantics(original)
        for field in ("stable_id", "name"):
            candidate = copy.deepcopy(original)
            candidate["tables"][0]["columns"][1][field] = "id"
            with self.subTest(field=field), self.assertRaises(ValueError):
                check_catalog_semantics(candidate)


if __name__ == "__main__":
    unittest.main()
