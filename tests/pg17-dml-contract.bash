#!/usr/bin/env bash
# Disposable PostgreSQL 17 prepared-DML SQL oracle. NOT native Oreslang.
set -euo pipefail
fail() { printf 'PG_DML_NOT_VERIFIED: %s\n' "$*" >&2; exit 1; }
[[ "${PG_TEST_DISPOSABLE:-}" == I_ACKNOWLEDGE_DISPOSABLE_DATABASE ]] || fail 'disposable opt-in required'
[[ -n "${PG_TEST_DSN:-}" ]] || fail 'test database DSN required'
command -v psql >/dev/null 2>&1 || fail 'psql missing'
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
fixture="$root/tests/plans.ores"
[[ -f "$fixture" && ! -L "$fixture" ]] || fail 'fixture unavailable'
for golden in \
  'INSERT INTO \"docs\" (\"workspace_id\", \"id\", \"title\", \"note\") VALUES ($1::uuid, $2::uuid, $3::text, $4::text) RETURNING \"id\"' \
  'UPDATE \"docs\" SET \"title\" = $1::text, \"note\" = $2::text WHERE workspace_id = $3::uuid AND id = $4::uuid'
do
  grep -Fq "$golden" "$fixture" || fail 'authored SQL golden drifted'
done
version="$(psql -X -q -A -t -v ON_ERROR_STOP=1 "$PG_TEST_DSN" -c 'SHOW server_version_num')" ||
  fail 'server version probe failed'
[[ "$version" =~ ^17[0-9]{4}$ ]] || fail 'PostgreSQL 17 server required'
schema="ores_dml_${RANDOM}_${RANDOM}_$$"
[[ "$schema" =~ ^[a-z_][a-z0-9_]{0,62}$ ]] || fail 'invalid test schema'
result="$(psql -X -q -A -t -v ON_ERROR_STOP=1 -v "test_schema=$schema" "$PG_TEST_DSN" <<'SQL'
BEGIN;
CREATE SCHEMA :"test_schema";
SET LOCAL search_path TO :"test_schema", pg_catalog;
CREATE TABLE docs (workspace_id uuid NOT NULL, id uuid NOT NULL, title text NOT NULL, note text,
  PRIMARY KEY (workspace_id, id));
PREPARE insert_doc(uuid, uuid, text, text) AS
  INSERT INTO docs (workspace_id,id,title,note)
  VALUES ($1::uuid,$2::uuid,$3::text,$4::text) RETURNING id;
EXECUTE insert_doc ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'quoted '' title', NULL) \gset
PREPARE update_doc(text,text,uuid,uuid) AS
  UPDATE docs SET title=$1::text, note=$2::text
  WHERE workspace_id=$3::uuid AND id=$4::uuid;
EXECUTE update_doc ('updated '' title', 'literal null',
  'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb');
DO $check$
DECLARE n integer;
BEGIN
  SELECT count(*) INTO n FROM docs WHERE title='updated '' title' AND note='literal null'
    AND workspace_id='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';
  IF n <> 1 THEN RAISE EXCEPTION 'typed prepared DML mismatched'; END IF;
END
$check$;
ROLLBACK;
SELECT count(*) FROM pg_namespace WHERE nspname=:'test_schema';
SQL
)" || fail 'prepared DML SQL execution failed'
[[ "$result" == 0 ]] || fail 'rollback receipt was not zero'
printf '%s\n' 'PG_DML_SQL_ONLY_PASS: prepared INSERT/UPDATE and rollback'
