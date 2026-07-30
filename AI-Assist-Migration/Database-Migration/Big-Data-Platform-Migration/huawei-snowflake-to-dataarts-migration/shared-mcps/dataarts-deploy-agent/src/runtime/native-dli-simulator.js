const path = require("path");
const { buildNativeRuntimePlan, flattenNativePlanSteps } = require("./native-runtime-plan");
const { loadRuntimePackageArtifacts } = require("./runtime-package-loader");
const { loadMigrationPackage } = require("../migration/package-loader");
const { generateRunId } = require("../core/run-id");
const { ensureDir, writeJson, readJsonSafe } = require("../core/json-file");
const { buildSafetyPolicy } = require("../core/safety-policy");

function buildSimulationSafetyPolicy() {
  return buildSafetyPolicy({
    native_dli_simulation_only: true,
    no_cloud_api_calls: true,
    no_runtime_execution: true,
    no_sql_execution: true,
    no_confirm: true,
    no_commands_executed: true,
    simulation_only: true,
  });
}

function simulateNativeStep(step, options = {}) {
  const simulated = {
    execution_order: step.execution_order,
    phase: step.phase,
    type: step.type,
    name: step.name,
    executed: false,
    simulated: true,
    status: "SIMULATED_PASS",
    simulated_at: new Date().toISOString(),
  };

  if (step.phase === "runtime_setup") {
    simulated.file_path = step.file_path;
    simulated.statement_count = step.statement_count;
    simulated.simulated_result = "SQL would be executed on DLI (simulated)";
  }

  if (step.phase === "target_transform") {
    simulated.node_id = step.node_id;
    simulated.sql_file = step.sql_file;
    simulated.depends_on = step.depends_on || [];
    simulated.simulated_result = "Transform SQL would be executed on DLI (simulated)";
  }

  if (step.phase === "runtime_validation") {
    simulated.query_type = step.query_type;
    simulated.object_name = step.object_name;
    simulated.expected = step.expected;
    simulated.simulated_actual = step.expected;
    simulated.simulated_result = "Validation query would return expected value (simulated)";
  }

  if (step.phase === "equivalence_summary") {
    simulated.simulated_result = "Equivalence comparison would be performed locally (simulated)";
  }

  return simulated;
}

function buildSimulatedEquivalenceSummary(options = {}) {
  const { validationQueries, migrationId } = options;
  const tableRows = [];

  if (validationQueries && validationQueries.length > 0) {
    for (const query of validationQueries) {
      if (query.type === "FINAL_EQUIVALENCE") continue;
      tableRows.push({
        object_name: query.object_name,
        query_id: query.id,
        query_type: query.type,
        expected: query.expected,
        simulated_actual: query.expected,
        simulated_match: true,
        simulated_only: true,
      });
    }
  }

  return {
    final_equivalence: "SIMULATED_EQUIVALENT",
    equivalence_confirmed: false,
    simulation_only: true,
    migration_id: migrationId || null,
    table_rows: tableRows,
    summary: {
      total_checks: tableRows.length,
      simulated_pass: tableRows.length,
      simulated_fail: 0,
      real_execution: false,
    },
  };
}

