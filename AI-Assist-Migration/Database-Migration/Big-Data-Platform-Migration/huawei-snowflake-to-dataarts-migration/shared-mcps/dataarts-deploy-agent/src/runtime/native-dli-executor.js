const path = require("path");
const fs = require("fs");
const { buildNativeRuntimePlan, flattenNativePlanSteps } = require("./native-runtime-plan");
const { loadRuntimePackageArtifacts } = require("./runtime-package-loader");
const { loadMigrationPackage } = require("../migration/package-loader");
const { assertDliClient } = require("./dli/dli-client-interface");
const { generateRunId } = require("../core/run-id");
const { ensureDir, writeJson } = require("../core/json-file");
const { buildSafetyPolicy } = require("../core/safety-policy");

function buildMockExecutionSafetyPolicy() {
  return buildSafetyPolicy({
    native_dli_mock_execution_only: true,
    no_cloud_api_calls: true,
    no_real_sql_execution: true,
    no_runtime_execution: true,
    no_confirm: true,
    no_commands_executed: true,
    mock_client_required: true,
  });
}

function compareValidationResults(options = {}) {
  const { validationResults, validationQueries } = options;
  const comparisons = [];

  for (const query of validationQueries) {
    if (query.type === "FINAL_EQUIVALENCE") continue;

    const result = validationResults.find((r) => r.query_id === query.id);

    if (!result) {
      comparisons.push({
        query_id: query.id,
        object_name: query.object_name,
        query_type: query.type,
        expected: query.expected,
        actual: null,
        match: false,
        error: "No result found for query",
      });
      continue;
    }

    if (query.type === "TABLE_COUNT" || query.type === "TASK_AUDIT_SUCCESS") {
      const expectedVal = query.expected;
      const actualVal = result.rows && result.rows[0] ? result.rows[0].actual_value : null;
      let match = false;
      if (typeof expectedVal === "string" && expectedVal.startsWith(">=")) {
        const minVal = parseInt(expectedVal.slice(2), 10);
        match = typeof actualVal === "number" && actualVal >= minVal;
      } else {
        match = actualVal === expectedVal;
      }
      comparisons.push({
        query_id: query.id,
        object_name: query.object_name,
        query_type: query.type,
        expected: expectedVal,
        actual: actualVal,
        match,
      });
      continue;
    }

    if (query.type === "AGGREGATE_CHECK") {
      const expectedObj = query.expected;
      const actualObj = result.rows && result.rows[0] ? result.rows[0] : {};
      let match = true;
      for (const key of Object.keys(expectedObj)) {
        if (actualObj[key] !== expectedObj[key]) {
          match = false;
          break;
        }
      }
      comparisons.push({
        query_id: query.id,
        object_name: query.object_name,
        query_type: query.type,
        expected: expectedObj,
        actual: actualObj,
        match,
      });
      continue;
    }

    comparisons.push({
      query_id: query.id,
      object_name: query.object_name,
      query_type: query.type,
      expected: query.expected,
      actual: result.rows && result.rows[0] ? result.rows[0] : null,
      match: false,
      error: `Unsupported query type: ${query.type}`,
    });
  }

  return comparisons;
}

function buildNativeDliEquivalenceSummary(options = {}) {
  const { comparisonResults, migrationId } = options;
  const allMatch = comparisonResults.every((c) => c.match);
  const passCount = comparisonResults.filter((c) => c.match).length;
  const failCount = comparisonResults.filter((c) => !c.match).length;

  return {
    final_equivalence: allMatch ? "MOCK_EQUIVALENT" : "NOT_EQUIVALENT",
    equivalence_confirmed: false,
    mock_execution: true,
    real_runtime_confirmed: false,
    migration_id: migrationId || null,
    table_rows: comparisonResults.map((c) => ({
      object_name: c.object_name,
      query_id: c.query_id,
      query_type: c.query_type,
      expected: c.expected,
      actual: c.actual,
      match: c.match,
      mock_only: true,
    })),
    summary: {
      total_checks: comparisonResults.length,
      mock_pass: passCount,
      mock_fail: failCount,
      real_execution: false,
    },
  };
}

