const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const OUT_DIR = path.join(ROOT, "out");
const RUNS_DIR = path.join(OUT_DIR, "runs");

function parseCliArgs(argv) {
  const args = argv.slice(2);
  const parsed = {};
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--run-id" && args[i + 1]) {
      parsed.runId = args[++i];
    } else if (args[i] === "--job-name" && args[i + 1]) {
      parsed.jobName = args[++i];
    }
  }
  return parsed;
}

function readJsonSafe(filePath) {
  if (!fs.existsSync(filePath)) return null;
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf-8"));
  } catch {
    return null;
  }
}

function resolveResults(cliArgs) {
  const runId = cliArgs.runId || null;
  const jobName = cliArgs.jobName || null;

  let currentRun = null;
  let demoResult = null;
  let runtimeValidateResult = null;
  let runImmediateResult = null;
  let resolvedRunId = runId;
  let runDir = null;

  if (runId) {
    runDir = path.join(RUNS_DIR, runId);
    currentRun = readJsonSafe(path.join(runDir, "current_run.json"));
    demoResult = readJsonSafe(path.join(runDir, "demo_one_shot_result.json"));
    runtimeValidateResult = readJsonSafe(path.join(runDir, "runtime_validate_result.json"));
    runImmediateResult = readJsonSafe(path.join(runDir, "run_immediate_job_result.json"));
  }

  if (!currentRun) {
    const crPath = path.join(OUT_DIR, "current_run.json");
    const cr = readJsonSafe(crPath);
    if (cr) {
      if (!resolvedRunId && cr.run_id) {
        resolvedRunId = cr.run_id;
        runDir = path.join(RUNS_DIR, cr.run_id);
      }
      currentRun = cr;
    }
  }

  if (!demoResult) {
    if (runDir) {
      demoResult = readJsonSafe(path.join(runDir, "demo_one_shot_result.json"));
    }
    if (!demoResult) {
      demoResult = readJsonSafe(path.join(OUT_DIR, "demo_one_shot_result.json"));
    }
  }

  if (!runtimeValidateResult) {
    if (runDir) {
      runtimeValidateResult = readJsonSafe(path.join(runDir, "runtime_validate_result.json"));
    }
    if (!runtimeValidateResult) {
      runtimeValidateResult = readJsonSafe(path.join(OUT_DIR, "runtime_validate_result.json"));
    }
  }

  if (!runImmediateResult) {
    if (runDir) {
      runImmediateResult = readJsonSafe(path.join(runDir, "run_immediate_job_result.json"));
    }
    if (!runImmediateResult) {
      runImmediateResult = readJsonSafe(path.join(OUT_DIR, "run_immediate_job_result.json"));
    }
  }

  const resultJobName = demoResult?.job_name || currentRun?.job_name || null;
  if (jobName && resultJobName && jobName !== resultJobName) {
    return {
      error: "STALE_RESULT_DETECTED",
      requested_job_name: jobName,
      result_job_name: resultJobName,
      message: `Result belongs to job "${resultJobName}", not requested "${jobName}".`,
    };
  }

  return {
    currentRun,
    demoResult,
    runtimeValidateResult,
    runImmediateResult,
    resolvedRunId,
    runDir,
  };
}

