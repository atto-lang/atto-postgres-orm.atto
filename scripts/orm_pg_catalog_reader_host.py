"""Read-only PostgreSQL 17 catalog capture for the *offline* ORM projector.

No SQL generation, DDL, migration approval, or application capability exists.
The caller supplies a DB role with catalog visibility and explicit EXECUTE on
pg_catalog.pg_control_system(); never silently trust supplied cluster IDs.
"""

class CaptureError(ValueError):
    pass


# All SQL text is constant; no identifier/value from a database or caller is
# interpolated into queries. PostgreSQL catalog access is metadata-only.
SQL = {
    "identity": """SELECT current_setting('server_version_num')::integer,
        (SELECT oid::integer FROM pg_catalog.pg_database WHERE datname = current_database()),
        (SELECT system_identifier::text FROM pg_catalog.pg_control_system())""",
    "relations": """SELECT c.oid::integer, n.nspname, c.relname, c.relkind::text,
        c.relrowsecurity, c.relforcerowsecurity
        FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' ORDER BY c.oid""",
    "columns": """SELECT a.attrelid::integer, a.attnum::integer, a.attname,
        pg_catalog.format_type(a.atttypid, a.atttypmod), a.attnotnull,
        (d.oid IS NOT NULL), a.attidentity::text, a.attgenerated::text,
        a.attisdropped
        FROM pg_catalog.pg_attribute a
        JOIN pg_catalog.pg_class c ON c.oid = a.attrelid
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        LEFT JOIN pg_catalog.pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
        WHERE n.nspname = 'public' AND c.relkind = 'r' AND a.attnum > 0
        ORDER BY a.attrelid, a.attnum""",
    "table_extras": """SELECT c.oid::integer,
        (SELECT count(*) FROM pg_catalog.pg_constraint k WHERE k.conrelid = c.oid)
        + (SELECT count(*) FROM pg_catalog.pg_index i WHERE i.indrelid = c.oid)
        + (SELECT count(*) FROM pg_catalog.pg_trigger t WHERE t.tgrelid = c.oid)
        + (SELECT count(*) FROM pg_catalog.pg_policy p WHERE p.polrelid = c.oid)
        + (SELECT count(*) FROM pg_catalog.pg_rewrite w WHERE w.ev_class = c.oid)
        + (SELECT count(*) FROM pg_catalog.pg_inherits h
            WHERE h.inhrelid = c.oid OR h.inhparent = c.oid)
        + (SELECT count(*) FROM pg_catalog.pg_publication_rel p WHERE p.prrelid = c.oid)
        FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'r' ORDER BY c.oid""",
    "global_extras": """SELECT
        (SELECT count(*) FROM pg_catalog.pg_namespace
            WHERE nspname NOT IN ('public', 'pg_catalog', 'information_schema')
            AND nspname NOT LIKE 'pg_toast%' AND nspname NOT LIKE 'pg_temp_%'),
        (SELECT count(*) FROM pg_catalog.pg_proc p
            JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'public'),
        (SELECT count(*) FROM pg_catalog.pg_type t
            JOIN pg_catalog.pg_namespace n ON n.oid = t.typnamespace
            WHERE n.nspname = 'public' AND t.typtype IN ('d', 'e', 'r', 'm')),
        (SELECT count(*) FROM pg_catalog.pg_extension WHERE extname <> 'plpgsql'),
        (SELECT count(*) FROM pg_catalog.pg_event_trigger),
        (SELECT count(*) FROM pg_catalog.pg_publication)""",
}


def _rows(conn, key):
    with conn.cursor() as cursor:
        cursor.execute(SQL[key])
        return cursor.fetchall()


def _int(value):
    return type(value) is int and 0 <= value < 2**32