function executeNativeDliPlan(options = {}) {
  const errors = [];
  const warnings = [];

  const packageDir = options.packageDir;
  const dliQueue = options.dliQueue || "default";
  const mode = options.mode || "MOCK";
  const dliClient = options.dliClient;
  const outDir = options.outDir || "./out";

  if (!packageDir) {
    return {
      status: "NATIVE_DLI_MOCK_EXECUTION_FAILED",
      valid: false,
      mode,
      mock_execution: true,
      real_runtime_confirmed: false,
      run_id: null,
      migration_id: null,
      package_dir: null,
      dli_queue: dliQueue,
      setup_results: [],
      target_results: [],
      validation_results: [],
      comparison_results: [],
      final_equivalence: "NOT_EQUIVALENT",
      equivalence_confirmed: false,
      evidence_paths: null,
      safety: buildMockExecutionSafetyPolicy(),
      warnings,
      errors: ["packageDir is required"],
    };
  }

  if (mode !== "MOCK") {
    return {
      status: "NATIVE_DLI_MOCK_EXECUTION_FAILED",
      valid: false,
      mode,
      mock_execution: true,
      real_runtime_confirmed: false,
      run_id: null,
      migration_id: null,
      package_dir: path.resolve(packageDir),
      dli_queue: dliQueue,
      setup_results: [],
      target_results: [],
      validation_results: [],
      comparison_results: [],
      final_equivalence: "NOT_EQUIVALENT",
      equivalence_confirmed: false,
      evidence_paths: null,
      safety: buildMockExecutionSafetyPolicy(),
      warnings,
      errors: [`Unsupported mode: ${mode}. Only MOCK is supported for native DLI executor v0.1.`],
    };
  }

  try {
    assertDliClient(dliClient);
  } catch (err) {
    return {
      status: "NATIVE_DLI_MOCK_EXECUTION_FAILED",
      valid: false,
      mode,
      mock_execution: true,
      real_runtime_confirmed: false,
      run_id: null,
      migration_id: null,
      package_dir: path.resolve(packageDir),
      dli_queue: dliQueue,
      setup_results: [],
      target_results: [],
      validation_results: [],
      comparison_results: [],
      final_equivalence: "NOT_EQUIVALENT",
      equivalence_confirmed: false,
      evidence_paths: null,
      safety: buildMockExecutionSafetyPolicy(),
      warnings,
      errors: [err.message],
    };
  }

  const resolvedPackageDir = path.resolve(packageDir);

  const planOpts = { packageDir: resolvedPackageDir, dliQueue, outDir };
  const nativePlan = buildNativeRuntimePlan(planOpts);

  if (!nativePlan.valid) {
    return {
      status: "NATIVE_DLI_MOCK_EXECUTION_FAILED",
      valid: false,
      mode,
      mock_execution: true,
      real_runtime_confirmed: false,
      run_id: null,
      migration_id: nativePlan.migration_id,
      package_dir: nativePlan.package_dir,
      dli_queue: dliQueue,
      setup_results: [],
      target_results: [],
      validation_results: [],
      comparison_results: [],
      final_equivalence: "NOT_EQUIVALENT",
      equivalence_confirmed: false,
      evidence_paths: null,
      safety: buildMockExecutionSafetyPolicy(),
      warnings: nativePlan.warnings,
      errors: nativePlan.errors,
    };
  }

  const runId = generateRunId();
  const migrationId = nativePlan.migration_id;

  const pkg = loadMigrationPackage(resolvedPackageDir);
  const runtimeArtifacts = loadRuntimePackageArtifacts({
    packageDir: resolvedPackageDir,
    migrationId,
  });

  const validationQueries = runtimeArtifacts.valid
    ? (runtimeArtifacts.validation_queries.queries || [])
    : [];

  const setupResults = [];
  for (const step of nativePlan.phases.runtime_setup) {
    const sql = fs.readFileSync(step.file_path, "utf-8");
    const result = dliClient.executeSql({
      sql,
      queueName: dliQueue,
      step,
    });
    setupResults.push({
      execution_order: step.execution_order,
      phase: step.phase,
      name: step.name,
      file_path: step.file_path,
      job_id: result.job_id,
      status: result.status,
      mocked: result.mocked || false,
    });

    if (result.status === "FAILED") {
      errors.push(`Setup step ${step.name} failed: ${result.error || "unknown error"}`);
    }
  }

  const targetResults = [];
  for (const step of nativePlan.phases.target_transform) {
    const sqlPath = step.sql_path;
    let sql = "";
    if (sqlPath && fs.existsSync(sqlPath)) {
      sql = fs.readFileSync(sqlPath, "utf-8");
    }
    const result = dliClient.executeSql({
      sql,
      queueName: dliQueue,
      step,
    });
    targetResults.push({
      execution_order: step.execution_order,
      phase: step.phase,
      name: step.name,
      node_id: step.node_id,
      job_id: result.job_id,
      status: result.status,
      mocked: result.mocked || false,
    });

    if (result.status === "FAILED") {
      errors.push(`Target step ${step.name} failed: ${result.error || "unknown error"}`);
    }
  }

  const validationResults = [];
  for (const step of nativePlan.phases.runtime_validation) {
    const result = dliClient.querySql({
      sql: step.sql,
      queueName: dliQueue,
      step,
    });
    validationResults.push({
      execution_order: step.execution_order,
      phase: step.phase,
      name: step.name,
      query_id: step.name,
      query_type: step.query_type,
      object_name: step.object_name,
      job_id: result.job_id,
      status: result.status,
      rows: result.rows || [],
      column_names: result.column_names || [],
      mocked: result.mocked || false,
    });
  }

  const comparisonResults = compareValidationResults({
    validationResults,
    validationQueries,
  });

  const equivalenceSummary = buildNativeDliEquivalenceSummary({
    comparisonResults,
    migrationId,
  });

  const hasErrors = errors.length > 0 || !equivalenceSummary.table_rows.every((r) => r.match);
  const finalEquivalence = hasErrors ? "NOT_EQUIVALENT" : equivalenceSummary.final_equivalence;
  const valid = !hasErrors;

  const resolvedOutDir = path.resolve(outDir);
  ensureDir(resolvedOutDir);

  const resultJsonPath = path.join(resolvedOutDir, "native_dli_mock_execution_result.json");
  const reportMdPath = path.join(resolvedOutDir, "native_dli_mock_execution_report.md");
  const runDir = path.join(resolvedOutDir, "runs", runId);
  ensureDir(runDir);
  const runResultJsonPath = path.join(runDir, "native_dli_mock_execution_result.json");
  const runReportMdPath = path.join(runDir, "native_dli_mock_execution_report.md");
  const currentRunJsonPath = path.join(runDir, "current_run.json");

  const result = {
    status: valid
      ? "NATIVE_DLI_MOCK_EXECUTION_COMPLETE"
      : "NATIVE_DLI_MOCK_EXECUTION_FAILED",
    valid,
    mode,
    mock_execution: true,
    real_runtime_confirmed: false,
    run_id: runId,
    migration_id: migrationId,
    package_dir: resolvedPackageDir,
    dli_queue: dliQueue,
    setup_results: setupResults,
    target_results: targetResults,
    validation_results: validationResults,
    comparison_results: comparisonResults,
    final_equivalence: finalEquivalence,
    equivalence_confirmed: false,
    safety: buildMockExecutionSafetyPolicy(),
    warnings,
    errors,
  };

  const report = renderMockExecutionMarkdown(result, equivalenceSummary);

  writeJson(resultJsonPath, result);
  fs.writeFileSync(reportMdPath, report, "utf-8");
  writeJson(runResultJsonPath, result);
  fs.writeFileSync(runReportMdPath, report, "utf-8");
  writeJson(currentRunJsonPath, {
    run_id: runId,
    migration_id: migrationId,
    status: result.status,
    mock_execution: true,
    started_at: new Date().toISOString(),
    completed_at: new Date().toISOString(),
  });

  const evidencePaths = {
    result_json: resultJsonPath,
    report_md: reportMdPath,
    run_result_json: runResultJsonPath,
    run_report_md: runReportMdPath,
    current_run_json: currentRunJsonPath,
  };

  return {
    ...result,
    evidence_paths: evidencePaths,
  };
}

