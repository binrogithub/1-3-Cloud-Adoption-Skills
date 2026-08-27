-- ============================================================================
-- 04 (DAS) - Target validation, template for the Huawei DAS SQL editor
--
-- WHY THIS FILE EXISTS
-- The DAS SQL Statements Window mangles the quoting in queries that use
-- xpath() / query_to_xml(), and they fail with:
--     ERROR: syntax error at or near "("
-- So the generic version in 04_target_validation_psql.sql cannot be pasted
-- into DAS. This file is the DAS-safe form.
--
-- HOW TO USE IT (assistant)
-- This is a TEMPLATE, not a runnable script. Build the real query from the
-- table names captured in step 2, then give the finished query to the user
-- ready to paste. Do not hand them the template with placeholders in it.
--
-- WHERE TO RUN: Huawei console -> RDS -> instance -> Log In (DAS) ->
--   <db_name> -> SQL Statements Window -> Execute SQL (F8)
--   Full click-by-click path: references/console-navigation.md
--
-- READ ONLY.
-- ============================================================================


-- ----------------------------------------------------------------------------
-- QUERY 1: row count per table
-- One line per table from the step 2 baseline.
-- ----------------------------------------------------------------------------

SELECT '<table_1>' AS tabla, count(*) AS filas FROM <table_1>
UNION ALL SELECT '<table_2>', count(*) FROM <table_2>
UNION ALL SELECT '<table_3>', count(*) FROM <table_3>;

-- Worked example, for a source whose baseline listed five tables:
--
--   SELECT 'demo_customers' AS tabla, count(*) AS filas FROM demo_customers
--   UNION ALL SELECT 'demo_migration_audit', count(*) FROM demo_migration_audit
--   UNION ALL SELECT 'demo_order_items', count(*) FROM demo_order_items
--   UNION ALL SELECT 'demo_orders', count(*) FROM demo_orders
--   UNION ALL SELECT 'demo_products', count(*) FROM demo_products;


-- ----------------------------------------------------------------------------
-- QUERY 2: object counts
-- Safe to paste as-is.
-- ----------------------------------------------------------------------------

SELECT 'tables' AS object_type, count(*) AS total
FROM information_schema.tables
WHERE table_type = 'BASE TABLE'
  AND table_schema NOT IN ('pg_catalog', 'information_schema')
UNION ALL
SELECT 'indexes', count(*)
FROM pg_indexes
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
UNION ALL
SELECT 'sequences', count(*)
FROM information_schema.sequences
WHERE sequence_schema NOT IN ('pg_catalog', 'information_schema')
UNION ALL
SELECT 'extensions', count(*)
FROM pg_extension;


-- ----------------------------------------------------------------------------
-- QUERY 3: locale check - must match the values recorded in step 1
-- Safe to paste as-is.
-- ----------------------------------------------------------------------------

SELECT datname,
       pg_encoding_to_char(encoding) AS encoding,
       datcollate AS lc_collate,
       datctype   AS lc_ctype
FROM pg_database
WHERE datname = current_database();

SELECT name, setting
FROM pg_settings
WHERE name IN ('lc_monetary', 'lc_numeric', 'lc_time', 'server_encoding')
ORDER BY name;


-- ----------------------------------------------------------------------------
-- QUERY 4: incremental probe check (step 10, option B)
-- Replace <table> with the table chosen for the probe. Run it before and
-- after the insert on the source; the count must go up by one.
-- ----------------------------------------------------------------------------

SELECT count(*) AS filas FROM <table>;
