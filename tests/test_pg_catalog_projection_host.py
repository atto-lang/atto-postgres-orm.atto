"""Offline PostgreSQL capture/ledger fixtures; no PostgreSQL server executed."""
import copy
import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[0]))
from orm_pg_catalog_projection_host import project_capture, ProjectionError


def capture_and_ledger():
    capture = {
        "version": "ores.orm.pg17-capture/v1", "cluster_system_identifier": "7311123456789000000",
        "database_oid": 16385, "server_version_num": 170004,
        "unmodeled_database_objects": [], "tables": [
            {"oid": 10010, "schema": "public", "name": "users", "relkind": "r",
             "rls_enabled": False, "rls_forced": False, "unmodeled_objects": [],
             "columns": [
                 {"attnum": 1, "name": "id", "pg_type": "uuid", "not_null": True,
                  "default_expr": None, "identity": "", "generated": "", "dropped": False},
                 {"attnum": 2, "name": "display_name", "pg_type": "text", "not_null": False,
                  "default_expr": None, "identity": "", "generated": "", "dropped": False}
             ]}
        ]}
    ledger = {
        "version": "ores.orm.pg17-ledger/v1", "cluster_system_identifier": "7311123456789000000",
        "database_oid": 16385, "table_mappings": [
            {"table_oid": 10010, "stable_id": "users", "column_mappings": [
                {"attnum": 1, "stable_id": "id"},
                {"attnum": 2, "stable_id": "name"}
            ]}
        ]}
    return capture, ledger