function renderMockExecutionMarkdown(result, equivalenceSummary) {
  const lines = [];

  lines.push("# Native DLI Mock Execution Report");
  lines.push("");
  lines.push("> **MOCK EXECUTION ONLY** — No cloud APIs were called. No real SQL was executed. No runtime execution occurred.");
  lines.push("");
  lines.push("## Executive Summary");
  lines.push("");
  lines.push(`**Status:** ${result.status}`);
  lines.push(`**Valid:** ${result.valid ? "YES" : "NO"}`);
  lines.push(`**Mode:** ${result.mode}`);
  lines.push(`**Mock Execution:** YES`);
  lines.push(`**Run ID:** ${result.run_id || "N/A"}`);
  lines.push(`**Migration ID:** ${result.migration_id || "N/A"}`);
  lines.push(`**Package Dir:** \`${result.package_dir || "N/A"}\``);
  lines.push(`**DLI Queue:** ${result.dli_queue || "N/A"}`);
  lines.push(`**Final Equivalence:** ${result.final_equivalence}`);
  lines.push(`**Equivalence Confirmed:** ${result.equivalence_confirmed ? "YES" : "NO"}`);
  lines.push(`**Real Runtime Confirmed:** ${result.real_runtime_confirmed ? "YES" : "NO"}`);
  lines.push("");

  lines.push("## Step Summary");
  lines.push("");
  lines.push("| Metric | Count |");
  lines.push("|--------|-------|");
  lines.push(`| Setup steps | ${result.setup_results.length} |`);
  lines.push(`| Target steps | ${result.target_results.length} |`);
  lines.push(`| Validation steps | ${result.validation_results.length} |`);
  lines.push("");

  lines.push("## Setup Results");
  lines.push("");
  lines.push("| Order | Name | Job ID | Status | Mocked |");
  lines.push("|-------|------|--------|--------|--------|");
  for (const step of result.setup_results) {
    lines.push(`| ${step.execution_order} | ${step.name} | ${step.job_id || "N/A"} | ${step.status} | ${step.mocked ? "YES" : "NO"} |`);
  }
  lines.push("");

  lines.push("## Target Results");
  lines.push("");
  lines.push("| Order | Name | Job ID | Status | Mocked |");
  lines.push("|-------|------|--------|--------|--------|");
  for (const step of result.target_results) {
    lines.push(`| ${step.execution_order} | ${step.name} | ${step.job_id || "N/A"} | ${step.status} | ${step.mocked ? "YES" : "NO"} |`);
  }
  lines.push("");

  if (equivalenceSummary && equivalenceSummary.table_rows && equivalenceSummary.table_rows.length > 0) {
    lines.push("## Equivalence Summary");
    lines.push("");
    lines.push(`**Final Equivalence:** ${equivalenceSummary.final_equivalence}`);
    lines.push(`**Equivalence Confirmed:** ${equivalenceSummary.equivalence_confirmed ? "YES" : "NO"}`);
    lines.push(`**Mock Execution:** YES`);
    lines.push(`**Real Runtime Confirmed:** NO`);
    lines.push("");

    lines.push("| Object | Query ID | Query Type | Expected | Actual | Match |");
    lines.push("|--------|----------|------------|----------|--------|-------|");
    for (const row of equivalenceSummary.table_rows) {
      const expectedStr = typeof row.expected === "object" ? JSON.stringify(row.expected) : String(row.expected);
      const actualStr = typeof row.actual === "object" ? JSON.stringify(row.actual) : String(row.actual);
      lines.push(`| ${row.object_name} | ${row.query_id} | ${row.query_type} | ${expectedStr} | ${actualStr} | ${row.match ? "YES" : "NO"} |`);
    }
    lines.push("");
  }

  if (result.warnings && result.warnings.length > 0) {
    lines.push("## Warnings");
    lines.push("");
    for (const w of result.warnings) {
      lines.push(`- ${w}`);
    }
    lines.push("");
  }

  if (result.errors && result.errors.length > 0) {
    lines.push("## Errors");
    lines.push("");
    for (const e of result.errors) {
      lines.push(`- ${e}`);
    }
    lines.push("");
  }

  lines.push("## Safety");
  lines.push("");
  lines.push("- **Mock execution only** — no real execution");
  lines.push("- No cloud API calls");
  lines.push("- No real SQL execution");
  lines.push("- No runtime execution");
  lines.push("- No confirm");
  lines.push("- Mock client required");
  lines.push("- Equivalence is MOCK_EQUIVALENT, not EQUIVALENT");
  lines.push("- equivalence_confirmed is false");
  lines.push("- real_runtime_confirmed is false");
  lines.push("");

  return lines.join("\n");
}

module.exports = {
  executeNativeDliPlan,
  compareValidationResults,
  buildNativeDliEquivalenceSummary,
  buildMockExecutionSafetyPolicy,
  renderMockExecutionMarkdown,
};
