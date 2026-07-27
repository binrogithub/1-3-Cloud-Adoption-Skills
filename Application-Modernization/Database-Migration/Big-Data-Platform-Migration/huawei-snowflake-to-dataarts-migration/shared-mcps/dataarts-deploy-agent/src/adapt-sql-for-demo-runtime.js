const fs = require('fs');
const path = require('path');

const SOURCE_DIR = path.resolve(__dirname, '../../snowflake_to_dataarts_demo_output');
const TARGET_DIR = path.resolve(__dirname, '../../snowflake_to_dataarts_demo_v3_runtime_output');
const OUT_DIR = path.resolve(__dirname, '../out');
const JOB_NAME_V2 = 'snowflake_to_dataarts_demo';
const JOB_NAME_V3 = 'snowflake_to_dataarts_demo_v3';

const REPLACEMENT_NAMES = [
  JOB_NAME_V2,
  'snowflake_to_dataarts_demo_v2',
];

const NEW_SQL_01 = `DROP TABLE IF EXISTS demo_migration.silver_orders;

CREATE TABLE demo_migration.silver_orders AS
SELECT
  order_id,
  customer_id,
  order_date,
  order_amount,
  CURRENT_TIMESTAMP() AS processed_at
FROM demo_migration.raw_orders
WHERE order_amount > 0;
`;

function replaceJobNames(content) {
  let result = content;
  for (const oldName of REPLACEMENT_NAMES) {
    result = result.split(oldName).join(JOB_NAME_V3);
  }
  return result;
}

function copyAndAdaptDir(srcRel, destRel, files, modifiedFiles, copiedFiles) {
  const srcAbs = path.join(SOURCE_DIR, srcRel);
  const destAbs = path.join(TARGET_DIR, destRel);
  fs.mkdirSync(destAbs, { recursive: true });

  for (const file of files) {
    const srcFile = path.join(srcAbs, file);
    const destFile = path.join(destAbs, file);
    let content = fs.readFileSync(srcFile, 'utf-8');
    const adapted = replaceJobNames(content);
    if (adapted !== content) {
      modifiedFiles.push(path.join(destRel, file));
    } else {
      copiedFiles.push(path.join(destRel, file));
    }
    fs.writeFileSync(destFile, adapted, 'utf-8');
  }
}

