const path = require("path");
const fs = require("fs");
const { buildNativeRuntimePlan, flattenNativePlanSteps } = require("./native-runtime-plan");
const { loadRuntimePackageArtifacts } = require("./runtime-package-loader");
const { loadMigrationPackage } = require("../migration/package-loader");
const { assertDliClient } = require("./dli/dli-client-interface");
const { assertRealDliExecutionAllowed, runReadOnlyDliPreflight, createRealDliClient } = require("./dli/real-dli-client");
const { checkDliQueueHealth } = require("./dli/dli-queue-health");
const { createDliHttpTransport } = require("./dli/dli-http-transport");
const { generateRunId } = require("../core/run-id");
const { ensureDir, writeJson } = require("../core/json-file");
const { buildSafetyPolicy } = require("../core/safety-policy");
const { scrubSecrets } = require("../core/secret-scrubber");

const VALID_RESUME_FROM_VALUES = new Set([
  "runtime_setup",
  "target_transform",
  "runtime_validation",
]);

function buildNativeDliGuardedSafetyPolicy(options = {}) {
  const base = {
    native_dli_guarded_execution: true,
    explicit_native_confirm_required: true,
    understand_executes_sql_required: true,
    preflight_required: true,
    no_publish: true,
    no_delete: true,
    no_update: true,
    no_overwrite: true,
    no_schedule_start: true,
  };

  if (options.planOnly) {
    return buildSafetyPolicy({
      ...base,
      plan_only: true,
      no_sql_execution: true,
      no_runtime_execution: true,
    });
  }

  return buildSafetyPolicy({
    ...base,
    sql_execution_possible: true,
    guarded_real_execution: true,
  });
}