def capture_from_connection(conn):
    """Run only inside an established repeatable-read read-only transaction.

    Refuses capture when read-only/isolation cannot be verified, rather
    than exposing a generic SQL executor or 'trust me' identity override.
    """
    with conn.cursor() as cursor:
        cursor.execute("SELECT current_setting('transaction_read_only'), current_setting('transaction_isolation')")
        mode = cursor.fetchone()
    if mode != ("on", "repeatable read"):
        raise CaptureError("requires verified read-only repeatable-read transaction")
    identities = _rows(conn, "identity")
    if len(identities) != 1 or len(identities[0]) != 3:
        raise CaptureError("PostgreSQL cluster/database identity unavailable")
    version, database_oid, sysid = identities[0]
    sysid = str(sysid)
    if not _int(version) or not 170000 <= version < 180000 or not _int(database_oid) or database_oid == 0 or not sysid.isascii() or not sysid.isdecimal() or not 1 <= len(sysid) <= 20:
        raise CaptureError("unexpected PostgreSQL 17 database identity")
    relations = _rows(conn, "relations")
    columns = _rows(conn, "columns")
    table_extras = _rows(conn, "table_extras")
    global_extras = _rows(conn, "global_extras")
    if len(global_extras) != 1 or len(global_extras[0]) != 6:
        raise CaptureError("incomplete global feature inventory")
    if len(relations) > 512 or len(columns) > 16384 or len(table_extras) > 256:
        raise CaptureError("catalog capture exceeds v1 limits")
    if any(not _int(x) for x in global_extras[0]):
        raise CaptureError("invalid global feature counters")
    unsupported = [name for name, count in zip(
        ("custom_schemas", "public_functions", "public_custom_types", "extensions", "event_triggers", "publications"),
        global_extras[0]) if count]
    observed = {}
    for row in relations:
        if len(row) != 6:
            raise CaptureError("incomplete relation metadata")
        oid, schema, name, kind, rls, force_rls = row
        if not _int(oid) or oid == 0 or oid in observed or type(rls) is not bool or type(force_rls) is not bool:
            raise CaptureError("ambiguous or invalid relation metadata")
        if kind != "r":
            unsupported.append("public_relation:" + str(kind))
            continue
        observed[oid] = {"oid": oid, "schema": schema, "name": name, "relkind": kind,
                         "rls_enabled": rls, "rls_forced": force_rls,
                         "unmodeled_objects": [], "columns": []}
    extras_by_oid = {}
    for row in table_extras:
        if len(row) != 2 or not _int(row[0]) or not _int(row[1]) or row[0] in extras_by_oid:
            raise CaptureError("invalid per-table feature inventory")
        extras_by_oid[row[0]] = row[1]
    if set(extras_by_oid) != set(observed):
        raise CaptureError("per-table feature inventory incomplete")
    for oid, count in extras_by_oid.items():
        if count:
            observed[oid]["unmodeled_objects"].append("constraints_indexes_triggers_policies_rules_inheritance_publication")
    seen_attnum = set()
    for row in columns:
        if len(row) != 9:
            raise CaptureError("incomplete column metadata")
        oid, attnum, name, pg_type, not_null, has_default, identity, generated, dropped = row
        if oid not in observed or not _int(attnum) or attnum == 0 or (oid, attnum) in seen_attnum:
            raise CaptureError("ambiguous or unmapped column metadata")
        if any(type(v) is not bool for v in (not_null, has_default, dropped)):
            raise CaptureError("invalid PostgreSQL column flags")
        seen_attnum.add((oid, attnum))
        observed[oid]["columns"].append({"attnum": attnum, "name": name, "pg_type": pg_type,
                                         "not_null": not_null, "default_expr": "present" if has_default else None,
                                         "identity": identity, "generated": generated, "dropped": dropped})
    return {"version": "ores.orm.pg17-capture/v1", "cluster_system_identifier": sysid,
            "database_oid": database_oid, "server_version_num": version,
            "unmodeled_database_objects": unsupported,
            "tables": [observed[k] for k in sorted(observed)]}


def capture_from_dsn(dsn):
    """Psycopg3 optional for offline tests. Credentials are never logged."""
    import psycopg
    # Autocommit avoids an implicit transaction before the explicit BEGIN.
    with psycopg.connect(dsn, autocommit=True, connect_timeout=5) as conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            return capture_from_connection(conn)
        finally:
            # Never COMMIT or run SQL write, even on a failed capture.
            with conn.cursor() as cursor:
                cursor.execute("ROLLBACK")
