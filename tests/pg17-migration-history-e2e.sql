-- PostgreSQL 17 SQL-only migration history/replay safety E2E.
-- Executes in a newly named disposable schema, ROLLBACKs every change.
-- This proves a SQL reference contract, NOT checksum of actual migration files.
BEGIN;
DO $version$
BEGIN
  IF current_setting('server_version_num')::integer < 170000
     OR current_setting('server_version_num')::integer >= 180000 THEN
    RAISE EXCEPTION 'PG17 migration history test required';
  END IF;
END
$version$;
CREATE SCHEMA :"fixture_schema";
SET LOCAL search_path TO :"fixture_schema", pg_catalog;
CREATE TABLE applied_migrations (
  version integer PRIMARY KEY CHECK (version > 0),
  sha256_hex text NOT NULL CHECK (sha256_hex ~ '^[0-9a-f]{64}$'),
  applied_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE FUNCTION record_migration(phase integer, digest_hex text)
RETURNS text LANGUAGE plpgsql AS $record$
DECLARE
  prior_digest text;
  last_version integer;
BEGIN
  IF phase IS NULL OR phase <= 0 OR digest_hex IS NULL
     OR digest_hex !~ '^[0-9a-f]{64}$' THEN
    RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'INVALID_MIGRATION_IDENTITY';
  END IF;
  SELECT sha256_hex INTO prior_digest FROM applied_migrations WHERE version = phase;
  IF FOUND THEN
    IF prior_digest <> digest_hex THEN
      RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'MIGRATION_CHECKSUM_DRIFT';
    END IF;
    RETURN 'REPLAY_OK';
  END IF;
  SELECT COALESCE(max(version),0) INTO last_version FROM applied_migrations;
  IF phase <> last_version + 1 THEN
    RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'MIGRATION_ORDER_DRIFT';
  END IF;
  INSERT INTO applied_migrations(version,sha256_hex) VALUES (phase,digest_hex);
  RETURN 'APPLIED';
END
$record$;
-- Stable v1/v2 immutable digests; these are fixture identities, not file digests.
SELECT record_migration(1, repeat('a',64));
SELECT record_migration(1, repeat('a',64));
SELECT record_migration(2, repeat('b',64));
DO $negative$
DECLARE received text;
BEGIN
  BEGIN
    PERFORM record_migration(1, repeat('c',64));
    RAISE EXCEPTION 'FORGED_REPLAY_NOT_REJECTED';
  EXCEPTION WHEN check_violation THEN
    GET STACKED DIAGNOSTICS received = MESSAGE_TEXT;
    IF received <> 'MIGRATION_CHECKSUM_DRIFT' THEN RAISE; END IF;
  END;
  BEGIN
    PERFORM record_migration(4, repeat('d',64));
    RAISE EXCEPTION 'OUT_OF_ORDER_NOT_REJECTED';
  EXCEPTION WHEN check_violation THEN
    GET STACKED DIAGNOSTICS received = MESSAGE_TEXT;
    IF received <> 'MIGRATION_ORDER_DRIFT' THEN RAISE; END IF;
  END;
  BEGIN
    PERFORM record_migration(0, repeat('e',64));
    RAISE EXCEPTION 'INVALID_VERSION_NOT_REJECTED';
  EXCEPTION WHEN check_violation THEN
    GET STACKED DIAGNOSTICS received = MESSAGE_TEXT;
    IF received <> 'INVALID_MIGRATION_IDENTITY' THEN RAISE; END IF;
  END;
  BEGIN
    PERFORM record_migration(3, 'weak-digest');
    RAISE EXCEPTION 'INVALID_DIGEST_NOT_REJECTED';
  EXCEPTION WHEN check_violation THEN
    GET STACKED DIAGNOSTICS received = MESSAGE_TEXT;
    IF received <> 'INVALID_MIGRATION_IDENTITY' THEN RAISE; END IF;
  END;
  BEGIN
    PERFORM record_migration(3, NULL);
    RAISE EXCEPTION 'NULL_DIGEST_NOT_REJECTED';
  EXCEPTION WHEN check_violation THEN
    GET STACKED DIAGNOSTICS received = MESSAGE_TEXT;
    IF received <> 'INVALID_MIGRATION_IDENTITY' THEN RAISE; END IF;
  END;
  BEGIN
    PERFORM record_migration(NULL, repeat('e',64));
    RAISE EXCEPTION 'NULL_VERSION_NOT_REJECTED';
  EXCEPTION WHEN check_violation THEN
    GET STACKED DIAGNOSTICS received = MESSAGE_TEXT;
    IF received <> 'INVALID_MIGRATION_IDENTITY' THEN RAISE; END IF;
  END;
  BEGIN
    PERFORM record_migration(3, repeat('A',64));
    RAISE EXCEPTION 'UPPERCASE_DIGEST_NOT_REJECTED';
  EXCEPTION WHEN check_violation THEN
    GET STACKED DIAGNOSTICS received = MESSAGE_TEXT;
    IF received <> 'INVALID_MIGRATION_IDENTITY' THEN RAISE; END IF;
  END;
END
$negative$;
SELECT count(*) FROM applied_migrations;
SELECT count(*) FROM applied_migrations WHERE version = 1 AND sha256_hex = repeat('a',64);
SELECT 'PG17_MIGRATION_HISTORY_E2E_OK';
ROLLBACK;
SELECT count(*) FROM pg_catalog.pg_namespace WHERE nspname = :'fixture_schema';
