-- SQL-only PostgreSQL 17: protect catalog objects omitted by v1 column snapshots.
-- Use only from a disposable-DB guard. This is not native Oreslang or DPM proof.
BEGIN;
DO $version_guard$
BEGIN
  IF current_setting('server_version_num')::integer NOT BETWEEN 170000 AND 179999 THEN
    RAISE EXCEPTION 'PostgreSQL 17 required for metadata E2E';
  END IF;
END
$version_guard$;
CREATE SCHEMA :"fixture_schema";
SET LOCAL search_path TO :"fixture_schema", pg_catalog;
CREATE TABLE guarded_records (
  workspace_id uuid NOT NULL,
  id bigint NOT NULL,
  status text NOT NULL DEFAULT 'open',
  CONSTRAINT guarded_records_pkey PRIMARY KEY (workspace_id,id),
  CONSTRAINT status_allowed CHECK (status IN ('open','closed'))
);
CREATE UNIQUE INDEX guarded_status_unique ON guarded_records(workspace_id,status);
ALTER TABLE guarded_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE guarded_records FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_guard ON guarded_records
  USING (workspace_id = '00000000-0000-0000-0000-000000000001'::uuid)
  WITH CHECK (workspace_id = '00000000-0000-0000-0000-000000000001'::uuid);
CREATE TEMP TABLE expected_policy ON COMMIT DROP AS
  SELECT pg_get_expr(polqual,polrelid) AS using_expr,
         pg_get_expr(polwithcheck,polrelid) AS check_expr,
         polroles AS expected_roles
  FROM pg_catalog.pg_policy
  WHERE polrelid='guarded_records'::regclass AND polname='tenant_guard';
CREATE TEMP TABLE expected_default ON COMMIT DROP AS
  SELECT pg_get_expr(d.adbin,d.adrelid) AS default_expr
  FROM pg_catalog.pg_attrdef d
  JOIN pg_catalog.pg_attribute a
    ON a.attrelid=d.adrelid AND a.attnum=d.adnum
  WHERE d.adrelid='guarded_records'::regclass AND a.attname='status';
-- Compare definitions, not just object name and existence, to catch
-- same-name constraint/index substitution.
CREATE TEMP TABLE expected_constraint_defs ON COMMIT DROP AS
  SELECT conname, pg_catalog.pg_get_constraintdef(oid) AS definition
  FROM pg_catalog.pg_constraint
  WHERE conrelid='guarded_records'::regclass AND contype IN ('p','c');
CREATE TEMP TABLE expected_index_def ON COMMIT DROP AS
  SELECT pg_catalog.pg_get_indexdef(i.indexrelid) AS definition
  FROM pg_catalog.pg_index i
  JOIN pg_catalog.pg_class idx ON idx.oid=i.indexrelid
  WHERE i.indrelid='guarded_records'::regclass
    AND idx.relname='guarded_status_unique';
CREATE FUNCTION assert_protected_metadata() RETURNS void
LANGUAGE plpgsql AS $assert$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_class
    WHERE oid='guarded_records'::regclass AND relrowsecurity AND relforcerowsecurity
  ) OR NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_constraint
    WHERE conrelid='guarded_records'::regclass
      AND conname='guarded_records_pkey' AND contype='p'
  ) OR NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_constraint
    WHERE conrelid='guarded_records'::regclass
      AND conname='status_allowed' AND contype='c'
  ) OR NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_index i
    JOIN pg_catalog.pg_class idx ON idx.oid=i.indexrelid
    WHERE i.indrelid='guarded_records'::regclass
      AND idx.relname='guarded_status_unique' AND i.indisunique AND i.indisvalid
  ) OR (SELECT count(*) FROM pg_catalog.pg_index
        WHERE indrelid='guarded_records'::regclass) <> 2
     OR (SELECT count(*) FROM pg_catalog.pg_constraint
        WHERE conrelid='guarded_records'::regclass AND contype IN ('p','c')) <> 2
     OR EXISTS (
    SELECT 1 FROM expected_constraint_defs base
    WHERE NOT EXISTS (
      SELECT 1 FROM pg_catalog.pg_constraint c
      WHERE c.conrelid='guarded_records'::regclass AND c.conname=base.conname
        AND pg_catalog.pg_get_constraintdef(c.oid)=base.definition
    )
  ) OR NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_index i
    JOIN pg_catalog.pg_class idx ON idx.oid=i.indexrelid
    CROSS JOIN expected_index_def base
    WHERE i.indrelid='guarded_records'::regclass
      AND idx.relname='guarded_status_unique'
      AND pg_catalog.pg_get_indexdef(i.indexrelid)=base.definition
  ) OR (SELECT count(*) FROM pg_catalog.pg_policy
        WHERE polrelid='guarded_records'::regclass) <> 1
     OR NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_policy p CROSS JOIN expected_policy b
    WHERE p.polrelid='guarded_records'::regclass AND p.polname='tenant_guard'
      AND p.polpermissive AND p.polcmd='*' AND p.polroles=b.expected_roles
      AND pg_get_expr(p.polqual,p.polrelid) = b.using_expr
      AND pg_get_expr(p.polwithcheck,p.polrelid) = b.check_expr
  ) OR NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_attrdef d
    JOIN pg_catalog.pg_attribute a ON a.attrelid=d.adrelid AND a.attnum=d.adnum
    CROSS JOIN expected_default b
    WHERE d.adrelid='guarded_records'::regclass AND a.attname='status'
      AND pg_get_expr(d.adbin,d.adrelid) = b.default_expr
  ) THEN
    RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='PROTECTED_CATALOG_DRIFT';
  END IF;
