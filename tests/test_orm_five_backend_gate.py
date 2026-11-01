"""Host-only mutation tests of ORM parity evidence admission.

A fake receipt is never compiled guest evidence. This suite proves that
incomplete/forged/ambiguous receipts cannot silently turn into parity.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts/verify-orm-five-backend-receipts.py"
spec = importlib.util.spec_from_file_location("orm_parity_gate", PATH)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

HEAD = "a" * 40


class ParityReceiptAdmissionTests(unittest.TestCase):
    def test_contract_is_five_backends_and_four_unmodified_guest_suites(self):
        manifest = gate.load_manifest()
        self.assertEqual(tuple(manifest["backends"]), gate.BACKENDS)
        self.assertEqual(len(manifest["cases"]), 5)
        self.assertEqual(len(manifest["backends"]) * len(manifest["cases"]), 25)
        self.assertEqual(manifest["status"], "NOT_VERIFIED")
        self.assertEqual(manifest["required_sources"], ["src/schema.ores", "src/pg.ores"])
        combined = next(entry for entry in manifest["cases"]
                        if entry["id"] == "combined-orm-modules")
        code = (ROOT / combined["source"]).read_text(encoding="utf-8")
        self.assertIn("import module schema from '../src/schema';", code)
        self.assertIn("import module pg from '../src/pg';", code)
        self.assertIn("table_typed_pk", code)
        self.assertIn("table_checked", code)
        self.assertIn("DDL rendering drift", code)

    def test_ambiguous_or_non_json_receipts_are_not_json(self):
        for raw in (
            '{"backend":"java","backend":"llvm"}',
            '{"guest_exit":0,"guest_exit":1}',
            '{"compiler_exit":NaN}',
            '{"guest_exit":Infinity}',
            '{"guest_exit":-Infinity}',
        ):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    gate.strict_json(raw)

    def test_all_twenty_five_receipt_shapes_and_adversarial_mutations(self):
        manifest = gate.load_manifest()
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            local_root = workspace / "orm"
            directory = workspace / "receipts"
            directory.mkdir()
            for name in manifest["required_sources"] + [
                case["source"] for case in manifest["cases"]
            ]:
                source = local_root / name
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text("fixture:" + name, encoding="utf-8")
            with mock.patch.object(gate, "ROOT", local_root):
                originals = {}
                for backend in gate.BACKENDS:
                    for case in manifest["cases"]:
                        value = {
                            "format": "ores.orm.native-guest-receipt/v1",
                            "backend": backend,
                            "case": case["id"],
                            "orm_head": HEAD,
                            "compiler_head": "b" * 40,
                            "source_sha256": gate.digest(local_root / case["source"]),
                            "schema_source_sha256": gate.digest(local_root / "src/schema.ores"),
                            "pg_source_sha256": gate.digest(local_root / "src/pg.ores"),
                            "compiler_binary_sha256": "c" * 64,
                            "guest_artifact_sha256": "d" * 64,
                            "runner_binary_sha256": "e" * 64,
                            "compiler_exit": 0,
                            "guest_exit": 0,
                            "guest_stdout": case["expected_stdout"],
                            "guest_stderr": "",
                            "skipped": False,
                            "run_kind": "compiled-oreslang-guest",
                        }
                        path = directory / (backend + "--" + case["id"] + ".json")
                        originals[path] = value
                        path.write_text(json.dumps(value), encoding="utf-8")
                def write_value(file, value):
                    file.write_text(json.dumps(value), encoding="utf-8")
                with mock.patch.object(gate.subprocess, "check_output",
                                       side_effect=[HEAD + "\n", ""] * 256):
                    self.assertEqual(gate.verify_receipts(manifest, directory, HEAD), 25)
                    target = next(iter(originals))
                    original = originals[target]
                    mutants = (
                        ("wrong-backend", {"backend": "unknown"}),
                        ("wrong-case", {"case": "other"}),
                        ("wrong-ORM-head", {"orm_head": "f" * 40}),
                        ("wrong-compiler-SHA", {"compiler_head": "not-a-head"}),
                        ("wrong-fixture", {"source_sha256": "0" * 64}),
                        ("wrong-schema-module", {"schema_source_sha256": "0" * 64}),
                        ("wrong-pg-module", {"pg_source_sha256": "0" * 64}),
                        ("missing-artifact", {"guest_artifact_sha256": ""}),
                        ("skipped", {"skipped": True}),
                        ("host-mock", {"run_kind": "python-model"}),
                        ("compiler-failed", {"compiler_exit": 1}),
                        ("guest-failed", {"guest_exit": 1}),
                        ("wrong-stdout", {"guest_stdout": "42\n"}),
                        ("unexpected-stderr", {"guest_stderr": "WARNING"}),
                        ("bool-int-exit", {"guest_exit": False}),
                        ("extra-authority", {"approved": True}),
                    )
                    for label, change in mutants:
                        with self.subTest(mutant=label):
                            write_value(target, {**original, **change})
                            with self.assertRaises(ValueError):
                                gate.verify_receipts(manifest, directory, HEAD)
                            write_value(target, original)
                    one = directory / ("java--" + manifest["cases"][1]["id"] + ".json")
                    value = originals[one]
                    write_value(one, {**value, "compiler_binary_sha256": "0" * 64})
                    with self.assertRaisesRegex(ValueError, "changed compiler"):
                        gate.verify_receipts(manifest, directory, HEAD)
                    write_value(one, value)
                    target.unlink()
                    with self.assertRaisesRegex(ValueError, "missing, extra"):
                        gate.verify_receipts(manifest, directory, HEAD)
                    write_value(target, original)
                    (directory / "unexpected.json").write_text("{}", encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "missing, extra"):
                        gate.verify_receipts(manifest, directory, HEAD)

    def test_receipt_head_must_match_clean_local_checkout(self):
        manifest = gate.load_manifest()
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            with mock.patch.object(gate.subprocess, "check_output",
                                   side_effect=["b" * 40 + "\n", ""]):
                with self.assertRaisesRegex(ValueError, "head mismatch"):
                    gate.verify_receipts(manifest, directory, HEAD)
            with mock.patch.object(gate.subprocess, "check_output",
                                   side_effect=[HEAD + "\n", " M src/schema.ores\n"]):
                with self.assertRaisesRegex(ValueError, "tracked files modified"):
                    gate.verify_receipts(manifest, directory, HEAD)
            with self.assertRaisesRegex(ValueError, "40-character"):
                gate.verify_receipts(manifest, directory, "main")


if __name__ == "__main__":
    unittest.main()
