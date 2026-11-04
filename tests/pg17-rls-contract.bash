#!/usr/bin/env bash
# PostgreSQL 17 role/RLS and prepared-plan reuse contract, SQL-only.
# NOT proof of Oreslang actor ownership, pool reset, or a live Oreslang driver.
set -euo pipefail
fail() { printf 'PG_RLS_NOT_VERIFIED: %s\n' "$*" >&2; exit 1; }
[[ "${PG_TEST_DISPOSABLE:-}" == I_ACKNOWLEDGE_DISPOSABLE_DATABASE ]] ||
  fail 'disposable database opt-in required'
[[ -n "${PG_TEST_DSN:-}" ]] || fail 'PG_TEST_DSN missing'
command -v psql >/dev/null 2>&1 || fail 'psql unavailable'

major="$(psql -X -qAt -v ON_ERROR_STOP=1 "$PG_TEST_DSN" -c 'SHOW server_version_num')" ||
  fail 'server version probe failed'
[[ "$major" =~ ^17[0-9]{4}$ ]] || fail 'PostgreSQL 17 required'

suffix="${RANDOM}_${RANDOM}_$$"
schema="ores_rls_${suffix}"
role_a="ores_rls_a_${suffix}"
role_b="ores_rls_b_${suffix}"
for ident in "$schema" "$role_a" "$role_b"; do
  [[ "$ident" =~ ^[a-z0-9_]{1,63}$ ]] || fail "invalid generated identifier: $ident"
done

cleanup() {
  set +e
  psql -X -q -v ON_ERROR_STOP=0 \
    -v "contract_schema=$schema" -v "role_a=$role_a" -v "role_b=$role_b" \
    "$PG_TEST_DSN" >/dev/null 2>&1 <<'SQL'
DROP SCHEMA IF EXISTS :"contract_schema" CASCADE;
DROP ROLE IF EXISTS :"role_a";
DROP ROLE IF EXISTS :"role_b";
SQL
}
trap cleanup EXIT

psql -X -q -v ON_ERROR_STOP=1 \
  -v "contract_schema=$schema" -v "role_a=$role_a" -v "role_b=$role_b" \
  "$PG_TEST_DSN" <<'SQL'
CREATE SCHEMA :"contract_schema";
CREATE ROLE :"role_a" NOLOGIN;
CREATE ROLE :"role_b" NOLOGIN;
GRANT USAGE ON SCHEMA :"contract_schema" TO :"role_a", :"role_b";
CREATE TABLE :"contract_schema".records (
  workspace_id uuid NOT NULL,
  id uuid NOT NULL,
  payload text NOT NULL,
  PRIMARY KEY (workspace_id, id)
);
ALTER TABLE :"contract_schema".records ENABLE ROW LEVEL SECURITY;
ALTER TABLE :"contract_schema".records FORCE ROW LEVEL SECURITY;
GRANT SELECT, INSERT, UPDATE, DELETE ON :"contract_schema".records TO :"role_a", :"role_b";
CREATE POLICY tenant_isolation ON :"contract_schema".records
  USING (
    (current_user = :'role_a' AND workspace_id = '00000000-0000-0000-0000-000000000001'::uuid)
    OR
    (current_user = :'role_b' AND workspace_id = '00000000-0000-0000-0000-000000000002'::uuid)
  )
  WITH CHECK (
    (current_user = :'role_a' AND workspace_id = '00000000-0000-0000-0000-000000000001'::uuid)
    OR
    (current_user = :'role_b' AND workspace_id = '00000000-0000-0000-0000-000000000002'::uuid)
  );
INSERT INTO :"contract_schema".records VALUES
 ('00000000-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000010','record-a'),
 ('00000000-0000-0000-0000-000000000002',
  '00000000-0000-0000-0000-000000000010','record-b');
SQL

reuse="$({ psql -X -qAt -v ON_ERROR_STOP=1 \
  -v "contract_schema=$schema" -v "role_a=$role_a" -v "role_b=$role_b" \
  "$PG_TEST_DSN" <<'SQL'
SET ROLE :"role_a";
SELECT current_user;
SELECT payload FROM :"contract_schema".records ORDER BY payload;
PREPARE by_id(uuid) AS
  SELECT payload FROM :"contract_schema".records WHERE id = $1 ORDER BY payload;
EXECUTE by_id('00000000-0000-0000-0000-000000000010');
RESET ROLE;
SET ROLE :"role_b";
SELECT current_user;
SELECT payload FROM :"contract_schema".records ORDER BY payload;
EXECUTE by_id('00000000-0000-0000-0000-000000000010');
DEALLOCATE by_id;
RESET ROLE;
SQL
} 2>&1)" || fail 'role/RLS prepared-plan reuse failed'
expected="$(printf '%s\nrecord-a\nrecord-a\n%s\nrecord-b\nrecord-b' "$role_a" "$role_b")"
[[ "$reuse" == "$expected" ]] || fail "unexpected role/RLS reuse result: $reuse"

write_checks="$({ psql -X -qAt -v ON_ERROR_STOP=1 \
  -v "contract_schema=$schema" -v "role_a=$role_a" \
  "$PG_TEST_DSN" <<'SQL'