async function executeNativeDliGuarded(options = {}) {
  const errors = [];
  const warnings = [];

  const packageDir = options.packageDir;
  const dliQueue = options.dliQueue || "default";
  const mode = options.mode || "PLAN_ONLY";
  const planOnly = options.planOnly === true || mode === "PLAN_ONLY";
  const allowRealExecution = options.allowRealExecution === true;
  const confirmNativeDli = options.confirmNativeDli === true;
  const understandExecutesSql = options.understandExecutesSql === true;
  const dliClient = options.dliClient || null;
  const outDir = options.outDir || "./out";
  const resumeFrom = options.resumeFrom || "runtime_setup";
  const maxLaunchingJobs = options.maxLaunchingJobs !== undefined ? options.maxLaunchingJobs : 10;

  if (!VALID_RESUME_FROM_VALUES.has(resumeFrom)) {
    return {
      status: "INVALID_INPUT",
      valid: false,
      plan_only: planOnly,
      real_execution: false,
      migration_id: null,
      dli_queue: dliQueue,
      resume_from: resumeFrom,
      planned_sql_executions: 0,
      planned_query_executions: 0,
      total_planned_requests: 0,
      safety: buildNativeDliGuardedSafetyPolicy({ planOnly }),
      warnings,
      errors: [`Invalid --resume-from value: "${resumeFrom}". Allowed values: ${Array.from(VALID_RESUME_FROM_VALUES).join(", ")}`],
    };
  }

  if (!packageDir) {
    return {
      status: "NATIVE_DLI_GUARDED_EXECUTION_FAILED",
      valid: false,
      plan_only: planOnly,
      real_execution: false,
      migration_id: null,
      dli_queue: dliQueue,
      resume_from: resumeFrom,
      planned_sql_executions: 0,
      planned_query_executions: 0,
      total_planned_requests: 0,
      safety: buildNativeDliGuardedSafetyPolicy({ planOnly }),
      warnings,
      errors: ["packageDir is required"],
    };
  }

  const resolvedPackageDir = path.resolve(packageDir);

  const pkg = loadMigrationPackage(resolvedPackageDir);
  if (!pkg.valid) {
    return {
      status: "NATIVE_DLI_GUARDED_EXECUTION_FAILED",
      valid: false,
      plan_only: planOnly,
      real_execution: false,
      migration_id: pkg.migration_id,
      dli_queue: dliQueue,
      resume_from: resumeFrom,
      planned_sql_executions: 0,
      planned_query_executions: 0,
      total_planned_requests: 0,
      safety: buildNativeDliGuardedSafetyPolicy({ planOnly }),
      warnings: pkg.warnings,
      errors: pkg.errors,
    };
  }

  const migrationId = pkg.migration_id;

  const runtimeArtifacts = loadRuntimePackageArtifacts({
    packageDir: resolvedPackageDir,
    migrationId,
  });

  if (!runtimeArtifacts.valid) {
    return {
      status: "NATIVE_DLI_GUARDED_EXECUTION_FAILED",
      valid: false,
      plan_only: planOnly,
      real_execution: false,
      migration_id: migrationId,
      dli_queue: dliQueue,
      resume_from: resumeFrom,
      planned_sql_executions: 0,
      planned_query_executions: 0,
      total_planned_requests: 0,
      safety: buildNativeDliGuardedSafetyPolicy({ planOnly }),
      warnings: runtimeArtifacts.warnings,
      errors: runtimeArtifacts.errors,
    };
  }

  const planOpts = { packageDir: resolvedPackageDir, dliQueue, outDir };
  const nativePlan = buildNativeRuntimePlan(planOpts);

  if (!nativePlan.valid) {
    return {
      status: "NATIVE_DLI_GUARDED_EXECUTION_FAILED",
      valid: false,
      plan_only: planOnly,
      real_execution: false,
      migration_id: migrationId,
      dli_queue: dliQueue,
      resume_from: resumeFrom,
      planned_sql_executions: 0,
      planned_query_executions: 0,
      total_planned_requests: 0,
      safety: buildNativeDliGuardedSafetyPolicy({ planOnly }),
      warnings: nativePlan.warnings,
      errors: nativePlan.errors,
    };
  }

  const skipSetup = resumeFrom === "target_transform" || resumeFrom === "runtime_validation";
  const skipTarget = resumeFrom === "runtime_validation";

  const setupCount = nativePlan.phases.runtime_setup.length;
  const targetCount = nativePlan.phases.target_transform.length;
  const validationCount = nativePlan.phases.runtime_validation.length;

  const effectiveSetupCount = skipSetup ? 0 : setupCount;
  const effectiveTargetCount = skipTarget ? 0 : targetCount;
  const plannedSqlExecutions = effectiveSetupCount + effectiveTargetCount;
  const plannedQueryExecutions = validationCount;
  const totalPlannedRequests = plannedSqlExecutions + plannedQueryExecutions;

  if (planOnly) {
    const safety = buildNativeDliGuardedSafetyPolicy({ planOnly: true });

    const resumePlan = buildResumePlan({ resumeFrom, nativePlan });

    const result = {
      status: "NATIVE_DLI_GUARDED_PLAN_READY",
      valid: true,
      plan_only: true,
      real_execution: false,
      migration_id: migrationId,
      dli_queue: dliQueue,
      resume_from: resumeFrom,
      resume_plan: resumePlan,
      planned_sql_executions: plannedSqlExecutions,
      planned_query_executions: plannedQueryExecutions,
      total_planned_requests: totalPlannedRequests,
      safety,
      warnings,
      errors,
    };

    const runId = generateRunId();
    const resolvedOutDir = path.resolve(outDir);
    ensureDir(resolvedOutDir);

    const resultJsonPath = path.join(resolvedOutDir, "native_dli_guarded_execution_result.json");
    const reportMdPath = path.join(resolvedOutDir, "native_dli_guarded_execution_report.md");
    const runDir = path.join(resolvedOutDir, "runs", runId);
    ensureDir(runDir);
    const runResultJsonPath = path.join(runDir, "native_dli_guarded_execution_result.json");
    const runReportMdPath = path.join(runDir, "native_dli_guarded_execution_report.md");
    const currentRunJsonPath = path.join(runDir, "current_run.json");

    const report = renderGuardedExecutionMarkdown(result);

    writeJson(resultJsonPath, result);
    fs.writeFileSync(reportMdPath, report, "utf-8");
    writeJson(runResultJsonPath, result);
    fs.writeFileSync(runReportMdPath, report, "utf-8");
    writeJson(currentRunJsonPath, {
      run_id: runId,
      migration_id: migrationId,
      status: result.status,
      plan_only: true,
      real_execution: false,
      resume_from: resumeFrom,
      started_at: new Date().toISOString(),
      completed_at: new Date().toISOString(),
    });

    return {
      ...result,
      run_id: runId,
      evidence_paths: {
        result_json: resultJsonPath,
        report_md: reportMdPath,
        run_result_json: runResultJsonPath,
        run_report_md: runReportMdPath,
        current_run_json: currentRunJsonPath,
      },
    };
  }

  const guardCheck = assertRealDliExecutionAllowed({
    allowRealExecution,
    confirmNativeDli,
    understandExecutesSql,
  });

  if (!guardCheck.allowed) {
    return {
      status: "NATIVE_DLI_GUARDED_EXECUTION_BLOCKED",
      valid: false,
      plan_only: false,
      real_execution: false,
      migration_id: migrationId,
      dli_queue: dliQueue,
      resume_from: resumeFrom,
      planned_sql_executions: plannedSqlExecutions,
      planned_query_executions: plannedQueryExecutions,
      total_planned_requests: totalPlannedRequests,
      safety: buildNativeDliGuardedSafetyPolicy({ planOnly: false }),
      warnings,
      errors: [...errors, ...guardCheck.errors],
    };
  }

  const preflightResult = await runReadOnlyDliPreflight({
    queueName: dliQueue,
    client: dliClient && dliClient.listQueues ? dliClient : undefined,
  });

  if (!preflightResult.healthy) {
    return {
      status: "NATIVE_DLI_GUARDED_PREFLIGHT_UNHEALTHY",
      valid: false,
      plan_only: false,
      real_execution: false,
      migration_id: migrationId,
      dli_queue: dliQueue,
      resume_from: resumeFrom,
      planned_sql_executions: plannedSqlExecutions,
      planned_query_executions: plannedQueryExecutions,
      total_planned_requests: totalPlannedRequests,
      preflight: preflightResult,
      safety: buildNativeDliGuardedSafetyPolicy({ planOnly: false }),
      warnings,
      errors: [...errors, "DLI live preflight is unhealthy. SQL execution blocked."],
    };
  }

  const queueHealthResult = await checkDliQueueHealth({
    queueName: dliQueue,
    readOnly: true,
    maxLaunchingJobs,
    client: dliClient || undefined,
  });

  if (queueHealthResult.congested) {
    return {
      status: "NATIVE_DLI_QUEUE_CONGESTED",
      valid: false,
      plan_only: false,
      real_execution: false,
      migration_id: migrationId,
      dli_queue: dliQueue,
      resume_from: resumeFrom,
      planned_sql_executions: plannedSqlExecutions,
      planned_query_executions: plannedQueryExecutions,
      total_planned_requests: totalPlannedRequests,
      queue_health: queueHealthResult,
      safety: buildNativeDliGuardedSafetyPolicy({ planOnly: false }),
      warnings,
      errors: [...errors, `DLI queue is congested: ${queueHealthResult.jobs_by_state ? queueHealthResult.jobs_by_state.LAUNCHING : "?"} jobs in LAUNCHING state (threshold: ${maxLaunchingJobs}). SQL execution blocked.`],
    };
  }

  const safety = buildNativeDliGuardedSafetyPolicy({ planOnly: false });

  const targetDatabase = options.database || "demo_migration";

  const realDliClient = dliClient || createRealDliClient({
    allowRealExecution,
    confirmNativeDli,
    understandExecutesSql,
    httpClient: options.httpClient || null,
    database: targetDatabase,
  });

  const executionResult = await executeGuardedRuntime({
    nativePlan,
    dliClient: realDliClient,
    dliQueue,
    migrationId,
    targetDatabase,
    resumeFrom,
  });

  const result = {
    status: executionResult.status,
    valid: executionResult.valid,
    plan_only: false,
    real_execution: executionResult.real_execution,
    migration_id: migrationId,
    dli_queue: dliQueue,
    resume_from: resumeFrom,
    planned_sql_executions: plannedSqlExecutions,
    planned_query_executions: plannedQueryExecutions,
    total_planned_requests: totalPlannedRequests,
    preflight: {
      healthy: preflightResult.healthy,
      queue_accessible: preflightResult.queue_accessible,
    },
    queue_health: {
      healthy: queueHealthResult.healthy,
      congested: queueHealthResult.congested || false,
    },
    final_equivalence: executionResult.final_equivalence || null,
    equivalence_confirmed: executionResult.equivalence_confirmed || false,
    real_runtime_confirmed: executionResult.real_runtime_confirmed || false,
    execution_summary: executionResult.execution_summary || null,
    resume_summary: executionResult.resume_summary || null,
    safety,
    warnings,
    errors: [...errors, ...(executionResult.errors || [])],
  };

  const runId = generateRunId();
  const resolvedOutDir = path.resolve(outDir);
  ensureDir(resolvedOutDir);

  const resultJsonPath = path.join(resolvedOutDir, "native_dli_guarded_execution_result.json");
  const reportMdPath = path.join(resolvedOutDir, "native_dli_guarded_execution_report.md");
  const runDirPath = path.join(resolvedOutDir, "runs", runId);
  ensureDir(runDirPath);
  const runResultJsonPath = path.join(runDirPath, "native_dli_guarded_execution_result.json");
  const runReportMdPath = path.join(runDirPath, "native_dli_guarded_execution_report.md");
  const currentRunJsonPath = path.join(runDirPath, "current_run.json");

  const report = renderGuardedExecutionMarkdown(result);

  writeJson(resultJsonPath, result);
  fs.writeFileSync(reportMdPath, report, "utf-8");
  writeJson(runResultJsonPath, result);
  fs.writeFileSync(runReportMdPath, report, "utf-8");
  writeJson(currentRunJsonPath, {
    run_id: runId,
    migration_id: migrationId,
    status: result.status,
    plan_only: false,
    real_execution: false,
    resume_from: resumeFrom,
    started_at: new Date().toISOString(),
    completed_at: new Date().toISOString(),
  });

  return {
    ...result,
    run_id: runId,
    evidence_paths: {
      result_json: resultJsonPath,
      report_md: reportMdPath,
      run_result_json: runResultJsonPath,
      run_report_md: runReportMdPath,
      current_run_json: currentRunJsonPath,
    },
  };
}

