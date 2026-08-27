-- ============================================================================
-- 03 - Source baseline
--
-- WHERE TO RUN: inside the source ECS, over SSH. READ ONLY.
--
--   scp 03_source_baseline.sql root@<source_eip>:/tmp/
--   ssh root@<source_eip>
--   sudo -u postgres psql -P pager=off -d <source_db> \
--        -f /tmp/03_source_baseline.sql
--
-- NOTE FOR THE ASSISTANT: record the TABLE NAMES from this output, not just
-- the counts. You need them in step 9 to build a DAS-compatible validation
-- query, and in step 10 to choose a table for the incremental probe.
--
-- SAVE THIS OUTPUT. It is the reference the target is validated against in
-- step 9. Without it, the migration cannot be proven: a target with perfect
-- structure and zero rows looks identical to a successful migration when
-- only objects are compared.
-- ============================================================================

\echo '=== Baseline captured at ==='
SELECT current_database() AS database_name,
       now()              AS captured_at;

\echo '=== Exact row count per table ==='
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

\echo '=== Totals ==='
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

\echo '=== Object counts ==='
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