END
$assert$;
DO $baseline$
BEGIN
  PERFORM assert_protected_metadata();
  ALTER TABLE guarded_records ADD COLUMN notes text;
  PERFORM assert_protected_metadata();
END
$baseline$;
DO $negative$
DECLARE diagnostic text;
BEGIN
  BEGIN
    ALTER TABLE guarded_records DISABLE ROW LEVEL SECURITY;
    PERFORM assert_protected_metadata();
    RAISE EXCEPTION 'RLS_DISABLE_UNDETECTED';
  EXCEPTION WHEN check_violation THEN
    GET STACKED DIAGNOSTICS diagnostic = MESSAGE_TEXT;
    IF diagnostic <> 'PROTECTED_CATALOG_DRIFT' THEN RAISE; END IF;
  END;
  BEGIN
    ALTER TABLE guarded_records NO FORCE ROW LEVEL SECURITY;
    PERFORM assert_protected_metadata();
    RAISE EXCEPTION 'RLS_FORCE_UNDETECTED';
  EXCEPTION WHEN check_violation THEN
    GET STACKED DIAGNOSTICS diagnostic = MESSAGE_TEXT;
    IF diagnostic <> 'PROTECTED_CATALOG_DRIFT' THEN RAISE; END IF;
  END;
  BEGIN
    DROP POLICY tenant_guard ON guarded_records;
    PERFORM assert_protected_metadata();
    RAISE EXCEPTION 'POLICY_DROP_UNDETECTED';
  EXCEPTION WHEN check_violation THEN
    GET STACKED DIAGNOSTICS diagnostic = MESSAGE_TEXT;
    IF diagnostic <> 'PROTECTED_CATALOG_DRIFT' THEN RAISE; END IF;
  END;
  BEGIN
    ALTER POLICY tenant_guard ON guarded_records USING (true);
    PERFORM assert_protected_metadata();
    RAISE EXCEPTION 'POLICY_WEAKEN_UNDETECTED';
  EXCEPTION WHEN check_violation THEN
    GET STACKED DIAGNOSTICS diagnostic = MESSAGE_TEXT;
    IF diagnostic <> 'PROTECTED_CATALOG_DRIFT' THEN RAISE; END IF;
  END;
  BEGIN
    ALTER POLICY tenant_guard ON guarded_records TO CURRENT_USER;
    PERFORM assert_protected_metadata();
    RAISE EXCEPTION 'POLICY_ROLE_CHANGE_UNDETECTED';
  EXCEPTION WHEN check_violation THEN
    GET STACKED DIAGNOSTICS diagnostic = MESSAGE_TEXT;
    IF diagnostic <> 'PROTECTED_CATALOG_DRIFT' THEN RAISE; END IF;
  END;
  BEGIN
    CREATE POLICY added_permissive_policy ON guarded_records USING (true);
    PERFORM assert_protected_metadata();
    RAISE EXCEPTION 'EXTRA_PERMISSIVE_POLICY_UNDETECTED';
  EXCEPTION WHEN check_violation THEN
    GET STACKED DIAGNOSTICS diagnostic = MESSAGE_TEXT;
    IF diagnostic <> 'PROTECTED_CATALOG_DRIFT' THEN RAISE; END IF;
  END;
  BEGIN
    DROP INDEX guarded_status_unique;
    PERFORM assert_protected_metadata();
    RAISE EXCEPTION 'UNIQUE_INDEX_DROP_UNDETECTED';
  EXCEPTION WHEN check_violation THEN
    GET STACKED DIAGNOSTICS diagnostic = MESSAGE_TEXT;
    IF diagnostic <> 'PROTECTED_CATALOG_DRIFT' THEN RAISE; END IF;
  END;
  BEGIN
    ALTER TABLE guarded_records DROP CONSTRAINT status_allowed;
    PERFORM assert_protected_metadata();
    RAISE EXCEPTION 'CHECK_CONSTRAINT_DROP_UNDETECTED';
  EXCEPTION WHEN check_violation THEN
    GET STACKED DIAGNOSTICS diagnostic = MESSAGE_TEXT;
    IF diagnostic <> 'PROTECTED_CATALOG_DRIFT' THEN RAISE; END IF;
  END;
  BEGIN
    ALTER TABLE guarded_records ALTER COLUMN status SET DEFAULT 'closed';
    PERFORM assert_protected_metadata();
    RAISE EXCEPTION 'DEFAULT_CHANGE_UNDETECTED';
  EXCEPTION WHEN check_violation THEN
    GET STACKED DIAGNOSTICS diagnostic = MESSAGE_TEXT;
    IF diagnostic <> 'PROTECTED_CATALOG_DRIFT' THEN RAISE; END IF;
  END;
  BEGIN
    DROP INDEX guarded_status_unique;
    CREATE UNIQUE INDEX guarded_status_unique ON guarded_records(id);
    PERFORM assert_protected_metadata();
    RAISE EXCEPTION 'INDEX_DEFINITION_SUBSTITUTION_UNDETECTED';
  EXCEPTION WHEN check_violation THEN
    GET STACKED DIAGNOSTICS diagnostic = MESSAGE_TEXT;
    IF diagnostic <> 'PROTECTED_CATALOG_DRIFT' THEN RAISE; END IF;
  END;
  BEGIN
    ALTER TABLE guarded_records DROP CONSTRAINT status_allowed;
    ALTER TABLE guarded_records ADD CONSTRAINT status_allowed CHECK (status <> '');
    PERFORM assert_protected_metadata();
    RAISE EXCEPTION 'CHECK_DEFINITION_SUBSTITUTION_UNDETECTED';
  EXCEPTION WHEN check_violation THEN
    GET STACKED DIAGNOSTICS diagnostic = MESSAGE_TEXT;
    IF diagnostic <> 'PROTECTED_CATALOG_DRIFT' THEN RAISE; END IF;
  END;
  BEGIN
    ALTER TABLE guarded_records DROP CONSTRAINT guarded_records_pkey;
    ALTER TABLE guarded_records ADD CONSTRAINT guarded_records_pkey PRIMARY KEY(id);
    PERFORM assert_protected_metadata();
    RAISE EXCEPTION 'PRIMARY_KEY_DEFINITION_SUBSTITUTION_UNDETECTED';
  EXCEPTION WHEN check_violation THEN
    GET STACKED DIAGNOSTICS diagnostic = MESSAGE_TEXT;
    IF diagnostic <> 'PROTECTED_CATALOG_DRIFT' THEN RAISE; END IF;
  END;
  BEGIN
    CREATE UNIQUE INDEX additional_unique ON guarded_records(id);
    PERFORM assert_protected_metadata();
    RAISE EXCEPTION 'ADDITIONAL_UNREVIEWED_INDEX_UNDETECTED';
  EXCEPTION WHEN check_violation THEN
    GET STACKED DIAGNOSTICS diagnostic = MESSAGE_TEXT;
    IF diagnostic <> 'PROTECTED_CATALOG_DRIFT' THEN RAISE; END IF;
  END;
  PERFORM assert_protected_metadata();
END
$negative$;
SELECT 'PG17_METADATA_E2E_OK';
ROLLBACK;
SELECT count(*) FROM pg_catalog.pg_namespace WHERE nspname=:'fixture_schema';