function main() {
  const timestamp = new Date().toISOString();
  const modifiedFiles = [];
  const copiedFiles = [];

  fs.mkdirSync(TARGET_DIR, { recursive: true });
  fs.mkdirSync(OUT_DIR, { recursive: true });

  // snowflake/
  copyAndAdaptDir('snowflake', 'snowflake', ['source_tasks.sql', 'task_inventory.csv'], modifiedFiles, copiedFiles);

  // analysis/
  copyAndAdaptDir('analysis', 'analysis', ['canonical_dag.json'], modifiedFiles, copiedFiles);

  // analysis/compatibility_report.md - adapt + append section
  {
    const srcFile = path.join(SOURCE_DIR, 'analysis/compatibility_report.md');
    const destFile = path.join(TARGET_DIR, 'analysis/compatibility_report.md');
    let content = fs.readFileSync(srcFile, 'utf-8');
    content = replaceJobNames(content);
    content += `

---

## Runtime Demo Adaptation

This section documents the adaptation applied for v3 runtime-safe demo execution.

- **Original Snowflake task used MERGE** for incremental upsert of RAW_ORDERS into SILVER_ORDERS.
- **MERGE is preserved in v2** as a faithful conversion artifact, matching the original Snowflake logic.
- **v3 replaces MERGE with full-refresh CTAS** (DROP TABLE IF EXISTS + CREATE TABLE AS SELECT) for DLI demo runtime. This avoids the need for Delta table format or MERGE-compatible DLI tables.
- **This is acceptable for demo** because the dataset is small and static (5 rows in raw_orders). Full refresh produces identical results to MERGE for a fresh dataset.
- **This is not production incremental logic.** In production, MERGE or INSERT OVERWRITE with partition predicates should be used for incremental processing.
`;
    modifiedFiles.push('analysis/compatibility_report.md');
    fs.writeFileSync(destFile, content, 'utf-8');
  }

  // dataarts/dataarts_pipeline.yaml
  copyAndAdaptDir('dataarts', 'dataarts', ['dataarts_pipeline.yaml'], modifiedFiles, copiedFiles);

  // dataarts/nodes/ directory
  fs.mkdirSync(path.join(TARGET_DIR, 'dataarts/nodes'), { recursive: true });

  // dataarts/nodes/01_load_silver_orders.sql - replace with CTAS
  {
    const destFile = path.join(TARGET_DIR, 'dataarts/nodes/01_load_silver_orders.sql');
    fs.writeFileSync(destFile, NEW_SQL_01, 'utf-8');
    modifiedFiles.push('dataarts/nodes/01_load_silver_orders.sql');
  }

  // dataarts/nodes/02_build_gold_daily_sales.sql - unchanged
  {
    const srcFile = path.join(SOURCE_DIR, 'dataarts/nodes/02_build_gold_daily_sales.sql');
    const destFile = path.join(TARGET_DIR, 'dataarts/nodes/02_build_gold_daily_sales.sql');
    const content = fs.readFileSync(srcFile, 'utf-8');
    fs.writeFileSync(destFile, content, 'utf-8');
    copiedFiles.push('dataarts/nodes/02_build_gold_daily_sales.sql');
  }

  // dataarts/nodes/03_audit_pipeline.sql - adapt job name
  {
    const srcFile = path.join(SOURCE_DIR, 'dataarts/nodes/03_audit_pipeline.sql');
    const destFile = path.join(TARGET_DIR, 'dataarts/nodes/03_audit_pipeline.sql');
    let content = fs.readFileSync(srcFile, 'utf-8');
    content = replaceJobNames(content);
    const original = fs.readFileSync(srcFile, 'utf-8');
    if (content !== original) {
      modifiedFiles.push('dataarts/nodes/03_audit_pipeline.sql');
    } else {
      copiedFiles.push('dataarts/nodes/03_audit_pipeline.sql');
    }
    fs.writeFileSync(destFile, content, 'utf-8');
  }

  // diagrams/
  copyAndAdaptDir('diagrams', 'diagrams', ['snowflake_task_graph.mmd', 'dataarts_pipeline_graph.mmd'], modifiedFiles, copiedFiles);

  // README.md - adapt + append v3 info
  {
    const srcFile = path.join(SOURCE_DIR, 'README.md');
    const destFile = path.join(TARGET_DIR, 'README.md');
    let content = fs.readFileSync(srcFile, 'utf-8');
    content = replaceJobNames(content);
    content += `

---

## v3 Runtime-Safe Demo Adaptation

- **v3 is runtime-safe for DLI demo execution.** The MERGE-based silver load has been replaced with a full-refresh CTAS (DROP + CREATE TABLE AS SELECT) that works on any DLI table format without requiring Delta tables.
- **v2 remains the faithful conversion job.** The v2 artifacts preserve the original MERGE logic as a direct Snowflake-to-DLI conversion.
- **v3 is intended for execution and equivalence validation.** Run the v3 pipeline in DLI to verify that the output matches the Snowflake source, then compare with v2 artifacts for conversion fidelity review.
`;
    modifiedFiles.push('README.md');
    fs.writeFileSync(destFile, content, 'utf-8');
  }

  // Generate report
  const report = `# Adapt SQL for Demo Runtime Report

**Timestamp:** ${timestamp}

## Summary

| Item | Value |
|------|-------|
| Source artifact folder | \`${path.relative(path.dirname(TARGET_DIR), SOURCE_DIR)}\` |
| Target artifact folder | \`${path.basename(TARGET_DIR)}\` |
| Job name v3 | \`${JOB_NAME_V3}\` |

## Files Copied (unchanged)

${copiedFiles.map(f => `- \`${f}\``).join('\n')}