function buildResumePlan({ resumeFrom, nativePlan }) {
  const skipSetup = resumeFrom === "target_transform" || resumeFrom === "runtime_validation";
  const skipTarget = resumeFrom === "runtime_validation";

  const setupSteps = (nativePlan.phases.runtime_setup || []).map((step) => ({
    ...step,
    status: skipSetup ? "SKIPPED_RESUME" : "PLANNED",
    executed: skipSetup ? false : false,
    skipped_reason: skipSetup ? "resume_from" : null,
  }));

  const targetSteps = (nativePlan.phases.target_transform || []).map((step) => ({
    ...step,
    status: skipTarget ? "SKIPPED_RESUME" : "PLANNED",
    executed: skipTarget ? false : false,
    skipped_reason: skipTarget ? "resume_from" : null,
  }));

  const validationSteps = (nativePlan.phases.runtime_validation || []).map((step) => ({
    ...step,
    status: "PLANNED",
    executed: false,
    skipped_reason: null,
  }));

  return {
    resume_from: resumeFrom,
    phases: {
      runtime_setup: setupSteps,
      target_transform: targetSteps,
      runtime_validation: validationSteps,
    },
  };
}

function resolveStepSql(step) {
  if (step.sql && typeof step.sql === "string") return step.sql;
  if (step.file_path && fs.existsSync(step.file_path)) return fs.readFileSync(step.file_path, "utf-8");
  if (step.sql_path && fs.existsSync(step.sql_path)) return fs.readFileSync(step.sql_path, "utf-8");
  return null;
}

