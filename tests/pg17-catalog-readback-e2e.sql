-- PostgreSQL 17 SQL-only catalog introspection and transactional migration E2E.
-- Invoked ONLY by the disposable-DB guard in pg17-catalog-readback-e2e.bash.
-- This v1 projection cannot certify keys, indexes, grants, RLS, or stable IDs.
BEGIN;
DO $pg17$
BEGIN
  IF current_setting('server_version_num')::integer < 170000
    OR current_setting('server_version_num')::integer >= 180000 THEN
    RAISE EXCEPTION 'PostgreSQL 17 server required';
  END IF;
END
$pg17$;
CREATE SCHEMA :"fixture_schema";
SET LOCAL search_path TO :"fixture_schema", pg_catalog;
CREATE TABLE accounts (
  workspace_id uuid NOT NULL,
  id uuid NOT NULL,
  label text NOT NULL,
  PRIMARY KEY (workspace_id, id)
);
CREATE FUNCTION assert_shape(expected text) RETURNS void
LANGUAGE plpgsql AS $check$
DECLARE actual text;
BEGIN
  SELECT string_agg(
    a.attname || ':' || pg_catalog.format_type(a.atttypid,a.atttypmod)
      || ':' || a.attnotnull::text, ',' ORDER BY a.attnum
  ) INTO actual
  FROM pg_catalog.pg_attribute a
  WHERE a.attrelid = 'accounts'::regclass AND a.attnum > 0
    AND NOT a.attisdropped;
  IF actual IS DISTINCT FROM expected THEN
    RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'CATALOG_SHAPE_DRIFT';
  END IF;
END
$check$;
DO $baseline$
BEGIN
  PERFORM assert_shape('workspace_id:uuid:true,id:uuid:true,label:text:true');
END
$baseline$;
-- Actual catalog migration, repeated under a stable precondition.
DO $first_migration$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_attribute
    WHERE attrelid='accounts'::regclass AND attname='notes' AND NOT attisdropped) THEN
    ALTER TABLE accounts ADD COLUMN notes text;
  END IF;
END
$first_migration$;
DO $idempotency$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_attribute
    WHERE attrelid='accounts'::regclass AND attname='notes' AND NOT attisdropped) THEN
    ALTER TABLE accounts ADD COLUMN notes text;
  END IF;
  PERFORM assert_shape(
    'workspace_id:uuid:true,id:uuid:true,label:text:true,notes:text:false');
END
$idempotency$;
-- Every injected drift must be rejected, and its subtransaction undone.
DO $negative$
DECLARE drift_message text;
BEGIN
  BEGIN
    ALTER TABLE accounts ALTER COLUMN notes TYPE integer USING NULL::integer;
    PERFORM assert_shape(
      'workspace_id:uuid:true,id:uuid:true,label:text:true,notes:text:false');
    RAISE EXCEPTION 'TYPE_DRIFT_NOT_CAUGHT';
  EXCEPTION WHEN check_violation THEN
    GET STACKED DIAGNOSTICS drift_message = MESSAGE_TEXT;
    IF drift_message <> 'CATALOG_SHAPE_DRIFT' THEN
      RAISE EXCEPTION 'WRONG_DRIFT_DIAGNOSTIC: %', drift_message;
    END IF;
  END;
  BEGIN
    ALTER TABLE accounts RENAME COLUMN label TO substituted_label;
    PERFORM assert_shape(
      'workspace_id:uuid:true,id:uuid:true,label:text:true,notes:text:false');
    RAISE EXCEPTION 'RENAME_DRIFT_NOT_CAUGHT';
  EXCEPTION WHEN check_violation THEN
    GET STACKED DIAGNOSTICS drift_message = MESSAGE_TEXT;
    IF drift_message <> 'CATALOG_SHAPE_DRIFT' THEN
      RAISE EXCEPTION 'WRONG_DRIFT_DIAGNOSTIC: %', drift_message;
    END IF;
  END;
  BEGIN
    ALTER TABLE accounts ADD COLUMN injected boolean;
    PERFORM assert_shape(
      'workspace_id:uuid:true,id:uuid:true,label:text:true,notes:text:false');
    RAISE EXCEPTION 'EXTRA_COLUMN_NOT_CAUGHT';
  EXCEPTION WHEN check_violation THEN
    GET STACKED DIAGNOSTICS drift_message = MESSAGE_TEXT;
    IF drift_message <> 'CATALOG_SHAPE_DRIFT' THEN
      RAISE EXCEPTION 'WRONG_DRIFT_DIAGNOSTIC: %', drift_message;
    END IF;
  END;
  BEGIN
    ALTER TABLE accounts ALTER COLUMN label DROP NOT NULL;
    PERFORM assert_shape(
      'workspace_id:uuid:true,id:uuid:true,label:text:true,notes:text:false');
    RAISE EXCEPTION 'NULLABILITY_DRIFT_NOT_CAUGHT';
  EXCEPTION WHEN check_violation THEN
    GET STACKED DIAGNOSTICS drift_message = MESSAGE_TEXT;
    IF drift_message <> 'CATALOG_SHAPE_DRIFT' THEN
      RAISE EXCEPTION 'WRONG_DRIFT_DIAGNOSTIC: %', drift_message;
    END IF;
  END;
  BEGIN
    ALTER TABLE accounts DROP COLUMN label;
    PERFORM assert_shape(
      'workspace_id:uuid:true,id:uuid:true,label:text:true,notes:text:false');
    RAISE EXCEPTION 'COLUMN_DROP_NOT_CAUGHT';
  EXCEPTION WHEN check_violation THEN
    GET STACKED DIAGNOSTICS drift_message = MESSAGE_TEXT;
    IF drift_message <> 'CATALOG_SHAPE_DRIFT' THEN
      RAISE EXCEPTION 'WRONG_DRIFT_DIAGNOSTIC: %', drift_message;
    END IF;
  END;
  PERFORM assert_shape(
    'workspace_id:uuid:true,id:uuid:true,label:text:true,notes:text:false');
END
$negative$;
SELECT 'PG17_CATALOG_E2E_OK';
ROLLBACK;
SELECT count(*) FROM pg_catalog.pg_namespace WHERE nspname = :'fixture_schema';
