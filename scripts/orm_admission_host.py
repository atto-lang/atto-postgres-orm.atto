"""Fail-closed *host-only* ORM JSON admission, never a migration executor.

The independently authored TypeSpec contract is not compiled or compared here.
A successful result means only that the checked-in JSON Schema and cross-item
host checks accepted a bounded review-only v1 envelope; it grants no DDL rights.
"""

import argparse
from functools import lru_cache
import json
from pathlib import Path
import sys

from jsonschema import Draft202012Validator, ValidationError

from orm_semantics_host import check_catalog_semantics, check_review_semantics

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 8 * 1024 * 1024
SCHEMAS = {
    "catalog": "orm-catalog.schema.json",
    "review": "orm-plan-preview.schema.json",
}


class AdmissionError(ValueError):
    """Review-only admission failure; never permission to execute a migration."""


def _unique_object_members(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise AdmissionError("duplicate JSON member")
        result[key] = value
    return result


def _reject_non_json_number(value):
    raise AdmissionError("non-JSON numeric constant")


@lru_cache(maxsize=2)
def _validator(kind):
    if kind not in SCHEMAS:
        raise AdmissionError("unrecognized ORM envelope kind")
    schema_path = ROOT / "contracts" / SCHEMAS[kind]
    # Schemas are fixed paths in the trusted checkout; no input-controlled refs.
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def admit_json(raw, kind):
    """Validate UTF-8 JSON shape THEN cross-item semantics, without I/O/DDL.

    Only accepts bytes to avoid lossy transcoding, permissive decoding, and
    accidental bypass of duplicate-object-key detection on parsed dicts.
    Returns untrusted *review data*, never an authorization or execution plan.
    """
    if kind not in SCHEMAS:
        raise AdmissionError("unrecognized ORM envelope kind")
    if not isinstance(raw, bytes):
        raise AdmissionError("admission requires exact UTF-8 bytes")
    if not raw or len(raw) > MAX_BYTES:
        raise AdmissionError("empty or oversized ORM envelope")
    try:
        text = raw.decode("utf-8", errors="strict")
        envelope = json.loads(text, object_pairs_hook=_unique_object_members,
                              parse_constant=_reject_non_json_number)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise AdmissionError("malformed or ambiguous JSON: " + str(exc)) from None
    try:
        _validator(kind).validate(envelope)
        if kind == "catalog":
            check_catalog_semantics(envelope)
        else:
            check_review_semantics(envelope)
    except ValidationError as exc:
        # Never stringify untrusted nested payloads through jsonschema's
        # pretty-printer: deep arrays can otherwise crash while formatting.
        raise AdmissionError("ORM v1 envelope rejected: " + str(exc.validator)) from None
    except (ValueError, RecursionError):
        raise AdmissionError("ORM v1 envelope rejected: semantic conflict") from None
    return envelope


def main(argv=None):
    parser = argparse.ArgumentParser(description="Host-only ORM review admission; no SQL, DB, TypeSpec, native guest, or apply")
    parser.add_argument("--kind", choices=tuple(SCHEMAS), required=True)
    parser.add_argument("--input", required=True, help="JSON file path or - for stdin")
    args = parser.parse_args(argv)
    try:
        if args.input == "-":
            raw = sys.stdin.buffer.read(MAX_BYTES + 1)
        else:
            with open(args.input, "rb") as stream:
                raw = stream.read(MAX_BYTES + 1)
        admit_json(raw, args.kind)
    except (AdmissionError, OSError) as exc:
        print("ORM_HOST_REVIEW_ONLY_REJECTED: " + str(exc), file=sys.stderr)
        return 2
    print("ORM_HOST_REVIEW_ONLY_OK: shape + cross-item checks; NOT a migration authorization")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
