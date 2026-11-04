"""End-to-end HOST-ONLY schema+semantic JSON admission regression tests.

These tests cannot certify native Oreslang, TypeSpec semantic parity, SQL,
or live PostgreSQL introspection. A successful admission is NEVER approval.
"""
import copy
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from orm_admission_host import AdmissionError, MAX_BYTES, admit_json

SCRIPT = ROOT / "scripts" / "orm_admission_host.py"


def catalog():
    return {"schema_version": "ores.orm.catalog/v1", "tables": [
        {"stable_id": "users", "name": "users", "columns": [
            {"stable_id": "id", "name": "id", "kind": "uuid", "nullable": False},
            {"stable_id": "name", "name": "name", "kind": "string", "nullable": True},
        ]}
    ]}


def step(op, table="users", column="name"):
    risk = {
        "review_table_rename": "manual", "review_create_table": "manual",
        "review_drop_table": "destructive", "review_column_rename": "manual",
        "review_type_change": "manual", "drop_not_null": "safe",
        "add_nullable_column": "safe", "set_not_null": "preflight",
        "add_required_column": "preflight", "drop_column": "destructive",
    }
    if op in ("review_table_rename", "review_create_table", "review_drop_table"):
        column = ""
    return {"op": op, "table_id": table, "column_id": column, "risk": risk[op]}


def review(steps=None):
    return {"schema": "ores.orm.plan-preview/v1",
            "status": "STOPPED_FOR_EVALUATION", "approved": False,
            "scope": "column_shapes_only",
            "steps": [] if steps is None else steps}


def encode(data):
    return json.dumps(data, ensure_ascii=True, separators=(",", ":")).encode("utf-8")


