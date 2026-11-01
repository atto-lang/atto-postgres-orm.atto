"""Source-only GitHub Actions admission hardening, NOT runner-execution proof.

Policies focus on minimizing source exposure while private Actions admission
is blocked. A green source-only policy test cannot certify runner billing.
"""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
SHA_PIN = re.compile(r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+@[0-9a-f]{40}$")


class WorkflowSafetyTests(unittest.TestCase):
    def test_every_remote_action_pinned_to_full_commit_and_credentials_not_persisted(self):
        files = sorted(WORKFLOWS.glob("*.yml"))
        self.assertGreaterEqual(len(files), 4)
        count = 0
        for file in files:
            lines = file.read_text(encoding="utf-8").splitlines()
            for index, line in enumerate(lines):
                matched = re.match(r"^\s*(?:-\s*)?uses:\s*(\S+)", line)
                if not matched:
                    continue
                ref = matched.group(1)
                with self.subTest(file=file.name, action=ref):
                    self.assertRegex(ref, SHA_PIN)
                    count += 1
                    if ref.startswith("actions/checkout@"):
                        window = "\n".join(lines[index + 1:index + 6])
                        self.assertIn("persist-credentials: false", window)
        self.assertGreaterEqual(count, 4)

    def test_no_privileged_event_or_write_token_scopes(self):
        for file in WORKFLOWS.glob("*.yml"):
            source = file.read_text(encoding="utf-8")
            with self.subTest(file=file.name):
                self.assertNotRegex(source, r"(?m)^\s*pull_request_target\s*:")
                self.assertNotRegex(source, r"(?m)^\s*workflow_run\s*:")
                self.assertNotRegex(source, r"(?m)^\s*permissions:\s*write-all")
                self.assertNotRegex(source, r"(?m)^\s*contents:\s*write")
                self.assertNotRegex(source, r"(?m)^\s*id-token:\s*write")
                self.assertRegex(source, r"(?m)^permissions:\s*(?:\{\}|$)")

    def test_sql_service_runs_exact_registered_database_guards(self):
        workflow = (WORKFLOWS / "pg17-ddl-integration.yml").read_text(encoding="utf-8")
        required = (
            "pg17-ddl-contract.bash",
            "pg17-prepared-binds.bash",
            "pg17-bind-failures.bash",
            "pg17-rls-contract.bash",
            "pg17-cancel-transaction.bash",
            "pg17-catalog-readback-e2e.bash",
            "pg17-catalog-metadata-e2e.bash",
            "pg17-migration-lock-e2e.bash",
            "pg17-migration-lock-abort-e2e.bash",
            "pg17-migration-history-e2e.bash",
        )
        for name in required:
            with self.subTest(name=name):
                self.assertIn("tests/" + name, workflow)
                self.assertTrue((ROOT / "tests" / name).is_file())
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn("PG_TEST_DISPOSABLE: I_ACKNOWLEDGE_DISPOSABLE_DATABASE", workflow)

    def test_host_contracts_discover_tests_and_never_claim_native_execution(self):
        workflow = (WORKFLOWS / "orm-schema-contract.yml").read_text(encoding="utf-8")
        self.assertIn("-p 'test_*.py'", workflow)
        self.assertIn("python -m compileall -q", workflow)
        self.assertIn('for script in tests/pg17-*.bash; do', workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn("JSON_SCHEMA_HOST_ONLY", workflow)

    def test_canary_does_not_checkout_private_source(self):
        workflow = (WORKFLOWS / "runner-admission-canary.yml").read_text(encoding="utf-8")
        self.assertIn("permissions: {}", workflow)
        self.assertIn("runner-admission-only:", workflow)
        self.assertNotRegex(workflow, r"(?m)^\s*-\s*uses:")
        self.assertNotIn("git clone", workflow)
        self.assertNotIn("actions/checkout", workflow)


if __name__ == "__main__":
    unittest.main()
