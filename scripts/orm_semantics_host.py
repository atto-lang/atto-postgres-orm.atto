"""Host-only semantic checks for *already shape-validated* ORM v1 JSON.

This is not an Oreslang oracle, TypeSpec parity proof, PostgreSQL driver,
or migration approval/execution capability. Validate against the pinned
Draft 2020-12 schema before invoking these cross-item checks.
"""

EXCLUSIVE_TABLE_OPS = frozenset({"review_create_table", "review_drop_table"})
EXCLUSIVE_COLUMN_OPS = frozenset({
    "drop_column", "add_nullable_column", "add_required_column",
})
NULLABILITY_OPS = frozenset({"set_not_null", "drop_not_null"})


def check_catalog_semantics(catalog):
    """Reject duplicate stable identities and physical names at both levels."""
    table_ids = set()
    table_names = set()
    for table in catalog["tables"]:
        if table["stable_id"] in table_ids or table["name"] in table_names:
            raise ValueError("ambiguous catalog table identity")
        table_ids.add(table["stable_id"])
        table_names.add(table["name"])
        column_ids = set()
        column_names = set()
        for column in table["columns"]:
            if column["stable_id"] in column_ids or column["name"] in column_names:
                raise ValueError("ambiguous catalog column identity")
            column_ids.add(column["stable_id"])
            column_names.add(column["name"])


def check_review_semantics(manifest):
    """Reject contradictory review-only steps regardless of input order.

    Distinct rename, type-change and nullability operations may coexist on
    an existing column. Create/drop operations cannot overlap other changes
    for the same target, and opposite nullability edits cannot coexist.
    """
    steps = manifest["steps"]
    seen = set()
    by_table = {}
    by_column = {}
    for step in steps:
        key = (step["op"], step["table_id"], step["column_id"])
        if key in seen:
            raise ValueError("duplicate review operation")
        seen.add(key)
        by_table.setdefault(step["table_id"], []).append(step["op"])
        if step["column_id"]:
            by_column.setdefault((step["table_id"], step["column_id"]), []).append(step["op"])
    for ops in by_table.values():
        if len(ops) > 1 and EXCLUSIVE_TABLE_OPS.intersection(ops):
            raise ValueError("table create/drop conflicts with other review operations")
    for ops in by_column.values():
        if len(ops) > 1 and EXCLUSIVE_COLUMN_OPS.intersection(ops):
            raise ValueError("column create/drop conflicts with other review operations")
        if NULLABILITY_OPS.issubset(ops):
            raise ValueError("opposite nullability review operations")