class IntegratedReviewAdmissionTests(unittest.TestCase):
    def assert_rejected(self, obj, kind):
        with self.assertRaises(AdmissionError):
            admit_json(encode(obj), kind)

    def test_valid_empty_and_nonempty_envelopes(self):
        for kind, candidate in (
            ("catalog", {"schema_version": "ores.orm.catalog/v1", "tables": []}),
            ("catalog", catalog()),
            ("review", review()),
            ("review", review([step("review_drop_table")]))):
            with self.subTest(kind=kind, candidate=candidate):
                self.assertEqual(admit_json(encode(candidate), kind), candidate)

    def test_malformed_json_and_non_utf8_refused(self):
        for raw in (b"", b"{", b"{} trailing", b"\xff", b"\xef\xbb\xbf{}",
                    b"[" * 1100 + b"0" + b"]" * 1100):
            with self.subTest(raw=raw[:24]), self.assertRaises(AdmissionError):
                admit_json(raw, "review")

    def test_duplicate_top_level_json_members_refused(self):
        raw = (b'{"schema_version":"ores.orm.catalog/v1",'
               b'"schema_version":"ores.orm.catalog/v1","tables":[]}')
        with self.assertRaisesRegex(AdmissionError, "duplicate JSON member"):
            admit_json(raw, "catalog")

    def test_escaped_duplicate_member_is_duplicate(self):
        raw = (b'{"schema":"ores.orm.plan-preview/v1",'
               b'"\\u0073chema":"ores.orm.plan-preview/v1",'
               b'"status":"STOPPED_FOR_EVALUATION","approved":false,'
               b'"scope":"column_shapes_only","steps":[]}')
        with self.assertRaisesRegex(AdmissionError, "duplicate JSON member"):
            admit_json(raw, "review")

    def test_nested_duplicate_column_member_refused(self):
        raw = encode(catalog()).replace(b'"kind":"uuid"',
                                        b'"kind":"uuid","kind":"int64"', 1)
        with self.assertRaisesRegex(AdmissionError, "duplicate JSON member"):
            admit_json(raw, "catalog")

    def test_non_standard_nan_infinity_refused(self):
        for token in (b"NaN", b"Infinity", b"-Infinity"):
            raw = encode(catalog()).replace(b'"nullable":false',
                                            b'"nullable":' + token, 1)
            with self.subTest(token=token), self.assertRaises(AdmissionError):
                admit_json(raw, "catalog")

    def test_input_type_kind_and_size_fail_closed(self):
        for wrong in (None, {}, "{}", bytearray(b"{}")):
            with self.subTest(type=str(type(wrong))), self.assertRaises(AdmissionError):
                admit_json(wrong, "catalog")
        with self.assertRaises(AdmissionError):
            admit_json(encode(catalog()), "../../../other")
        with self.assertRaises(AdmissionError):
            admit_json(b" " * (MAX_BYTES + 1), "catalog")

    def test_duplicate_catalog_table_stable_id_or_name_refused(self):
        for field in ("stable_id", "name"):
            obj = catalog()
            dup = copy.deepcopy(obj["tables"][0])
            dup["stable_id"] = "different"
            dup["name"] = "different"
            dup[field] = obj["tables"][0][field]
            obj["tables"].append(dup)
            with self.subTest(field=field):
                self.assert_rejected(obj, "catalog")

    def test_duplicate_catalog_column_stable_id_or_name_refused(self):
        for field in ("stable_id", "name"):
            obj = catalog()
            dup = copy.deepcopy(obj["tables"][0]["columns"][0])
            dup["stable_id"] = "another"
            dup["name"] = "another"
            dup[field] = obj["tables"][0]["columns"][0][field]
            obj["tables"][0]["columns"].append(dup)
            with self.subTest(field=field):
                self.assert_rejected(obj, "catalog")

    def test_same_column_ids_on_different_tables_allowed(self):
        obj = catalog()
        other = copy.deepcopy(obj["tables"][0])
        other["stable_id"] = "other"
        other["name"] = "other"
        obj["tables"].append(other)
        self.assertEqual(admit_json(encode(obj), "catalog"), obj)

    def test_unsafe_column_identity_and_kind_refused(self):
        for field, bad in (("stable_id", "é"), ("name", "a.b"),
                           ("name", "1leading"), ("name", "x" * 64),
                           ("kind", "DROP TABLE"), ("nullable", "false")):
            obj = catalog()
            obj["tables"][0]["columns"][0][field] = bad
            with self.subTest(field=field, bad=bad):
                self.assert_rejected(obj, "catalog")

    def test_terminal_line_breaks_denied_in_all_stable_id_fields(self):
        for ending in ("\n", "\r", "\u2028", "\u2029"):
            for field in ("stable_id", "name"):
                obj = catalog()
                obj["tables"][0][field] = "valid" + ending
                with self.subTest(kind="table", field=field, ending=repr(ending)):
                    self.assert_rejected(obj, "catalog")
                obj = catalog()
                obj["tables"][0]["columns"][0][field] = "valid" + ending
                with self.subTest(kind="column", field=field, ending=repr(ending)):
                    self.assert_rejected(obj, "catalog")
            for field, operation in (("table_id", "review_drop_table"),
                                     ("column_id", "drop_column")):
                obj = review([step(operation)])
                obj["steps"][0][field] = "valid" + ending
                with self.subTest(kind="review", field=field, ending=repr(ending)):
                    self.assert_rejected(obj, "review")
            obj = review([step("review_drop_table")])
            obj["steps"][0]["column_id"] = ending
            with self.subTest(kind="empty-column-id", ending=repr(ending)):
                self.assert_rejected(obj, "review")

    def test_unknown_fields_and_version_refused(self):
        for kind, original in (("catalog", catalog()), ("review", review())):
            obj = copy.deepcopy(original)
            obj["sql"] = "DROP TABLE users"
            self.assert_rejected(obj, kind)
        obj = catalog()
        obj["schema_version"] = "ores.orm.catalog/v2"
        self.assert_rejected(obj, "catalog")

    def test_forged_review_authorization_and_scope_refused(self):
        for field, value in (("approved", True), ("status", "APPROVED"),
                             ("scope", "all_tables")):
            obj = review([step("review_drop_table")])
            obj[field] = value
            with self.subTest(field=field):
                self.assert_rejected(obj, "review")

    def test_wrong_risk_and_wrong_column_scope_refused(self):
        obj = review([step("drop_column")])
        obj["steps"][0]["risk"] = "safe"
        self.assert_rejected(obj, "review")
        obj = review([step("review_drop_table")])
        obj["steps"][0]["column_id"] = "id"
        self.assert_rejected(obj, "review")

    def test_conflicting_table_create_drop_and_other_ops_refused(self):
        for other in ("review_drop_table", "review_type_change", "review_table_rename"):
            for reversed_order in (False, True):
                ops = [step("review_create_table"), step(other)]
                if reversed_order:
                    ops.reverse()
                with self.subTest(other=other, reverse=reversed_order):
                    self.assert_rejected(review(ops), "review")

    def test_conflicting_column_add_drop_nullability_refused(self):
        for first, second in (("drop_column", "review_type_change"),
                              ("add_nullable_column", "review_column_rename"),
                              ("add_required_column", "add_nullable_column"),
                              ("drop_not_null", "set_not_null")):
            for pair in ((first, second), (second, first)):
                with self.subTest(pair=pair):
                    self.assert_rejected(review([step(x) for x in pair]), "review")

    def test_duplicate_review_operation_rejected(self):
        self.assert_rejected(review([step("drop_column"), step("drop_column")]), "review")

    def test_legal_composite_and_independent_operations_allowed(self):
        obj = review([step("review_table_rename"), step("review_column_rename"),
                      step("review_type_change"), step("set_not_null"),
                      step("drop_column", column="obsolete"),
                      step("review_drop_table", table="other")])
        self.assertEqual(admit_json(encode(obj), "review"), obj)
        self.assertIs(obj["approved"], False)

    def test_shape_then_semantics_hardened_order(self):
        raw = (b'{"schema":"ores.orm.plan-preview/v1","status":"APPROVED",'
               b'"approved":false,"scope":"column_shapes_only",'
               b'"steps":[{"op":"drop_column","table_id":"users",'
               b'"column_id":"name","risk":"destructive"},'
               b'{"op":"drop_column","table_id":"users",'
               b'"column_id":"name","risk":"destructive"}]}')
        with self.assertRaisesRegex(AdmissionError, "ORM v1 envelope rejected"):
            admit_json(raw, "review")

    def test_cli_file_positive_and_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "input.json"
            path.write_bytes(encode(catalog()))
            result = subprocess.run([sys.executable, str(SCRIPT), "--kind", "catalog",
                                     "--input", str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("HOST_REVIEW_ONLY_OK", result.stdout)
            self.assertIn("NOT a migration authorization", result.stdout)
            path.write_bytes(encode(review([step("drop_column"), step("drop_column")])))
            result = subprocess.run([sys.executable, str(SCRIPT), "--kind", "review",
                                     "--input", str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn("HOST_REVIEW_ONLY_OK", result.stdout)
            self.assertIn("HOST_REVIEW_ONLY_REJECTED", result.stderr)

    def test_cli_stdin_positive_and_rejected(self):
        for expected, payload in ((0, encode(review([step("review_drop_table")]))),
                                  (2, b'{"approved":true}')):
            with self.subTest(exit=expected):
                result = subprocess.run([sys.executable, str(SCRIPT), "--kind", "review",
                                         "--input", "-"], input=payload, capture_output=True)
                self.assertEqual(result.returncode, expected, result.stderr)

    def test_no_unreviewed_sql_written_by_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_path = pathlib.Path(tmp) / "preview.json"
            input_path.write_bytes(encode(review([step("drop_column")])))
            result = subprocess.run([sys.executable, str(SCRIPT), "--kind", "review",
                                     "--input", str(input_path)], cwd=tmp,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual({p.name for p in pathlib.Path(tmp).iterdir()}, {"preview.json"})


if __name__ == "__main__":
    unittest.main()