function resolveStepCurrentdb(step, targetDatabase) {
  const sql = (step.sql || "").toUpperCase().trim();
  if (sql.startsWith("CREATE DATABASE") || sql.startsWith("DROP DATABASE")) return null;
  const fileSql = resolveStepSql(step);
  if (fileSql) {
    const upper = fileSql.toUpperCase().trim();
    if (upper.startsWith("CREATE DATABASE") || upper.startsWith("DROP DATABASE")) return null;
  }
  return targetDatabase || null;
}

async function executeGuardedRuntime({ nativePlan, dliClient, dliQueue, migrationId, targetDatabase, resumeFrom }) {
  const errors = [];
  const executionSummary = {
    setup_steps: 0,
    setup_succeeded: 0,
    setup_failed: 0,
    setup_skipped: 0,
    target_steps: 0,
    target_succeeded: 0,
    target_failed: 0,
    target_skipped: 0,
    validation_steps: 0,
    validation_succeeded: 0,
    validation_failed: 0,
    validation_results: [],
  };

  const resumeSummary = {
    resume_from: resumeFrom || "runtime_setup",
    setup_skipped: false,
    target_skipped: false,
    skipped_steps: [],
  };

  const setupSteps = nativePlan.phases.runtime_setup || [];
  const targetSteps = nativePlan.phases.target_transform || [];
  const validationSteps = nativePlan.phases.runtime_validation || [];

  executionSummary.setup_steps = setupSteps.length;
  executionSummary.target_steps = targetSteps.length;
  executionSummary.validation_steps = validationSteps.length;

  const skipSetup = resumeFrom === "target_transform" || resumeFrom === "runtime_validation";
  const skipTarget = resumeFrom === "runtime_validation";

  if (skipSetup) {
    resumeSummary.setup_skipped = true;
    for (const step of setupSteps) {
      resumeSummary.skipped_steps.push({
        phase: "runtime_setup",
        name: step.name,
        status: "SKIPPED_RESUME",
        executed: false,
        skipped_reason: "resume_from",
      });
    }
    executionSummary.setup_skipped = setupSteps.length;
  } else {
    for (const step of setupSteps) {
      try {
        const sql = resolveStepSql(step);
        if (!sql) {
          executionSummary.setup_failed++;
          errors.push(`Setup step ${step.name || "unknown"} failed: could not read SQL from file`);
          continue;
        }
        const currentdb = resolveStepCurrentdb(step, targetDatabase);
        const result = await dliClient.executeSql({
          sql,
          queueName: dliQueue,
          step,
          currentdb,
        });

        if (result.status === "NATIVE_DLI_TRANSPORT_NOT_CONFIGURED" ||
            result.status === "NATIVE_DLI_TRANSPORT_NOT_IMPLEMENTED") {
          return {
            status: result.status,
            valid: false,
            real_execution: false,
            final_equivalence: null,
            equivalence_confirmed: false,
            real_runtime_confirmed: false,
            execution_summary: executionSummary,
            resume_summary: resumeSummary,
            errors: [result.message || "DLI transport cannot execute."],
          };
        }

        if (result.status === "SUBMITTED" || result.status === "SUBMITTED_TIMEOUT_ACCEPTED" || result.status === "FINISHED") {
          executionSummary.setup_succeeded++;
        } else {
          executionSummary.setup_failed++;
          const detail = result.message ? `: ${result.message}` : "";
          const httpInfo = result.http_status ? ` (HTTP ${result.http_status})` : "";
          const bodySnippet = result.response_body_snippet ? ` | body: ${result.response_body_snippet}` : "";
          errors.push(`Setup step ${step.name || "unknown"} failed: ${result.status}${httpInfo}${detail}${bodySnippet}`);
        }
      } catch (err) {
        executionSummary.setup_failed++;
        errors.push(`Setup step ${step.name || "unknown"} error: ${scrubSecrets(err.message)}`);
      }
    }
  }

  if (executionSummary.setup_failed > 0) {
    return {
      status: "NATIVE_DLI_GUARDED_SETUP_FAILED",
      valid: false,
      real_execution: true,
      final_equivalence: "NOT_EQUIVALENT",
      equivalence_confirmed: false,
      real_runtime_confirmed: false,
      execution_summary: executionSummary,
      resume_summary: resumeSummary,
      errors,
    };
  }

  if (skipTarget) {
    resumeSummary.target_skipped = true;
    for (const step of targetSteps) {
      resumeSummary.skipped_steps.push({
        phase: "target_transform",
        name: step.name,
        status: "SKIPPED_RESUME",
        executed: false,
        skipped_reason: "resume_from",
      });
    }
    executionSummary.target_skipped = targetSteps.length;
  } else {
    for (const step of targetSteps) {
      try {
        const sql = resolveStepSql(step);
        if (!sql) {
          executionSummary.target_failed++;
          errors.push(`Target step ${step.name || "unknown"} failed: could not read SQL from file`);
          continue;
        }
        const currentdb = resolveStepCurrentdb(step, targetDatabase);
        const result = await dliClient.executeSql({
          sql,
          queueName: dliQueue,
          step,
          currentdb,
        });

        if (result.status === "NATIVE_DLI_TRANSPORT_NOT_CONFIGURED" ||
            result.status === "NATIVE_DLI_TRANSPORT_NOT_IMPLEMENTED") {
          return {
            status: result.status,
            valid: false,
            real_execution: false,
            final_equivalence: null,
            equivalence_confirmed: false,
            real_runtime_confirmed: false,
            execution_summary: executionSummary,
            resume_summary: resumeSummary,
            errors: [result.message || "DLI transport cannot execute."],
          };
        }

        if (result.status === "SUBMITTED" || result.status === "SUBMITTED_TIMEOUT_ACCEPTED" || result.status === "FINISHED") {
          executionSummary.target_succeeded++;
        } else {
          executionSummary.target_failed++;
          const detail = result.message ? `: ${result.message}` : "";
          const httpInfo = result.http_status ? ` (HTTP ${result.http_status})` : "";
          const bodySnippet = result.response_body_snippet ? ` | body: ${result.response_body_snippet}` : "";
          errors.push(`Target step ${step.name || "unknown"} failed: ${result.status}${httpInfo}${detail}${bodySnippet}`);
        }
      } catch (err) {
        executionSummary.target_failed++;
        errors.push(`Target step ${step.name || "unknown"} error: ${scrubSecrets(err.message)}`);
      }
    }
  }

  if (executionSummary.target_failed > 0) {
    return {
      status: "NATIVE_DLI_GUARDED_TARGET_FAILED",
      valid: false,
      real_execution: true,
      final_equivalence: "NOT_EQUIVALENT",
      equivalence_confirmed: false,
      real_runtime_confirmed: false,
      execution_summary: executionSummary,
      resume_summary: resumeSummary,
      errors,
    };
  }

  for (const step of validationSteps) {
    try {
      const result = await dliClient.querySql({
        sql: step.sql,
        queueName: dliQueue,
        step,
        currentdb: targetDatabase || null,
      });

      if (result.status === "NATIVE_DLI_TRANSPORT_NOT_CONFIGURED" ||
          result.status === "NATIVE_DLI_TRANSPORT_NOT_IMPLEMENTED") {
        return {
          status: result.status,
          valid: false,
          real_execution: false,
          final_equivalence: null,
          equivalence_confirmed: false,
          real_runtime_confirmed: false,
          execution_summary: executionSummary,
          resume_summary: resumeSummary,
          errors: [result.message || "DLI transport cannot execute."],
        };
      }

      const rows = result.rows || [];
      const queryType = step.query_type || step.type;
      const expectedValue = step.expected;
      let actualValue;
      if (queryType === "AGGREGATE_CHECK" && rows.length > 0 && typeof expectedValue === "object") {
        actualValue = rows[0];
      } else {
        actualValue = rows.length > 0 ? rows[0].actual_value : undefined;
      }
      const passed = compareValidationResult(actualValue, expectedValue, queryType);

      executionSummary.validation_results.push({
        id: step.name || step.id || "unknown",
        type: step.type,
        passed,
        actual: actualValue,
        expected: expectedValue,
      });

      if (passed) {
        executionSummary.validation_succeeded++;
      } else {
        executionSummary.validation_failed++;
        errors.push(`Validation ${step.name || "unknown"} failed: actual=${JSON.stringify(actualValue)} expected=${JSON.stringify(expectedValue)}`);
      }
    } catch (err) {
      executionSummary.validation_failed++;
      errors.push(`Validation ${step.name || "unknown"} error: ${scrubSecrets(err.message)}`);
    }
  }

  const allValidationsPassed = executionSummary.validation_failed === 0 && executionSummary.validation_succeeded > 0;

  return {
    status: allValidationsPassed ? "NATIVE_DLI_GUARDED_EXECUTION_SUCCEEDED" : "NATIVE_DLI_GUARDED_VALIDATION_FAILED",
    valid: allValidationsPassed,
    real_execution: true,
    final_equivalence: allValidationsPassed ? "EQUIVALENT" : "NOT_EQUIVALENT",
    equivalence_confirmed: allValidationsPassed,
    real_runtime_confirmed: allValidationsPassed,
    execution_summary: executionSummary,
    resume_summary: resumeSummary,
    errors,
  };
}

