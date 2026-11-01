"""Host-only fake DB tests: fixed pg_catalog SQL; no live PostgreSQL executed."""
import copy
import pathlib
import sys
import types
import unittest
from unittest.mock import patch
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
from orm_pg_catalog_reader_host import SQL, CaptureError, capture_from_connection, capture_from_dsn


def responses():
    return {
        "mode": [("on", "repeatable read")],
        "identity": [(170004, 16385, "7311123456789000000")],
        "relations": [(10010, "public", "users", "r", False, False)],
        "columns": [(10010, 1, "id", "uuid", True, False, "", "", False),
                    (10010, 2, "display_name", "text", False, False, "", "", False)],
        "table_extras": [(10010, 0)],
        "global_extras": [(0, 0, 0, 0, 0, 0)],
    }


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self.data = None
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def execute(self, query):
        self.conn.queries.append(query)
        if query.startswith("BEGIN") or query == "ROLLBACK":
            self.data = []
        elif query.startswith("SELECT current_setting('transaction_read_only')"):
            self.data = self.conn.responses["mode"]
        else:
            candidates = [key for key, value in SQL.items() if value == query]
            if len(candidates) != 1:
                raise AssertionError("unknown SQL in capture")
            key = candidates[0]
            if key == "identity" and self.conn.deny_identity:
                raise PermissionError("pg_control_system() denied")
            self.data = self.conn.responses[key]
    def fetchone(self): return self.data[0]
    def fetchall(self): return self.data


class FakeConnection:
    def __init__(self, data=None):
        self.responses = copy.deepcopy(data if data is not None else responses())
        self.queries = []
        self.deny_identity = False
    def cursor(self): return FakeCursor(self)
    def __enter__(self): return self
    def __exit__(self, *args): return False


class LiveCatalogReaderHostTests(unittest.TestCase):
    def test_complete_pg17_capture_matches_offline_shape(self):
        db = FakeConnection()
        out = capture_from_connection(db)
        self.assertEqual(out["version"], "ores.orm.pg17-capture/v1")
        self.assertEqual(out["database_oid"], 16385)
        self.assertEqual(out["tables"][0]["columns"][1]["pg_type"], "text")
        self.assertEqual(out["unmodeled_database_objects"], [])
        self.assertEqual(len(db.queries), 6)

    def test_all_queries_are_fixed_catalog_selects(self):
        self.assertEqual(len(SQL), 5)
        for name, query in SQL.items():
            with self.subTest(name=name):
                self.assertTrue(query.startswith("SELECT"))
                self.assertFalse("%s" in query or "{}" in query)
                self.assertFalse(any(s in query.upper() for s in (";INSERT", ";UPDATE", ";DROP", ";DELETE")))

    def test_readonly_and_repeatable_read_mandatory(self):
        for mode in (("off", "repeatable read"), ("on", "read committed"), ("on", "serializable")):
            db = FakeConnection()
            db.responses["mode"] = [mode]
            with self.subTest(mode=mode), self.assertRaises(CaptureError):
                capture_from_connection(db)
            self.assertEqual(len(db.queries), 1)

    def test_cluster_attestation_failure_never_falls_back(self):
        db = FakeConnection()
        db.deny_identity = True
        with self.assertRaises(PermissionError):
            capture_from_connection(db)
        self.assertFalse(any("system_identifier" in str(x) for x in db.queries if x.startswith("BEGIN")))

    def test_version_and_oid_validation(self):
        for invalid in ((160010, 16385, "7311123456789000000"),
                        (180000, 16385, "7311123456789000000"),
                        (True, 16385, "7311123456789000000"),
                        (170004, True, "7311123456789000000"),
                        (170004, 16385, "false")):
            db = FakeConnection()
            db.responses["identity"] = [invalid]
            with self.subTest(identity=invalid), self.assertRaises(CaptureError):
                capture_from_connection(db)

    def test_unmodeled_relation_kind_preserved(self):
        db = FakeConnection()
        db.responses["relations"].append((10011, "public", "users_pk", "i", False, False))
        result = capture_from_connection(db)
        self.assertIn("public_relation:i", result["unmodeled_database_objects"])

    def test_rls_flags_and_policy_count_preserved(self):
        for change in ("rls", "force", "policy"):
            db = FakeConnection()
            if change == "rls": db.responses["relations"][0] = (10010, "public", "users", "r", True, False)
            if change == "force": db.responses["relations"][0] = (10010, "public", "users", "r", False, True)
            if change == "policy": db.responses["table_extras"] = [(10010, 1)]
            result = capture_from_connection(db)
            self.assertTrue(result["tables"][0]["rls_enabled"] or result["tables"][0]["rls_forced"] or result["tables"][0]["unmodeled_objects"])

    def test_default_identity_generated_dropped_preserved(self):
        for index, value in ((5, True), (6, "a"), (7, "s"), (8, True)):
            db = FakeConnection()
            row = list(db.responses["columns"][1]); row[index] = value
            db.responses["columns"][1] = tuple(row)
            out = capture_from_connection(db)["tables"][0]["columns"][1]
            self.assertTrue(out["default_expr"] is not None or out["identity"] or out["generated"] or out["dropped"])

    def test_extra_columns_cannot_disappear(self):
        db = FakeConnection()
        db.responses["columns"].append((10010, 3, "extra", "integer", False, False, "", "", False))
        self.assertEqual(len(capture_from_connection(db)["tables"][0]["columns"]), 3)

    def test_missing_table_feature_row_fails_closed(self):
        db = FakeConnection()
        db.responses["table_extras"] = []
        with self.assertRaises(CaptureError): capture_from_connection(db)

    def test_duplicate_table_oid_and_attnum_rejected(self):
        for key in ("relations", "columns"):
            db = FakeConnection(); db.responses[key].append(db.responses[key][0])
            with self.subTest(key=key), self.assertRaises(CaptureError): capture_from_connection(db)

    def test_invalid_counter_does_not_create_clean_inventory(self):
        for value in (-1, True, None):
            db = FakeConnection(); db.responses["global_extras"] = [(value, 0, 0, 0, 0, 0)]
            with self.subTest(value=value), self.assertRaises(CaptureError): capture_from_connection(db)

    def test_db_connection_begins_readonly_and_rolls_back(self):
        conn = FakeConnection()
        connect_calls = []
        def connect(dsn, **kwargs):
            connect_calls.append((dsn, kwargs)); return conn
        with patch.dict(sys.modules, {"psycopg": types.SimpleNamespace(connect=connect)}):
            out = capture_from_dsn("secret-conninfo")
        self.assertEqual(out["database_oid"], 16385)
        self.assertEqual(conn.queries[0], "BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        self.assertEqual(conn.queries[-1], "ROLLBACK")
        self.assertTrue(connect_calls[0][1]["autocommit"])

    def test_failure_always_rolls_back(self):
        conn = FakeConnection(); conn.deny_identity = True
        with patch.dict(sys.modules, {"psycopg": types.SimpleNamespace(connect=lambda *a, **kw: conn)}):
            with self.assertRaises(PermissionError): capture_from_dsn("SECRET")
        self.assertEqual(conn.queries[-1], "ROLLBACK")


if __name__ == "__main__":
    unittest.main()