SET ROLE :"role_a";
WITH changed AS (
  UPDATE :"contract_schema".records
  SET payload = 'cross-tenant-update'
  WHERE workspace_id = '00000000-0000-0000-0000-000000000002'::uuid
  RETURNING 1
) SELECT count(*) FROM changed;
WITH removed AS (
  DELETE FROM :"contract_schema".records
  WHERE workspace_id = '00000000-0000-0000-0000-000000000002'::uuid
  RETURNING 1
) SELECT count(*) FROM removed;
INSERT INTO :"contract_schema".records VALUES
 ('00000000-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000011','record-a-2');
SELECT count(*) FROM :"contract_schema".records;
RESET ROLE;
SQL
} 2>&1)" || fail 'same-tenant write checks failed'
[[ "$write_checks" == "$(printf '0\n0\n2')" ]] ||
  fail "cross-tenant update/delete visibility changed: $write_checks"

set +e
denied="$(printf '%s\n' '\set VERBOSITY verbose' \
  "SET ROLE :\"role_a\";" \
  "INSERT INTO :\"contract_schema\".records VALUES ('00000000-0000-0000-0000-000000000002','00000000-0000-0000-0000-000000000012','forbidden');" |
  psql -X -qAt -v ON_ERROR_STOP=1 \
    -v "contract_schema=$schema" -v "role_a=$role_a" \
    "$PG_TEST_DSN" 2>&1)"
status=$?
set -e
[[ $status -ne 0 ]] || fail 'cross-tenant insert unexpectedly succeeded'
grep -Fq '42501' <<<"$denied" || fail "cross-tenant insert lacked SQLSTATE 42501: $denied"

tenant_b_count="$(psql -X -qAt -v ON_ERROR_STOP=1 \
  -v "contract_schema=$schema" -v "role_b=$role_b" \
  "$PG_TEST_DSN" <<'SQL'
SET ROLE :"role_b";
SELECT count(*) FROM :"contract_schema".records;
RESET ROLE;
SQL
)" || fail 'tenant B post-denial query failed'
[[ "$tenant_b_count" == "1" ]] || fail "tenant B row was modified or leaked: $tenant_b_count"

# Exercise effective session privileges, rather than only a privileged login
# performing SET ROLE. A fresh superuser-owned test connection demotes its
# session authorization to the untrusted role; PostgreSQL must then deny
# switching directly to the other tenant role.
nonprivileged="$(psql -X -qAt -v ON_ERROR_STOP=1 \
  -v "contract_schema=$schema" -v "role_a=$role_a" \
  "$PG_TEST_DSN" <<'SQL'
SET SESSION AUTHORIZATION :"role_a";
SELECT current_user = session_user;
SELECT count(*) FROM :"contract_schema".records;
SQL
)" || fail 'unprivileged tenant query failed'
[[ "$nonprivileged" == "$(printf 't\n2')" ]] ||
  fail "unprivileged tenant authorization/visibility mismatch: $nonprivileged"

set +e
switch_denied="$(printf '%s\n' '\set VERBOSITY verbose' \
  "SET SESSION AUTHORIZATION :\"role_a\";" \
  "SET ROLE :\"role_b\";" | \
  psql -X -qAt -v ON_ERROR_STOP=1 \
    -v "role_a=$role_a" -v "role_b=$role_b" \
    "$PG_TEST_DSN" 2>&1)"
switch_status=$?
set -e
[[ $switch_status -ne 0 ]] || fail 'unprivileged tenant switched to another tenant role'
grep -Fq '42501' <<<"$switch_denied" ||
  fail "unprivileged role switch did not return SQLSTATE 42501: $switch_denied"

# A role may UPDATE its own visible row, but RLS WITH CHECK must reject
# re-keying it into the other tenant's workspace. Use a distinct row ID to
# ensure the rejection is policy SQLSTATE 42501, not a PK collision (23505).
set +e
rekey_denied="$(printf '%s\n' '\set VERBOSITY verbose' \
  "SET SESSION AUTHORIZATION :\"role_a\";" \
  "UPDATE :\"contract_schema\".records SET workspace_id = '00000000-0000-0000-0000-000000000002'::uuid WHERE workspace_id = '00000000-0000-0000-0000-000000000001'::uuid AND id = '00000000-0000-0000-0000-000000000011'::uuid;" | \
  psql -X -qAt -v ON_ERROR_STOP=1 \
    -v "contract_schema=$schema" -v "role_a=$role_a" \
    "$PG_TEST_DSN" 2>&1)"
rekey_status=$?
set -e
[[ $rekey_status -ne 0 ]] || fail 'tenant A moved its own row to tenant B'
grep -Fq '42501' <<<"$rekey_denied" ||
  fail "tenant-key UPDATE denial lacked SQLSTATE 42501: $rekey_denied"

rekey_state="$(psql -X -qAt -v ON_ERROR_STOP=1 \
  -v "contract_schema=$schema" -v "role_a=$role_a" -v "role_b=$role_b" \
  "$PG_TEST_DSN" <<'SQL'
SET ROLE :"role_a";
SELECT payload FROM :"contract_schema".records
 WHERE workspace_id = '00000000-0000-0000-0000-000000000001'::uuid
   AND id = '00000000-0000-0000-0000-000000000011'::uuid;
RESET ROLE;
SET ROLE :"role_b";
SELECT count(*) FROM :"contract_schema".records;
RESET ROLE;
SQL
)" || fail 'tenant-key denial poststate could not be read'
[[ "$rekey_state" == "$(printf 'record-a-2\n1')" ]] ||
  fail "tenant-key UPDATE modified tenant A or B records: $rekey_state"

printf '%s\n' 'PG_RLS_SQL_ONLY_PASS'