class Pg17OfflineProjectionTests(unittest.TestCase):
    def assert_rejected(self, change, kind="capture"):
        capture, ledger = capture_and_ledger()
        change(capture if kind == "capture" else ledger)
        with self.assertRaises(ProjectionError):
            project_capture(capture, ledger)

    def test_normalized_review_only_projection(self):
        c, l = capture_and_ledger()
        original_c, original_l = copy.deepcopy(c), copy.deepcopy(l)
        p = project_capture(c, l)
        self.assertEqual(p["schema_version"], "ores.orm.catalog/v1")
        self.assertEqual(p["tables"][0]["stable_id"], "users")
        self.assertEqual(p["tables"][0]["columns"][1],
                         {"stable_id": "name", "name": "display_name", "kind": "string", "nullable": True})
        self.assertEqual((c, l), (original_c, original_l))

    def test_column_reordering_has_same_projection(self):
        c, l = capture_and_ledger()
        expected = project_capture(c, l)
        c["tables"][0]["columns"].reverse()
        l["table_mappings"][0]["column_mappings"].reverse()
        self.assertEqual(project_capture(c, l), expected)

    def test_renamed_column_keeps_reviewed_identity(self):
        c, l = capture_and_ledger()
        c["tables"][0]["columns"][1]["name"] = "new_physical_name"
        projected = project_capture(c, l)
        self.assertEqual(projected["tables"][0]["columns"][1]["stable_id"], "name")
        self.assertEqual(projected["tables"][0]["columns"][1]["name"], "new_physical_name")

    def test_cluster_system_id_mismatch_rejected(self):
        self.assert_rejected(lambda x: x.update(cluster_system_identifier="999"), "ledger")

    def test_database_oid_mismatch_rejected(self):
        self.assert_rejected(lambda x: x.update(database_oid=5), "ledger")

    def test_boolean_oid_rejected(self):
        self.assert_rejected(lambda x: x.update(database_oid=True), "ledger")

    def test_non_ascii_cluster_identity_rejected(self):
        self.assert_rejected(lambda x: x.update(cluster_system_identifier="١٢٣"))

    def test_wrong_major_version_rejected(self):
        for version in (160009, 180000, "170004", True):
            with self.subTest(version=version):
                self.assert_rejected(lambda x: x.update(server_version_num=version))

    def test_unmapped_extra_table_rejected(self):
        self.assert_rejected(lambda x: x["tables"].append({**copy.deepcopy(x["tables"][0]), "oid": 10011, "name": "extras"}))

    def test_stale_table_ledger_rejected(self):
        self.assert_rejected(lambda x: x["table_mappings"].append({**copy.deepcopy(x["table_mappings"][0]), "table_oid": 10011}), "ledger")

    def test_duplicate_table_oid_rejected(self):
        self.assert_rejected(lambda x: x["tables"].append(copy.deepcopy(x["tables"][0])))

    def test_mismatched_column_attnum_rejected(self):
        self.assert_rejected(lambda x: x["tables"][0]["columns"][1].update(attnum=3))

    def test_duplicate_column_attnum_rejected(self):
        self.assert_rejected(lambda x: x["tables"][0]["columns"][1].update(attnum=1))

    def test_missing_column_mapping_rejected(self):
        self.assert_rejected(lambda x: x["table_mappings"][0]["column_mappings"].pop(), "ledger")

    def test_stale_extra_column_mapping_rejected(self):
        self.assert_rejected(lambda x: x["table_mappings"][0]["column_mappings"].append({"attnum": 3, "stable_id": "ghost"}), "ledger")

    def test_unreported_extra_capture_metadata_rejected(self):
        self.assert_rejected(lambda x: x["tables"][0].update(migration_sql="DROP TABLE users"))

    def test_default_generated_identity_or_dropped_column_rejected(self):
        for key, value in (("default_expr", "now()"), ("generated", "s"),
                           ("identity", "a"), ("dropped", True)):
            with self.subTest(key=key):
                self.assert_rejected(lambda x: x["tables"][0]["columns"][1].update({key: value}))

    def test_rls_and_unmodeled_catalog_objects_rejected(self):
        for key, value in (("rls_enabled", True), ("rls_forced", True),
                           ("unmodeled_objects", ["index users_pkey"])):
            with self.subTest(key=key):
                self.assert_rejected(lambda x: x["tables"][0].update({key: value}))
        self.assert_rejected(lambda x: x["unmodeled_database_objects"].append("view public.v"))

    def test_unknown_pg_type_and_relation_kind_rejected(self):
        for pg_type in ("varchar(32)", "numeric", "timestamp", "text[]", "citext"):
            with self.subTest(pg_type=pg_type):
                self.assert_rejected(lambda x: x["tables"][0]["columns"][1].update(pg_type=pg_type))
        for relkind in ("p", "v", "m", "f"):
            with self.subTest(relkind=relkind):
                self.assert_rejected(lambda x: x["tables"][0].update(relkind=relkind))

    def test_identifier_unicode_and_newline_rejected(self):
        for name in ("usérs", "users\n", "1users", "users.public", "users_x" * 10):
            with self.subTest(name=name):
                self.assert_rejected(lambda x: x["tables"][0].update(name=name))

    def test_duplicate_stable_ids_from_ledger_rejected(self):
        self.assert_rejected(lambda x: x["table_mappings"][0]["column_mappings"][1].update(stable_id="id"), "ledger")

    def test_duplicate_physical_names_from_capture_rejected(self):
        self.assert_rejected(lambda x: x["tables"][0]["columns"][1].update(name="id"))

    def test_oversize_table_and_column_limits(self):
        self.assert_rejected(lambda x: x["tables"].extend([copy.deepcopy(x["tables"][0])] * 256))
        self.assert_rejected(lambda x: x["tables"][0]["columns"].extend([copy.deepcopy(x["tables"][0]["columns"][0])] * 63))

    def test_missing_field_or_wrong_container_rejected(self):
        self.assert_rejected(lambda x: x["tables"][0].pop("unmodeled_objects"))
        self.assert_rejected(lambda x: x.update(tables={}))
        self.assert_rejected(lambda x: x.update(unmodeled_database_objects=""))

    def test_scoped_oid_mappings_not_name_inference(self):
        c, l = capture_and_ledger()
        c["tables"][0]["name"] = "renamed_users"
        self.assertEqual(project_capture(c, l)["tables"][0]["stable_id"], "users")
        c["tables"][0]["oid"] = 10011
        with self.assertRaises(ProjectionError):
            project_capture(c, l)


    def test_checked_in_offline_capture_and_ledger(self):
        import json
        root = pathlib.Path(__file__).resolve().parents[1]
        c = json.loads((root / "contracts/examples/pg17-capture.offline.json").read_text("utf-8"))
        l = json.loads((root / "contracts/examples/pg17-ledger.offline.json").read_text("utf-8"))
        generated_c, generated_l = capture_and_ledger()
        self.assertEqual(c, generated_c)
        self.assertEqual(l, generated_l)
        self.assertEqual(project_capture(c, l), project_capture(generated_c, generated_l))

    def test_checked_in_fixture_rejects_unreviewed_rls_metadata(self):
        import json
        root = pathlib.Path(__file__).resolve().parents[1]
        c = json.loads((root / "contracts/examples/pg17-capture.offline.json").read_text("utf-8"))
        l = json.loads((root / "contracts/examples/pg17-ledger.offline.json").read_text("utf-8"))
        c["tables"][0]["rls_enabled"] = True
        with self.assertRaises(ProjectionError):
            project_capture(c, l)


if __name__ == "__main__":
    unittest.main()