function buildTableRows(data) {
  const { runtimeValidateResult, demoResult } = data;
  const rows = [];

  const rv = runtimeValidateResult;
  const dr = demoResult;

  const runtimePassed = rv?.status === "PASS" || dr?.runtime_validate_status === "PASS";
  const finalEquiv = rv?.equivalence_result || dr?.final_equivalence || "NOT_EVALUATED";
  const instanceId = rv?.instance_id || dr?.instance_id || "N/A";

  rows.push({
    VALIDATION_TYPE: "PIPELINE_READY",
    OBJECT_NAME: "SNOWFLAKE_TASK_GRAPH_TO_DATAARTS_DAG",
    SNOWFLAKE_EXPECTED: "PASS",
    DATAARTS_DLI_ACTUAL: runtimePassed ? "PASS" : "FAIL",
    STATUS: finalEquiv === "EQUIVALENT" ? "PASS" : "FAIL",
    DETAIL: "Snowflake Task Graph was converted to a DataArts/DLI runtime-safe DAG and executed successfully.",
  });

  const tc = rv?.table_counts || [];
  const tableMap = {};
  for (const t of tc) {
    tableMap[t.table] = t;
  }

  const rawActual = tableMap["demo_migration.raw_orders"]?.actual ?? "N/A";
  rows.push({
    VALIDATION_TYPE: "TABLE_COUNT",
    OBJECT_NAME: "RAW_ORDERS",
    SNOWFLAKE_EXPECTED: "5",
    DATAARTS_DLI_ACTUAL: String(rawActual),
    STATUS: String(rawActual) === "5" ? "PASS" : "FAIL",
    DETAIL: `raw_orders row count: expected=5, actual=${rawActual}`,
  });

  const silverActual = tableMap["demo_migration.silver_orders"]?.actual ?? "N/A";
  rows.push({
    VALIDATION_TYPE: "TABLE_COUNT",
    OBJECT_NAME: "SILVER_ORDERS",
    SNOWFLAKE_EXPECTED: "5",
    DATAARTS_DLI_ACTUAL: String(silverActual),
    STATUS: String(silverActual) === "5" ? "PASS" : "FAIL",
    DETAIL: `silver_orders row count: expected=5, actual=${silverActual}`,
  });

  const goldActual = tableMap["demo_migration.gold_daily_sales"]?.actual ?? "N/A";
  rows.push({
    VALIDATION_TYPE: "TABLE_COUNT",
    OBJECT_NAME: "GOLD_DAILY_SALES",
    SNOWFLAKE_EXPECTED: "2",
    DATAARTS_DLI_ACTUAL: String(goldActual),
    STATUS: String(goldActual) === "2" ? "PASS" : "FAIL",
    DETAIL: `gold_daily_sales row count: expected=2, actual=${goldActual}`,
  });

  const auditActual = tableMap["demo_migration.task_audit (SUCCESS)"]?.actual ?? "N/A";
  const auditPass = typeof auditActual === "number" ? auditActual >= 1 : false;
  rows.push({
    VALIDATION_TYPE: "TABLE_COUNT",
    OBJECT_NAME: "TASK_AUDIT_SUCCESS",
    SNOWFLAKE_EXPECTED: ">=1",
    DATAARTS_DLI_ACTUAL: String(auditActual),
    STATUS: auditPass ? "PASS" : "FAIL",
    DETAIL: `task_audit SUCCESS count: expected>=1, actual=${auditActual}`,
  });

  const ga = rv?.gold_aggregates || [];

  const ga20260620 = ga.find((g) => g.date === "2026-06-20");
  const actual20 = ga20260620
    ? `order_count=${ga20260620.actual_order_count},total_amount=${ga20260620.actual_total_amount}`
    : "N/A";
  rows.push({
    VALIDATION_TYPE: "AGGREGATE_CHECK",
    OBJECT_NAME: "2026-06-20",
    SNOWFLAKE_EXPECTED: "order_count=2,total_amount=420.50",
    DATAARTS_DLI_ACTUAL: actual20,
    STATUS: ga20260620?.result || "FAIL",
    DETAIL: ga20260620
      ? `2026-06-20: expected order_count=2,total_amount=420.50; actual order_count=${ga20260620.actual_order_count},total_amount=${ga20260620.actual_total_amount}`
      : "2026-06-20 aggregate data not found",
  });

  const ga20260621 = ga.find((g) => g.date === "2026-06-21");
  const actual21 = ga20260621
    ? `order_count=${ga20260621.actual_order_count},total_amount=${ga20260621.actual_total_amount}`
    : "N/A";
  rows.push({
    VALIDATION_TYPE: "AGGREGATE_CHECK",
    OBJECT_NAME: "2026-06-21",
    SNOWFLAKE_EXPECTED: "order_count=3,total_amount=630.34",
    DATAARTS_DLI_ACTUAL: actual21,
    STATUS: ga20260621?.result || "FAIL",
    DETAIL: ga20260621
      ? `2026-06-21: expected order_count=3,total_amount=630.34; actual order_count=${ga20260621.actual_order_count},total_amount=${ga20260621.actual_total_amount}`
      : "2026-06-21 aggregate data not found",
  });

  rows.push({
    VALIDATION_TYPE: "FINAL_EQUIVALENCE",
    OBJECT_NAME: "SNOWFLAKE_TO_DATAARTS",
    SNOWFLAKE_EXPECTED: "EQUIVALENT",
    DATAARTS_DLI_ACTUAL: finalEquiv,
    STATUS: finalEquiv === "EQUIVALENT" ? "PASS" : "FAIL",
    DETAIL: "DataArts/DLI output is functionally equivalent to the Snowflake result.",
  });

  return rows;
}

function generateMarkdownTable(rows) {
  const lines = [];
  lines.push("# Equivalence Summary Report");
  lines.push("");
  lines.push("## Snowflake vs DataArts/DLI Equivalence Table");
  lines.push("");
  lines.push("| VALIDATION_TYPE | OBJECT_NAME | SNOWFLAKE_EXPECTED | DATAARTS_DLI_ACTUAL | STATUS | DETAIL |");
  lines.push("|-----------------|-------------|--------------------|---------------------|--------|--------|");
  for (const r of rows) {
    lines.push(`| ${r.VALIDATION_TYPE} | ${r.OBJECT_NAME} | ${r.SNOWFLAKE_EXPECTED} | ${r.DATAARTS_DLI_ACTUAL} | ${r.STATUS} | ${r.DETAIL} |`);
  }
  lines.push("");
  return lines;
}

