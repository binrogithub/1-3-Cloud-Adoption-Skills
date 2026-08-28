-- ============================================================================
-- 04 (psql) - Target validation
-- Run against the TARGET RDS database, after the full sync reaches 100%.
-- READ ONLY.
--
-- *** DO NOT PASTE THIS INTO THE DAS SQL EDITOR ***
-- DAS mangles the quoting in xpath() / query_to_xml() and the query fails
-- with: ERROR: syntax error at or near "("
-- For DAS, use 04_target_validation_das.sql instead.
--
-- WHERE TO RUN: psql, from a host inside the target VPC:
--   psql -h <rds_private_ip> -p 5432 -d <db_name> -U root \
--        -P pager=off -f 04_target_validation.sql
--
-- Compare this output line by line against the step 2 baseline.
-- ============================================================================

SELECT current_database() AS database_name,
       now()              AS validated_at;

-- Exact row count per table
SELECT table_schema,
       table_name,
       (xpath(
          '/row/cnt/text()',
          query_to_xml(
            format('SELECT count(*) AS cnt FROM %I.%I', table_schema, table_name),
            false, true, ''
          )
        ))[1]::text::bigint AS row_count
FROM information_schema.tables
WHERE table_type = 'BASE TABLE'
  AND table_schema NOT IN ('pg_catalog', 'information_schema')
ORDER BY table_schema, table_name;

-- Totals
SELECT count(*) AS total_tables,
       coalesce(sum(rc), 0) AS total_rows
FROM (
  SELECT (xpath(
            '/row/cnt/text()',
            query_to_xml(
              format('SELECT count(*) AS cnt FROM %I.%I', table_schema, table_name),
              false, true, ''
            )
          ))[1]::text::bigint AS rc
  FROM information_schema.tables
  WHERE table_type = 'BASE TABLE'
    AND table_schema NOT IN ('pg_catalog', 'information_schema')
) t;

-- Object counts
SELECT 'indexes' AS object_type, count(*) AS total
FROM pg_indexes
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
UNION ALL
SELECT 'constraints', count(*)
FROM pg_constraint c
JOIN pg_namespace n ON n.oid = c.connamespace
WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
UNION ALL
SELECT 'sequences', count(*)
FROM information_schema.sequences
WHERE sequence_schema NOT IN ('pg_catalog', 'information_schema')
UNION ALL
SELECT 'views', count(*)
FROM information_schema.views
WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
UNION ALL
SELECT 'extensions', count(*)
FROM pg_extension;

-- Locale check: must match the source values captured in step 1.
-- On PostgreSQL 16+, lc_collate and lc_ctype are database properties, not
-- server settings, so they come from pg_database rather than pg_settings.
SELECT name, setting
FROM pg_settings
WHERE name IN ('lc_monetary', 'lc_numeric', 'lc_time', 'server_encoding')
ORDER BY name;

SELECT datname,
       pg_encoding_to_char(encoding) AS encoding,
       datcollate AS lc_collate,
       datctype   AS lc_ctype
FROM pg_database
WHERE datname = current_database();
