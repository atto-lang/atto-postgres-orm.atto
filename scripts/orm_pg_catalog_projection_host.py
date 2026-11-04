"""Offline PostgreSQL 17 shape projection; not live introspection or DDL authority.

Both capture and ledger are untrusted inputs. OID+attnum mappings are scoped
by a PostgreSQL cluster system identifier and database OID; they are not
portable across restore, dump/reload, or a new cluster. An independent ledger
review and an actual least-privilege DB capture are mandatory future gates.
"""
import json

from orm_admission_host import AdmissionError, admit_json


class ProjectionError(ValueError):
    pass


TYPES = {
    "uuid": "uuid", "text": "string", "integer": "int32",
    "bigint": "int64", "boolean": "boolean", "jsonb": "json",
    "timestamp with time zone": "timestamp", "bytea": "bytes",
}
MAX_TABLES = 256
MAX_COLUMNS = 64


def _object(value, fields, label):
    if type(value) is not dict or set(value) != set(fields):
        raise ProjectionError("unsupported or incomplete " + label)


def _positive_int(value):
    return type(value) is int and 0 < value < 2**32


def _identifier(value):
    return (type(value) is str and 1 <= len(value) <= 63
            and (value[0].isalpha() and value[0].isascii() or value[0] == "_")
            and all(ch.isascii() and (ch.isalnum() or ch == "_") for ch in value))


def project_capture(capture, ledger):
    """Return deterministic v1 shape projection, NEVER a trusted DB attestation.

    Refuses all reported out-of-scope objects. Empty inventories do not prove
    that a live database was inspected or that all objects were enumerated.
    """
    _object(capture, {"version", "cluster_system_identifier", "database_oid",
                      "server_version_num", "tables", "unmodeled_database_objects"}, "capture")
    _object(ledger, {"version", "cluster_system_identifier", "database_oid",
                     "table_mappings"}, "ledger")
    if capture["version"] != "ores.orm.pg17-capture/v1" or ledger["version"] != "ores.orm.pg17-ledger/v1":
        raise ProjectionError("unsupported capture or ledger version")
    ident = capture["cluster_system_identifier"]
    if type(ident) is not str or not (1 <= len(ident) <= 20) or not all("0" <= ch <= "9" for ch in ident):
        raise ProjectionError("invalid cluster identity")
    if ident != ledger["cluster_system_identifier"] or not _positive_int(capture["database_oid"]) or not _positive_int(ledger["database_oid"]) or capture["database_oid"] != ledger["database_oid"]:
        raise ProjectionError("capture/ledger database identity mismatch")
    if type(capture["server_version_num"]) is not int or not (170000 <= capture["server_version_num"] < 180000):
        raise ProjectionError("requires PostgreSQL 17 capture")
    if type(capture["unmodeled_database_objects"]) is not list or capture["unmodeled_database_objects"]:
        raise ProjectionError("unmodeled database objects require full-catalog review")
    tables = capture["tables"]
    mappings = ledger["table_mappings"]
    if type(tables) is not list or type(mappings) is not list or len(tables) > MAX_TABLES or len(mappings) != len(tables):
        raise ProjectionError("catalog or ledger table cardinality mismatch")
    by_oid = {}
    for mapping in mappings:
        _object(mapping, {"table_oid", "stable_id", "column_mappings"}, "table mapping")
        oid = mapping["table_oid"]
        if not _positive_int(oid) or oid in by_oid or not _identifier(mapping["stable_id"]):
            raise ProjectionError("ambiguous table mapping")
        by_oid[oid] = mapping
    output = []
    observed_oids = set()
    for table in tables:
        _object(table, {"oid", "schema", "name", "relkind", "rls_enabled", "rls_forced",
                        "unmodeled_objects", "columns"}, "table")
        oid = table["oid"]
        if not _positive_int(oid) or oid in observed_oids or oid not in by_oid:
            raise ProjectionError("unmapped or repeated table OID")
        observed_oids.add(oid)
        if table["schema"] != "public" or not _identifier(table["name"]) or table["relkind"] != "r":
            raise ProjectionError("unsupported schema, name, or relation kind")
        if type(table["rls_enabled"]) is not bool or type(table["rls_forced"]) is not bool or table["rls_enabled"] or table["rls_forced"]:
            raise ProjectionError("RLS requires full-catalog verification")
        if type(table["unmodeled_objects"]) is not list or table["unmodeled_objects"]:
            raise ProjectionError("unmodeled table objects require review")
        cols = table["columns"]
        if type(cols) is not list or not (1 <= len(cols) <= MAX_COLUMNS):
            raise ProjectionError("unsupported column count")
        cmaps = by_oid[oid]["column_mappings"]
        if type(cmaps) is not list or len(cmaps) != len(cols):
            raise ProjectionError("column ledger cardinality mismatch")
        stable_for_attnum = {}
        for cm in cmaps:
            _object(cm, {"attnum", "stable_id"}, "column mapping")
            n = cm["attnum"]
            if not _positive_int(n) or n in stable_for_attnum or not _identifier(cm["stable_id"]):
                raise ProjectionError("ambiguous column mapping")
            stable_for_attnum[n] = cm["stable_id"]
        observed_attnums = set()
        columns = []
        for col in cols:
            _object(col, {"attnum", "name", "pg_type", "not_null", "default_expr",
                          "identity", "generated", "dropped"}, "column")
            n = col["attnum"]
            if not _positive_int(n) or n in observed_attnums or n not in stable_for_attnum:
                raise ProjectionError("unmapped or repeated column attnum")
            observed_attnums.add(n)
            if not _identifier(col["name"]) or type(col["pg_type"]) is not str or col["pg_type"] not in TYPES:
                raise ProjectionError("unsupported column name or PostgreSQL type")
            if type(col["not_null"]) is not bool or type(col["dropped"]) is not bool:
                raise ProjectionError("invalid column flags")
            if col["dropped"] or col["default_expr"] is not None or col["identity"] != "" or col["generated"] != "":
                raise ProjectionError("unmodeled column features require review")
            columns.append({"stable_id": stable_for_attnum[n], "name": col["name"],
                            "kind": TYPES[col["pg_type"]], "nullable": not col["not_null"]})
        if observed_attnums != set(stable_for_attnum):
            raise ProjectionError("stale column ledger")
        output.append({"stable_id": by_oid[oid]["stable_id"], "name": table["name"],
                       "columns": sorted(columns, key=lambda c: c["stable_id"])})
    if observed_oids != set(by_oid):
        raise ProjectionError("stale table ledger")
    result = {"schema_version": "ores.orm.catalog/v1", "tables": sorted(output, key=lambda t: t["stable_id"])}
    try:
        return admit_json(json.dumps(result, ensure_ascii=True, separators=(",", ":")).encode("utf-8"), "catalog")
    except AdmissionError as exc:
        raise ProjectionError("portable catalog shape/identity rejected") from exc