function simulateNativeDliExecution(options = {}) {
  const errors = [];
  const warnings = [];

  const packageDir = options.packageDir;
  const dliQueue = options.dliQueue || "default";
  const outDir = options.outDir || "./out";

  if (!packageDir) {
    return {
      status: "NATIVE_DLI_SIMULATION_FAILED",
      valid: false,
      simulation_only: true,
      run_id: null,
      migration_id: null,
      package_dir: null,
      dli_queue: dliQueue,
      steps_simulated: 0,
      setup_steps: 0,
      target_steps: 0,
      validation_steps: 0,
      final_equivalence: "SIMULATED_EQUIVALENT",
      equivalence_confirmed: false,
      simulated_step_results: [],
      simulated_equivalence_summary: null,
      evidence_paths: null,
      safety: buildSimulationSafetyPolicy(),
      warnings,
      errors: ["packageDir is required"],
    };
  }

  const resolvedPackageDir = path.resolve(packageDir);

  const planOpts = { packageDir: resolvedPackageDir, dliQueue, outDir };
  const nativePlan = buildNativeRuntimePlan(planOpts);

  if (!nativePlan.valid) {
    return {
      status: "NATIVE_DLI_SIMULATION_FAILED",
      valid: false,
      simulation_only: true,
      run_id: null,
      migration_id: nativePlan.migration_id,
      package_dir: nativePlan.package_dir,
      dli_queue: dliQueue,
      steps_simulated: 0,
      setup_steps: 0,
      target_steps: 0,
      validation_steps: 0,
      final_equivalence: "SIMULATED_EQUIVALENT",
      equivalence_confirmed: false,
      simulated_step_results: [],
      simulated_equivalence_summary: null,
      evidence_paths: null,
      safety: buildSimulationSafetyPolicy(),
      warnings: nativePlan.warnings,
      errors: nativePlan.errors,
    };
  }

  const runId = generateRunId();
  const migrationId = nativePlan.migration_id;

  const flatSteps = flattenNativePlanSteps(nativePlan);

  const simulatedStepResults = flatSteps.map((step) =>
    simulateNativeStep(step, { packageDir: resolvedPackageDir })
  );

  const setupSteps = nativePlan.phases.runtime_setup.length;
  const targetSteps = nativePlan.phases.target_transform.length;
  const validationSteps = nativePlan.phases.runtime_validation.length;
  const equivalenceSteps = nativePlan.phases.equivalence_summary.length;
  const stepsSimulated = setupSteps + targetSteps + validationSteps + equivalenceSteps;

  const pkg = loadMigrationPackage(resolvedPackageDir);
  const runtimeArtifacts = loadRuntimePackageArtifacts({
    packageDir: resolvedPackageDir,
    migrationId,
  });

  const validationQueries = runtimeArtifacts.valid
    ? (runtimeArtifacts.validation_queries.queries || [])
    : [];

  const simulatedEquivalenceSummary = buildSimulatedEquivalenceSummary({
    validationQueries,
    migrationId,
  });

  const resolvedOutDir = path.resolve(outDir);
  ensureDir(resolvedOutDir);

  const resultJsonPath = path.join(resolvedOutDir, "native_dli_simulation_result.json");
  const reportMdPath = path.join(resolvedOutDir, "native_dli_simulation_report.md");
  const runDir = path.join(resolvedOutDir, "runs", runId);
  ensureDir(runDir);
  const runResultJsonPath = path.join(runDir, "native_dli_simulation_result.json");
  const runReportMdPath = path.join(runDir, "native_dli_simulation_report.md");
  const currentRunJsonPath = path.join(runDir, "current_run.json");

  const result = {
    status: "NATIVE_DLI_SIMULATION_COMPLETE",
    valid: true,
    simulation_only: true,
    run_id: runId,
    migration_id: migrationId,
    package_dir: resolvedPackageDir,
    dli_queue: dliQueue,
    steps_simulated: stepsSimulated,
    setup_steps: setupSteps,
    target_steps: targetSteps,
    validation_steps: validationSteps,
    final_equivalence: "SIMULATED_EQUIVALENT",
    equivalence_confirmed: false,
    simulated_step_results: simulatedStepResults,
    simulated_equivalence_summary: simulatedEquivalenceSummary,
    safety: buildSimulationSafetyPolicy(),
    warnings,
    errors: [],
  };

  const report = renderSimulationMarkdown(result);

  writeJson(resultJsonPath, result);
  require("fs").writeFileSync(reportMdPath, report, "utf-8");
  writeJson(runResultJsonPath, result);
  require("fs").writeFileSync(runReportMdPath, report, "utf-8");
  writeJson(currentRunJsonPath, {
    run_id: runId,
    migration_id: migrationId,
    status: "NATIVE_DLI_SIMULATION_COMPLETE",
    simulation_only: true,
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

function renderSimulationMarkdown(result) {
  const lines = [];

  lines.push("# Native DLI Simulation Report");
  lines.push("");
  lines.push("> **SIMULATION ONLY** — No cloud APIs were called. No SQL was executed. No runtime execution occurred.");
  lines.push("");
  lines.push("## Executive Summary");
  lines.push("");
  lines.push(`**Status:** ${result.status}`);
  lines.push(`**Valid:** ${result.valid ? "YES" : "NO"}`);
  lines.push(`**Simulation Only:** YES`);
  lines.push(`**Run ID:** ${result.run_id || "N/A"}`);
  lines.push(`**Migration ID:** ${result.migration_id || "N/A"}`);
  lines.push(`**Package Dir:** \`${result.package_dir || "N/A"}\``);
  lines.push(`**DLI Queue:** ${result.dli_queue || "N/A"}`);
  lines.push(`**Final Equivalence:** ${result.final_equivalence}`);
  lines.push(`**Equivalence Confirmed:** ${result.equivalence_confirmed ? "YES" : "NO"}`);
  lines.push("");

  lines.push("## Step Summary");
  lines.push("");
  lines.push("| Metric | Count |");
  lines.push("|--------|-------|");
  lines.push(`| Setup steps | ${result.setup_steps} |`);
  lines.push(`| Target steps | ${result.target_steps} |`);
  lines.push(`| Validation steps | ${result.validation_steps} |`);
  lines.push(`| Total steps simulated | ${result.steps_simulated} |`);
  lines.push("");

  lines.push("## Simulated Step Results");
  lines.push("");
  lines.push("| Order | Phase | Type | Name | Executed | Simulated | Status |");
  lines.push("|-------|-------|------|------|----------|-----------|--------|");
  for (const step of result.simulated_step_results) {
    lines.push(
      `| ${step.execution_order} | ${step.phase} | ${step.type} | ${step.name} | ${step.executed ? "YES" : "NO"} | ${step.simulated ? "YES" : "NO"} | ${step.status} |`
    );
  }
  lines.push("");

  if (result.simulated_equivalence_summary) {
    const eq = result.simulated_equivalence_summary;
    lines.push("## Simulated Equivalence Summary");
    lines.push("");
    lines.push(`**Final Equivalence:** ${eq.final_equivalence}`);
    lines.push(`**Equivalence Confirmed:** ${eq.equivalence_confirmed ? "YES" : "NO"}`);
    lines.push(`**Simulation Only:** YES`);
    lines.push("");

    if (eq.table_rows && eq.table_rows.length > 0) {
      lines.push("| Object | Query ID | Query Type | Expected | Simulated Actual | Match |");
      lines.push("|--------|----------|------------|----------|-----------------|-------|");
      for (const row of eq.table_rows) {
        const expectedStr = typeof row.expected === "object" ? JSON.stringify(row.expected) : String(row.expected);
        const actualStr = typeof row.simulated_actual === "object" ? JSON.stringify(row.simulated_actual) : String(row.simulated_actual);
        lines.push(`| ${row.object_name} | ${row.query_id} | ${row.query_type} | ${expectedStr} | ${actualStr} | ${row.simulated_match ? "YES" : "NO"} |`);
      }
      lines.push("");
    }
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
  lines.push("- **Simulation only** — no real execution");
  lines.push("- No cloud API calls");
  lines.push("- No SQL execution");
  lines.push("- No runtime execution");
  lines.push("- No confirm");
  lines.push("- No commands executed");
  lines.push("- Equivalence is SIMULATED_EQUIVALENT, not EQUIVALENT");
  lines.push("- equivalence_confirmed is false");
  lines.push("");

  return lines.join("\n");
}

module.exports = {
  simulateNativeDliExecution,
  simulateNativeStep,
  buildSimulatedEquivalenceSummary,
  buildSimulationSafetyPolicy,
  renderSimulationMarkdown,
};
