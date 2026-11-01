"""Host-only mock/contract guards for PG17 metadata E2E; never DB proof."""
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "tests/pg17-catalog-metadata-e2e.bash"
SQL = ROOT / "tests/pg17-catalog-metadata-e2e.sql"


class CatalogMetadataAdmissionTests(unittest.TestCase):
    def test_metadata_scope_and_rollback_contract(self):
        sql = SQL.read_text(encoding="utf-8")
        expected = (
            "pg_catalog.pg_policy", "pg_catalog.pg_index",
            "pg_catalog.pg_constraint", "pg_catalog.pg_attrdef",
            "relrowsecurity AND relforcerowsecurity",
            "expected_policy ON COMMIT DROP", "expected_default ON COMMIT DROP",
            "ALTER TABLE guarded_records ADD COLUMN notes text",
            "RLS_DISABLE_UNDETECTED", "RLS_FORCE_UNDETECTED",
            "POLICY_DROP_UNDETECTED", "POLICY_WEAKEN_UNDETECTED",
            "UNIQUE_INDEX_DROP_UNDETECTED", "CHECK_CONSTRAINT_DROP_UNDETECTED",
            "DEFAULT_CHANGE_UNDETECTED", "PROTECTED_CATALOG_DRIFT",
            "GET STACKED DIAGNOSTICS",
            "SELECT count(*) FROM pg_catalog.pg_namespace",
        )
        for marker in expected:
            with self.subTest(marker=marker):
                self.assertIn(marker, sql)
        self.assertEqual(sql.count("\nROLLBACK;\n"), 1)
        self.assertNotIn("\nCOMMIT;\n", sql)
        self.assertEqual(sql.count("EXCEPTION WHEN check_violation"), 7)
        for name in ("version_guard", "assert", "baseline", "negative"):
            self.assertEqual(sql.count("$" + name + "$"), 2)

    def test_registration_and_shell_syntax(self):
        shell = shutil.which("bash")
        if shell is None:
            self.skipTest("bash unavailable")
        run = subprocess.run([shell, "-n", str(WRAPPER)],
                             capture_output=True, text=True, check=False)
        self.assertEqual(run.returncode, 0, run.stderr)
        for path in (".github/workflows/pg17-ddl-integration.yml",
                     ".github/workflows/orm-schema-contract.yml"):
            workflow = (ROOT / path).read_text(encoding="utf-8")
            with self.subTest(workflow=path):
                self.assertIn("tests/pg17-catalog-metadata-e2e.sql", workflow)
                self.assertIn("tests/pg17-catalog-metadata-e2e.bash", workflow)
        self.assertIn("PG_TEST_DISPOSABLE", WRAPPER.read_text(encoding="utf-8"))

    def test_mock_psql_rejects_bypass_and_false_receipts(self):
        """Runs an isolated fake psql process, never an actual PG17 server."""
        shell = shutil.which("bash")
        if shell is None:
            self.skipTest("bash unavailable")
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            fake = root / "psql"
            touched = root / "called"
            fake.write_text(r"""#!/bin/sh
printf 'called\n' >> "$MOCK_CONTACT"
case " $* " in
  *"SHOW server_version_num"*)
    printf '%s\n' "$MOCK_VERSION"
    exit "$MOCK_VERSION_RC";;
esac
printf '%s\n' "$MOCK_RESULT"
exit "$MOCK_SQL_RC"
""", encoding="utf-8")
            fake.chmod(0o755)
            env = os.environ.copy()
            env["PATH"] = str(root) + os.pathsep + env.get("PATH", "")
            env.update(MOCK_CONTACT=str(touched), MOCK_VERSION="170005",
                       MOCK_VERSION_RC="0", MOCK_SQL_RC="0",
                       PG_TEST_DSN="postgresql://fake.invalid/isolated",
                       PG_TEST_DISPOSABLE="I_ACKNOWLEDGE_DISPOSABLE_DATABASE")
            def run_case(overrides, expected_pass, before_contact=False):
                values = env.copy()
                values.update(overrides)
                run = subprocess.run([shell, str(WRAPPER)], env=values,
                                     capture_output=True, text=True, check=False,
                                     timeout=10)
                self.assertEqual(run.returncode == 0, expected_pass, run.stderr)
                if not expected_pass:
                    self.assertIn("PG_METADATA_E2E_NOT_VERIFIED:", run.stderr)
                if before_contact:
                    self.assertFalse(touched.exists(), "unexpected psql contact")
                return run
            touched.unlink(missing_ok=True)
            run_case({"PG_TEST_DISPOSABLE": ""}, False, True)
            run_case({"PG_TEST_DSN": ""}, False, True)
            for version in ("160001", "180001", "seventeen", "17"):
                with self.subTest(version=version):
                    run_case({"MOCK_VERSION": version}, False)
            run_case({"MOCK_VERSION_RC": "33"}, False)
            good = "PG17_METADATA_E2E_OK\n0"
            run_case({"MOCK_RESULT": good}, True)
            for candidate in ("PG17_METADATA_E2E_OK\n1",
                              "PG17_METADATA_E2E_OK",
                              "PG17_METADATA_E2E_OK\n0\nEXTRA",
                              "APPROVED\n0"):
                with self.subTest(receipt=candidate):
                    run_case({"MOCK_RESULT": candidate}, False)
            run_case({"MOCK_RESULT": good, "MOCK_SQL_RC": "41"}, False)


if __name__ == "__main__":
    unittest.main()
