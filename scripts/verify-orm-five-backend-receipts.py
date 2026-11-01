#!/usr/bin/env python3
"""Fail-closed local receipt admission for five Oreslang ORM toolchains.

Does NOT compile any guest. Even accepted receipt shapes require independent
exact-head stepful compiler and guest execution before claiming parity.
No network access, repo cloning, or cross-organization source export.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "contracts/orm-five-backend-gate.v1.json"
HEAD = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^[0-9a-f]{64}$")
BACKENDS = ("java", "llvm", "wasm", "cranelift", "net")
EXPECTED_KEYS = {
    "format", "backend", "case", "orm_head", "compiler_head",
    "source_sha256", "compiler_binary_sha256", "guest_artifact_sha256",
    "runner_binary_sha256", "compiler_exit", "guest_exit",
    "guest_stdout", "guest_stderr", "skipped", "run_kind",
}


def strict_json(content):
    def unique(pairs):
        output = {}
        for name, value in pairs:
            if name in output:
                raise ValueError("duplicate JSON key: " + name)
            output[name] = value
        return output

    def deny_non_json(value):
        raise ValueError("non-JSON numeric constant: " + value)

    return json.loads(content, object_pairs_hook=unique,
                      parse_constant=deny_non_json)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_manifest():
    manifest = strict_json(MANIFEST.read_text(encoding="utf-8"))
    require(manifest["schema"] == "ores.orm.five-backend-gate/v1",
            "wrong manifest version")
    require(manifest["status"] == "NOT_VERIFIED",
            "manifest must never self-certify backend execution")
    require(manifest["backends"] == list(BACKENDS),
            "must require all five backends once each")
    require(manifest["policy"]["require_all_backends"] is True,
            "five-backend completeness policy disabled")
    require(manifest["policy"]["source_transfer"] == "source-local-only",
            "source transfer policy weakened")
    sources = manifest["required_sources"]
    require(sources == ["src/schema.ores", "src/pg.ores"],
            "ORM source compilation scope must include schema and SQL planner")
    cases = manifest["cases"]
    require(len(cases) == 4, "must retain four independent native suites")
    expected = {
        "typed-ddl-planner": ("tests/plans.ores",
                              "Postgres SQL planning contracts passed\n"),
        "neutral-schema-planner": ("tests/schema-plans.ores",
                                   "Pure Oreslang schema-diff planning contracts passed\n"),
        "adversarial-schema": ("tests/schema-adversarial.ores",
                               "Pure Oreslang adversarial schema contracts passed\n"),
        "invariant-schema": ("tests/schema-invariants.ores",
                             "Pure Oreslang schema invariant and metamorphic contracts passed\n"),
    }
    require({x["id"]: (x["source"], x["expected_stdout"]) for x in cases}
            == expected and len({x["id"] for x in cases}) == 4,
            "native suite identity or expected output modified")
    for name in sources + [entry["source"] for entry in cases]:
        file = ROOT / name
        require(file.is_file() and not file.is_symlink(),
                "missing or symlinked native source: " + name)
    return manifest


def verify_receipts(manifest, directory, orm_head):
    require(HEAD.fullmatch(orm_head) is not None,
            "ORM HEAD must be exact 40-character lowercase Git SHA")
    require(directory.is_dir() and not directory.is_symlink(),
            "receipt directory must be a real local directory")
    required_names = {
        backend + "--" + case["id"] + ".json"
        for backend in BACKENDS for case in manifest["cases"]
    }
    actual_names = {item.name for item in directory.iterdir()}
    require(actual_names == required_names,
            "missing, extra, or non-exactly named backend receipts")
    for backend in BACKENDS:
        for case in manifest["cases"]:
            file = directory / (backend + "--" + case["id"] + ".json")
            require(file.is_file() and not file.is_symlink(),
                    "missing or symlinked receipt")
            item = strict_json(file.read_text(encoding="utf-8"))
            require(isinstance(item, dict) and set(item) == EXPECTED_KEYS,
                    "receipt schema changed or optional bypass fields injected")
            require(item["format"] == "ores.orm.native-guest-receipt/v1"
                    and item["backend"] == backend and item["case"] == case["id"],
                    "backend/case receipt identity mismatch")
            require(item["orm_head"] == orm_head
                    and HEAD.fullmatch(item["compiler_head"]) is not None,
                    "stale or malformed source/compiler head")
            require(item["source_sha256"] == digest(ROOT / case["source"]),
                    "receipt is not bound to this exact Oreslang fixture")
            for key in ("compiler_binary_sha256", "guest_artifact_sha256",
                        "runner_binary_sha256"):
                require(isinstance(item[key], str)
                        and DIGEST.fullmatch(item[key]) is not None,
                        "missing exact artifact digest: " + key)
            require(type(item["compiler_exit"]) is int and item["compiler_exit"] == 0
                    and type(item["guest_exit"]) is int and item["guest_exit"] == 0,
                    "skipped or unsuccessful compiler/guest outcome")
            require(item["skipped"] is False
                    and item["run_kind"] == "compiled-oreslang-guest",
                    "host mock, skipped run, or unsupported execution kind")
            require(item["guest_stdout"] == case["expected_stdout"]
                    and item["guest_stderr"] == "",
                    "guest output/diagnostic mismatch")
    return len(required_names)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipts", type=Path,
                        help="existing local 20-file receipt directory; never fetch or mirror")
    parser.add_argument("--orm-head", default="",
                        help="exact reviewed ORM HEAD, required with --receipts")
    opts = parser.parse_args(argv)
    manifest = load_manifest()
    if opts.receipts is None:
        require(not opts.orm_head, "unexpected ORM HEAD without receipts")
        print("NOT_VERIFIED: 5 toolchains x 4 suites = 20 compiled guest receipts required")
    else:
        number = verify_receipts(manifest, opts.receipts, opts.orm_head)
        print(f"RECEIPT_SHAPES_ACCEPTED_PENDING_INDEPENDENT_NATIVE_REVIEW: {number}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as error:
        print("NOT_VERIFIED: " + str(error), file=sys.stderr)
        sys.exit(1)