## Files Modified

${modifiedFiles.map(f => `- \`${f}\``).join('\n')}

## SQL Adaptation Summary

| File | Original | Adapted | Reason |
|------|----------|---------|--------|
| \`dataarts/nodes/01_load_silver_orders.sql\` | MERGE INTO (upsert) | DROP TABLE IF EXISTS + CREATE TABLE AS SELECT (full refresh) | DLI demo runtime: avoids Delta table requirement for MERGE |
| \`dataarts/nodes/02_build_gold_daily_sales.sql\` | CTAS (DROP + CREATE) | Unchanged | Already DLI-compatible |
| \`dataarts/nodes/03_audit_pipeline.sql\` | INSERT with pipeline name | INSERT with v3 pipeline name | Job name updated to v3 |

## Safety Statement

- **No Huawei Cloud API was called.**
- **No DataArts job was modified.**
- **No DataArts job was published.**
- **No DataArts job was started.**
- **No DLI SQL was executed.**

This step only generated local runtime-safe artifacts for review.

## Required .env.dataarts Changes

The user must manually update \`.env.dataarts\` with:

\`\`\`
DATAARTS_JOB_NAME=${JOB_NAME_V3}
DATAARTS_ARTIFACTS_DIR=../snowflake_to_dataarts_demo_v3_runtime_output
\`\`\`
`;

  const reportPath = path.join(OUT_DIR, 'adapt_sql_for_demo_runtime_report.md');
  fs.writeFileSync(reportPath, report, 'utf-8');

  // Generate result JSON
  const result = {
    status: 'success',
    source_artifacts_dir: path.relative(path.dirname(SOURCE_DIR), SOURCE_DIR),
    target_artifacts_dir: path.relative(path.dirname(TARGET_DIR), TARGET_DIR),
    job_name: JOB_NAME_V3,
    modified_files: modifiedFiles,
    copied_files: copiedFiles,
    safety: {
      no_huawei_cloud_api_called: true,
      no_dataarts_job_modified: true,
      no_dataarts_job_published: true,
      no_dataarts_job_started: true,
      no_dli_sql_executed: true,
    },
    timestamp,
  };

  const resultPath = path.join(OUT_DIR, 'adapt_sql_for_demo_runtime_result.json');
  fs.writeFileSync(resultPath, JSON.stringify(result, null, 2), 'utf-8');

  console.log('=== Adapt SQL for Demo Runtime ===');
  console.log();
  console.log(`Source: ${SOURCE_DIR}`);
  console.log(`Target: ${TARGET_DIR}`);
  console.log(`Job name: ${JOB_NAME_V3}`);
  console.log();
  console.log('Modified files:');
  for (const f of modifiedFiles) console.log(`  [MOD] ${f}`);
  console.log();
  console.log('Copied files:');
  for (const f of copiedFiles) console.log(`  [CPY] ${f}`);
  console.log();
  console.log('SQL adaptation:');
  console.log('  01_load_silver_orders.sql: MERGE → CTAS (full refresh)');
  console.log('  02_build_gold_daily_sales.sql: unchanged');
  console.log('  03_audit_pipeline.sql: job name updated to v3');
  console.log();
  console.log('Reports:');
  console.log(`  ${reportPath}`);
  console.log(`  ${resultPath}`);
  console.log();
  console.log('=== Safety ===');
  console.log('No Huawei Cloud API was called.');
  console.log('No DataArts job was modified.');
  console.log('No DataArts job was published.');
  console.log('No DataArts job was started.');
  console.log('No DLI SQL was executed.');
  console.log();
  console.log('=== Required .env.dataarts changes ===');
  console.log(`DATAARTS_JOB_NAME=${JOB_NAME_V3}`);
  console.log('DATAARTS_ARTIFACTS_DIR=../snowflake_to_dataarts_demo_v3_runtime_output');
}

main();
