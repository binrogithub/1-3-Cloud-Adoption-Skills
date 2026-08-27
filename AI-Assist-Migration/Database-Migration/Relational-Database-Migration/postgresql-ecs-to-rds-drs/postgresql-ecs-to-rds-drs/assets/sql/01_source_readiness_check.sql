-- ============================================================================
-- 01 - Source readiness check
--
-- WHERE TO RUN: inside the source ECS, over SSH.
-- WHY THERE: the "postgres" superuser normally has no remote-access entry in
-- pg_hba.conf, so running this remotely would just be refused.
--
--   scp 01_source_readiness_check.sql root@<source_eip>:/tmp/
--   ssh root@<source_eip>
--   sudo -u postgres psql -P pager=off -d <source_db> \
--        -f /tmp/01_source_readiness_check.sql
--
-- READ ONLY. Nothing here modifies anything.
-- Paste the full output back to the assistant.
-- ============================================================================

\echo '=== 1. Server version ==='
SELECT version() AS server_version;
SELECT current_setting('server_version_num')::int / 10000 AS major_version;

\echo '=== 2. Logical replication settings (required by DRS) ==='
SELECT name,
       setting,
       CASE
         WHEN name = 'wal_level'             AND setting = 'logical' THEN 'OK'
         WHEN name = 'max_replication_slots' AND setting::int >= 1   THEN 'OK'
         WHEN name = 'max_wal_senders'       AND setting::int >= 1   THEN 'OK'
         ELSE 'NEEDS CHANGE - requires a restart'
       END AS status
FROM pg_settings
WHERE name IN ('wal_level', 'max_replication_slots', 'max_wal_senders')
ORDER BY name;

\echo '=== 3. Authentication method - decides the pg_hba.conf entry in step 6 ==='
SELECT current_setting('password_encryption') AS password_encryption;

\echo '=== 4. Server-level locale - the target RDS must match ==='
-- NOTE: on PostgreSQL 16+, lc_collate and lc_ctype are no longer server
-- settings, so they do not appear here. They are database properties and are
-- reported in section 5 below. This is expected, not a missing result.
SELECT name, setting
FROM pg_settings
WHERE name IN ('lc_monetary', 'lc_numeric', 'lc_time', 'server_encoding')
ORDER BY name;

\echo '=== 5. Database-level locale and encoding (source of truth for collate/ctype) ==='
SELECT datname,
       pg_encoding_to_char(encoding) AS encoding,
       datcollate                    AS lc_collate,
       datctype                      AS lc_ctype
FROM pg_database
WHERE datname = current_database();

\echo '=== 6. Roles with REPLICATION privilege ==='
SELECT rolname, rolreplication, rolcanlogin
FROM pg_roles
WHERE rolreplication = true
ORDER BY rolname;

\echo '=== 7. Table privileges of each replication-capable role ==='
SELECT grantee,
       count(*) AS tables_with_select
FROM information_schema.table_privileges
WHERE privilege_type = 'SELECT'
  AND grantee IN (SELECT rolname FROM pg_roles WHERE rolreplication = true)
GROUP BY grantee
ORDER BY grantee;

\echo '=== 8. Sequence privileges - missing grants cause a pre-check failure ==='
SELECT r.rolname AS grantee,
       count(c.oid) FILTER (
         WHERE has_sequence_privilege(r.rolname, c.oid, 'SELECT')
       ) AS sequences_readable,
       count(c.oid) AS sequences_total
FROM pg_roles r
CROSS JOIN pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE r.rolreplication = true
  AND c.relkind = 'S'
  AND n.nspname NOT IN ('pg_catalog', 'information_schema')
GROUP BY r.rolname
ORDER BY r.rolname;

\echo '=== 9. Installed extensions - must be supported by the target RDS ==='
SELECT extname, extversion
FROM pg_extension
ORDER BY extname;

\echo '=== 10. Replication slots currently in use ==='
SELECT slot_name, plugin, slot_type, active
FROM pg_replication_slots;

\echo '=== 11. Tables without a primary key (incremental replication risk) ==='
SELECT n.nspname AS schema_name,
       c.relname AS table_name
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind = 'r'
  AND n.nspname NOT IN ('pg_catalog', 'information_schema')
  AND NOT EXISTS (
        SELECT 1 FROM pg_constraint k
        WHERE k.conrelid = c.oid AND k.contype = 'p'
      )
ORDER BY 1, 2;

\echo '=== 12. Database size - the target disk must be larger than this ==='
SELECT pg_size_pretty(pg_database_size(current_database())) AS database_size;
