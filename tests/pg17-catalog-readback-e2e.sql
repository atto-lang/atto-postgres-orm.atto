# PostgreSQL 17 SQL-only integration fixture: read-only catalog projection
SELECT current_setting('server_version_num')::integer BETWEEN 170000 AND 179999 AS pg17;