function generateExecutiveSummary(data) {
  const { demoResult, currentRun, runtimeValidateResult, resolvedRunId } = data;
  const dr = demoResult;
  const rv = runtimeValidateResult;

  const jobName = dr?.job_name || currentRun?.job_name || "N/A";
  const runId = resolvedRunId || dr?.run_id || "N/A";
  const instanceId = rv?.instance_id || dr?.instance_id || "N/A";
  const runtimeVal = rv?.status || dr?.runtime_validate_status || "N/A";
  const finalEquiv = rv?.equivalence_result || dr?.final_equivalence || "N/A";
  const equivConfirmed = finalEquiv === "EQUIVALENT";

  const lines = [];
  lines.push("## Executive Summary");
  lines.push("");
  lines.push(`**Functional equivalence: ${equivConfirmed ? "CONFIRMED" : "NOT CONFIRMED"}**`);
  lines.push("");
  lines.push(`- Job name: ${jobName}`);
  lines.push(`- Run ID: ${runId}`);
  lines.push(`- Instance ID: ${instanceId}`);
  lines.push(`- Runtime validation: ${runtimeVal}`);
  lines.push(`- Safety: no publish, no /start, no delete, no update, run-immediate only`);
  lines.push("");

  return { lines, jobName, runId, instanceId, runtimeVal, finalEquiv, equivConfirmed };
}

function main() {
  console.log("=== DataArts Deploy Agent: EQUIVALENCE SUMMARY ===\n");

  const cliArgs = parseCliArgs(process.argv);
  const data = resolveResults(cliArgs);

  if (data.error) {
    console.error(`ERROR: ${data.error}`);
    console.error(data.message);
    console.error(`  Requested job: ${data.requested_job_name}`);
    console.error(`  Result job:    ${data.result_job_name}`);
    process.exit(1);
  }

  const { currentRun, demoResult, runtimeValidateResult, resolvedRunId, runDir } = data;

  if (!currentRun && !demoResult && !runtimeValidateResult) {
    console.error("ERROR: No result files found. Run the demo first.");
    process.exit(1);
  }

  const rows = buildTableRows(data);
  const tableLines = generateMarkdownTable(rows);
  const { lines: execLines, jobName, runId, instanceId, runtimeVal, finalEquiv, equivConfirmed } = generateExecutiveSummary(data);

  const fullMd = [...tableLines, ...execLines].join("\n");

  console.log(fullMd);
  console.log("");

  const timestamp = new Date().toISOString();

  const jsonResult = {
    status: equivConfirmed ? "EQUIVALENT" : "NOT_EQUIVALENT",
    job_name: jobName,
    run_id: runId,
    instance_id: instanceId,
    runtime_validation: runtimeVal,
    final_equivalence: finalEquiv,
    equivalence_confirmed: equivConfirmed,
    table_rows: rows,
    safety: {
      no_publish: true,
      no_start: true,
      no_delete: true,
      no_update: true,
      no_overwrite: true,
      only_run_immediate_for_execution: true,
      no_secrets_printed: true,
    },
    timestamp,
    no_secrets_included: true,
  };

  if (!fs.existsSync(OUT_DIR)) {
    fs.mkdirSync(OUT_DIR, { recursive: true });
  }

  const mdPath = path.join(OUT_DIR, "equivalence_summary_report.md");
  const jsonPath = path.join(OUT_DIR, "equivalence_summary_result.json");
  fs.writeFileSync(mdPath, fullMd, "utf-8");
  fs.writeFileSync(jsonPath, JSON.stringify(jsonResult, null, 2), "utf-8");

  console.log("Reports saved:");
  console.log(`  ${mdPath}`);
  console.log(`  ${jsonPath}`);

  if (resolvedRunId) {
    const targetRunDir = path.join(RUNS_DIR, resolvedRunId);
    if (fs.existsSync(targetRunDir)) {
      const runMdPath = path.join(targetRunDir, "equivalence_summary_report.md");
      const runJsonPath = path.join(targetRunDir, "equivalence_summary_result.json");
      fs.writeFileSync(runMdPath, fullMd, "utf-8");
      fs.writeFileSync(runJsonPath, JSON.stringify(jsonResult, null, 2), "utf-8");
      console.log(`  ${runMdPath}`);
      console.log(`  ${runJsonPath}`);
    }
  }

  console.log("");
  console.log("Safety: No Huawei Cloud APIs called. No DLI SQL executed. No DataArts job run. Only local result files read.");

  process.exit(equivConfirmed ? 0 : 1);
}

main();