function compareValidationResult(actual, expected, type) {
  if (actual === undefined || actual === null) return false;
  if (expected === undefined || expected === null) return false;

  if (typeof expected === "string" && expected.startsWith(">=")) {
    const minVal = parseInt(expected.slice(2), 10);
    return parseInt(actual, 10) >= minVal;
  }

  if (typeof expected === "object") {
    if (typeof actual !== "object") return false;
    for (const key of Object.keys(expected)) {
      if (String(actual[key]) !== String(expected[key])) return false;
    }
    return true;
  }

  return String(actual) === String(expected);
}

function renderGuardedExecutionMarkdown(result) {
  const lines = [];

  lines.push("# Native DLI Guarded Execution Report");
  lines.push("");

  if (result.plan_only) {
    lines.push("> **PLAN-ONLY MODE** — No SQL was executed. No runtime execution occurred.");
  } else if (result.status === "NATIVE_DLI_REAL_EXECUTION_NOT_IMPLEMENTED") {
    lines.push("> **GUARDED REAL MODE** — Real execution is guarded but not yet implemented. No SQL was executed.");
  } else if (result.status === "NATIVE_DLI_GUARDED_EXECUTION_BLOCKED") {
    lines.push("> **BLOCKED** — Execution blocked by guardrail flags. No SQL was executed.");
  } else if (result.status === "NATIVE_DLI_GUARDED_PREFLIGHT_UNHEALTHY") {
    lines.push("> **BLOCKED** — DLI preflight is unhealthy. No SQL was executed.");
  } else if (result.status === "NATIVE_DLI_QUEUE_CONGESTED") {
    lines.push("> **BLOCKED** — DLI queue is congested. No SQL was executed.");
  } else if (result.status === "NATIVE_DLI_GUARDED_EXECUTION_SUCCEEDED") {
    lines.push("> **SUCCEEDED** — Real DLI execution completed. All validations passed.");
  } else if (result.status === "NATIVE_DLI_GUARDED_VALIDATION_FAILED") {
    lines.push("> **VALIDATION FAILED** — Real DLI execution completed but validation checks failed.");
  } else if (result.status === "NATIVE_DLI_GUARDED_SETUP_FAILED") {
    lines.push("> **SETUP FAILED** — Setup SQL execution failed. No target or validation SQL was executed.");
  } else if (result.status === "NATIVE_DLI_GUARDED_TARGET_FAILED") {
    lines.push("> **TARGET FAILED** — Target SQL execution failed. No validation SQL was executed.");
  } else if (result.status === "NATIVE_DLI_TRANSPORT_NOT_CONFIGURED") {
    lines.push("> **NOT CONFIGURED** — DLI transport is not configured for real execution.");
  } else if (result.status === "NATIVE_DLI_TRANSPORT_NOT_IMPLEMENTED") {
    lines.push("> **NOT IMPLEMENTED** — DLI transport real execution is not fully implemented.");
  } else {
    lines.push("> **FAILED** — Execution failed. No SQL was executed.");
  }

  lines.push("");
  lines.push("## Executive Summary");
  lines.push("");
  lines.push(`**Status:** ${result.status}`);
  lines.push(`**Valid:** ${result.valid ? "YES" : "NO"}`);
  lines.push(`**Plan Only:** ${result.plan_only ? "YES" : "NO"}`);
  lines.push(`**Real Execution:** ${result.real_execution ? "YES" : "NO"}`);
  lines.push(`**Migration ID:** ${result.migration_id || "N/A"}`);
  lines.push(`**DLI Queue:** ${result.dli_queue || "N/A"}`);
  if (result.resume_from) {
    lines.push(`**Resume From:** ${result.resume_from}`);
  }
  lines.push(`**SQL Executions Planned:** ${result.planned_sql_executions}`);
  lines.push(`**Query Executions Planned:** ${result.planned_query_executions}`);
  lines.push(`**Total DLI Requests Planned:** ${result.total_planned_requests}`);
  if (result.final_equivalence) {
    lines.push(`**Final Equivalence:** ${result.final_equivalence}`);
  }
  if (result.real_runtime_confirmed !== undefined) {
    lines.push(`**Real Runtime Confirmed:** ${result.real_runtime_confirmed ? "YES" : "NO"}`);
  }
  if (result.equivalence_confirmed !== undefined) {
    lines.push(`**Equivalence Confirmed:** ${result.equivalence_confirmed ? "YES" : "NO"}`);
  }
  lines.push("");

  if (result.resume_plan) {
    lines.push("## Resume Plan");
    lines.push("");
    lines.push(`**Resume From:** ${result.resume_plan.resume_from}`);
    lines.push("");

    for (const [phaseName, steps] of Object.entries(result.resume_plan.phases)) {
      lines.push(`### ${phaseName}`);
      lines.push("");
      lines.push("| Step | Status | Skipped Reason |");
      lines.push("|------|--------|----------------|");
      for (const step of steps) {
        lines.push(`| ${step.name || "unknown"} | ${step.status} | ${step.skipped_reason || "-"} |`);
      }
      lines.push("");
    }
  }

  if (result.safety) {
    lines.push("## Safety Policy");
    lines.push("");
    lines.push("| Flag | Value |");
    lines.push("|------|-------|");
    for (const [key, value] of Object.entries(result.safety)) {
      lines.push(`| ${key} | ${value} |`);
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

  lines.push("## Guardrail Requirements");
  lines.push("");
  lines.push("Real DLI execution requires ALL of the following flags:");
  lines.push("- `--allow-real-execution`");
  lines.push("- `--confirm-native-dli`");
  lines.push("- `--i-understand-this-executes-sql`");
  lines.push("");
  lines.push("Plan-only mode is safe and recommended before any real run.");
  lines.push("`migration:execute --confirm --adapter native-dli` remains unsupported.");
  lines.push("");

  return lines.join("\n");
}

module.exports = {
  executeNativeDliGuarded,
  buildNativeDliGuardedSafetyPolicy,
  buildResumePlan,
  VALID_RESUME_FROM_VALUES,
  renderGuardedExecutionMarkdown,
};
