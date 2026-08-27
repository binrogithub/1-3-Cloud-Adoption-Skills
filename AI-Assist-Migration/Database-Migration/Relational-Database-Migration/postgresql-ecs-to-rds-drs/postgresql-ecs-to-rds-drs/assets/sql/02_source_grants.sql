-- ============================================================================
-- 02 - Grants for the DRS replication user
-- Run against the SOURCE database, as a superuser.
--
--   psql -h <source_eip> -p 5432 -d <source_db> -U <admin_user> \
--        -v repl_user=drs_replicator -P pager=off -f 02_source_grants.sql
--
-- Run this ONLY if script 01 showed missing privileges.
-- These are GRANT statements only. No data is read, written or altered.
--
-- Note on schemas: this covers the "public" schema. If the database uses
-- additional schemas, repeat the GRANT / ALTER DEFAULT PRIVILEGES blocks
-- for each one.
-- ============================================================================

\set ON_ERROR_STOP on

-- Connect privilege on the database being migrated
GRANT CONNECT ON DATABASE :"repl_user_db" TO :"repl_user";

-- Schema access
GRANT USAGE ON SCHEMA public TO :"repl_user";

-- Read access to existing tables
GRANT SELECT ON ALL TABLES IN SCHEMA public TO :"repl_user";

-- Read access to tables created later
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT ON TABLES TO :"repl_user";

-- SEQUENCES - the most commonly forgotten grant.
-- Without these, the DRS pre-check fails with
-- FULL_PG_SRC_DB_PRIVI_IS_NOT_ENOUGH_V2
GRANT SELECT, USAGE ON ALL SEQUENCES IN SCHEMA public TO :"repl_user";

ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, USAGE ON SEQUENCES TO :"repl_user";

\echo '=== Grants applied. Verification: ==='

SELECT rolname, rolreplication, rolcanlogin
FROM pg_roles
WHERE rolname = :'repl_user';

SELECT count(*) AS tables_readable
FROM information_schema.table_privileges
WHERE grantee = :'repl_user'
  AND privilege_type = 'SELECT';

SELECT count(*) AS sequences_readable
FROM information_schema.usage_privileges
WHERE grantee = :'repl_user'
  AND object_type = 'SEQUENCE';
