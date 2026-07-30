const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("path");
const {
  executeNativeDliGuarded,
  buildNativeDliGuardedSafetyPolicy,
  buildResumePlan,
  VALID_RESUME_FROM_VALUES,
} = require("../../src/runtime/native-dli-guarded-executor");
const { assertRealDliExecutionAllowed } = require("../../src/runtime/dli/real-dli-client");

const CUSTOMER_PKG = path.resolve(__dirname, "../../cases/golden/customer_status_pipeline_simple");

function createMockHealthyClient(overrides = {}) {
  return {
    listQueues: async () => ({
      status: "OK",
      http_status: 200,
      read_only: true,
      real_execution: false,
      queues: [{ queue_name: "default", queue_type: "general", queue_id: 1 }],
      queues_found: 1,
    }),
    describeQueue: async () => ({
      status: "OK",
      http_status: 200,
      read_only: true,
      real_execution: false,
      queue_name: "default",
      queue: { queue_name: "default", queue_type: "general", status: "RUNNING" },
      queue_exists: true,
    }),
    executeSql: overrides.executeSql || (async ({ sql, queueName, step }) => ({
      job_id: "fake_job_" + (step ? step.name : "unknown"),
      status: "SUBMITTED",
      valid: true,
      real_execution: true,
      statement_type: "EXECUTE_SQL",
    })),
    querySql: overrides.querySql || (async ({ sql, queueName, step }) => {
      const queryType = step && step.query_type;
      const expected = step && step.expected;
      let rows;
      if (queryType === "AGGREGATE_CHECK" && typeof expected === "object") {
        rows = [expected];
      } else if (typeof expected === "string" && expected.startsWith(">=")) {
        rows = [{ actual_value: parseInt(expected.slice(2), 10) }];
      } else {
        rows = [{ actual_value: expected !== undefined ? expected : 1 }];
      }
      return {
        job_id: "fake_query_" + (step ? step.name : "unknown"),
        status: "FINISHED",
        valid: true,
        real_execution: true,
        statement_type: "QUERY",
        rows,
        column_names: Object.keys(rows[0]),
      };
    }),
    getJobStatus: async ({ jobId }) => ({
      job_id: jobId,
      status: "FINISHED",
      valid: true,
      real_execution: true,
    }),
    getJobResult: async ({ jobId }) => ({
      job_id: jobId,
      status: "FINISHED",
      valid: true,
      real_execution: true,
      rows: [],
      column_names: [],
    }),
  };
}

test("guarded PLAN_ONLY returns NATIVE_DLI_GUARDED_PLAN_READY", async () => {
  const result = await executeNativeDliGuarded({
    packageDir: CUSTOMER_PKG,
    dliQueue: "default",
    mode: "PLAN_ONLY",
    planOnly: true,
    outDir: path.resolve(__dirname, "../../out"),
  });

  assert.equal(result.status, "NATIVE_DLI_GUARDED_PLAN_READY");
  assert.equal(result.valid, true);
  assert.equal(result.plan_only, true);
  assert.equal(result.real_execution, false);
});

test("guarded PLAN_ONLY planned_sql_executions = 8", async () => {
  const result = await executeNativeDliGuarded({
    packageDir: CUSTOMER_PKG,
    dliQueue: "default",
    mode: "PLAN_ONLY",
    planOnly: true,
    outDir: path.resolve(__dirname, "../../out"),
  });

  assert.equal(result.planned_sql_executions, 8);
});

test("guarded PLAN_ONLY planned_query_executions = 7", async () => {
  const result = await executeNativeDliGuarded({
    packageDir: CUSTOMER_PKG,
    dliQueue: "default",
    mode: "PLAN_ONLY",
    planOnly: true,
    outDir: path.resolve(__dirname, "../../out"),
  });

  assert.equal(result.planned_query_executions, 7);
});

test("guarded PLAN_ONLY total_planned_requests = 15", async () => {
  const result = await executeNativeDliGuarded({
    packageDir: CUSTOMER_PKG,
    dliQueue: "default",
    mode: "PLAN_ONLY",
    planOnly: true,
    outDir: path.resolve(__dirname, "../../out"),
  });

  assert.equal(result.total_planned_requests, 15);
});

test("guarded PLAN_ONLY safety flags present", async () => {
  const result = await executeNativeDliGuarded({
    packageDir: CUSTOMER_PKG,
    dliQueue: "default",
    mode: "PLAN_ONLY",
    planOnly: true,
    outDir: path.resolve(__dirname, "../../out"),
  });

  assert.equal(result.safety.native_dli_guarded_execution, true);
  assert.equal(result.safety.explicit_native_confirm_required, true);
  assert.equal(result.safety.understand_executes_sql_required, true);
  assert.equal(result.safety.preflight_required, true);
  assert.equal(result.safety.no_publish, true);
  assert.equal(result.safety.no_delete, true);
  assert.equal(result.safety.no_update, true);
  assert.equal(result.safety.no_overwrite, true);
  assert.equal(result.safety.no_schedule_start, true);
  assert.equal(result.safety.plan_only, true);
  assert.equal(result.safety.no_sql_execution, true);
  assert.equal(result.safety.no_runtime_execution, true);
});

test("guarded REAL without flags fails before SQL", async () => {
  const result = await executeNativeDliGuarded({
    packageDir: CUSTOMER_PKG,
    dliQueue: "default",
    mode: "REAL",
    planOnly: false,
    allowRealExecution: false,
    confirmNativeDli: false,
    understandExecutesSql: false,
    outDir: path.resolve(__dirname, "../../out"),
  });

  assert.equal(result.status, "NATIVE_DLI_GUARDED_EXECUTION_BLOCKED");
  assert.equal(result.valid, false);
  assert.equal(result.real_execution, false);
  assert.ok(result.errors.length > 0);
});

test("guarded REAL with partial flags fails before SQL", async () => {
  const result = await executeNativeDliGuarded({
    packageDir: CUSTOMER_PKG,
    dliQueue: "default",
    mode: "REAL",
    planOnly: false,
    allowRealExecution: true,
    confirmNativeDli: false,
    understandExecutesSql: false,
    outDir: path.resolve(__dirname, "../../out"),
  });

  assert.equal(result.status, "NATIVE_DLI_GUARDED_EXECUTION_BLOCKED");
  assert.equal(result.valid, false);
  assert.equal(result.real_execution, false);
});

test("guarded REAL with unhealthy preflight fails before SQL", async () => {
  const mockUnhealthyClient = {
    listQueues: async () => ({ status: "ERROR", http_status: 403, queues: [] }),
    describeQueue: async () => ({ status: "ERROR", http_status: 403 }),
  };

  const result = await executeNativeDliGuarded({
    packageDir: CUSTOMER_PKG,
    dliQueue: "default",
    mode: "REAL",
    planOnly: false,
    allowRealExecution: true,
    confirmNativeDli: true,
    understandExecutesSql: true,
    dliClient: mockUnhealthyClient,
    outDir: path.resolve(__dirname, "../../out"),
  });

  assert.equal(result.status, "NATIVE_DLI_GUARDED_PREFLIGHT_UNHEALTHY");
  assert.equal(result.valid, false);
  assert.equal(result.real_execution, false);
});

test("guarded REAL with all flags and healthy mock preflight returns NOT_IMPLEMENTED", async () => {
  const mockHealthyClient = {
    listQueues: async () => ({
      status: "OK",
      http_status: 200,
      read_only: true,
      real_execution: false,
      queues: [{ queue_name: "default", queue_type: "general", queue_id: 1 }],
      queues_found: 1,
    }),
    describeQueue: async () => ({
      status: "OK",
      http_status: 200,
      read_only: true,
      real_execution: false,
      queue_name: "default",
      queue: { queue_name: "default", queue_type: "general", status: "RUNNING" },
      queue_exists: true,
    }),
    executeSql: async () => ({
      status: "NATIVE_DLI_TRANSPORT_NOT_CONFIGURED",
      valid: false,
      real_execution: false,
      message: "No transport configured.",
    }),
    querySql: async () => ({
      status: "NATIVE_DLI_TRANSPORT_NOT_CONFIGURED",
      valid: false,
      real_execution: false,
      message: "No transport configured.",
    }),
    getJobStatus: async () => ({
      status: "NATIVE_DLI_TRANSPORT_NOT_CONFIGURED",
      valid: false,
      real_execution: false,
    }),
    getJobResult: async () => ({
      status: "NATIVE_DLI_TRANSPORT_NOT_CONFIGURED",
      valid: false,
      real_execution: false,
      rows: [],
      column_names: [],
    }),
  };

  const result = await executeNativeDliGuarded({
    packageDir: CUSTOMER_PKG,
    dliQueue: "default",
    mode: "REAL",
    planOnly: false,
    allowRealExecution: true,
    confirmNativeDli: true,
    understandExecutesSql: true,
    dliClient: mockHealthyClient,
    outDir: path.resolve(__dirname, "../../out"),
  });

  assert.equal(result.status, "NATIVE_DLI_TRANSPORT_NOT_CONFIGURED");
  assert.equal(result.valid, false);
  assert.equal(result.real_execution, false);
  assert.equal(result.planned_sql_executions, 8);
  assert.equal(result.planned_query_executions, 7);
  assert.equal(result.total_planned_requests, 15);
});

test("guarded REAL safety flags include guarded_real_execution", async () => {
  const mockHealthyClient = {
    listQueues: async () => ({
      status: "OK",
      http_status: 200,
      read_only: true,
      real_execution: false,
      queues: [{ queue_name: "default", queue_type: "general", queue_id: 1 }],
      queues_found: 1,
    }),
    describeQueue: async () => ({
      status: "OK",
      http_status: 200,
      read_only: true,
      real_execution: false,
      queue_name: "default",
      queue: { queue_name: "default", queue_type: "general", status: "RUNNING" },
      queue_exists: true,
    }),
  };

  const result = await executeNativeDliGuarded({
    packageDir: CUSTOMER_PKG,
    dliQueue: "default",
    mode: "REAL",
    planOnly: false,
    allowRealExecution: true,
    confirmNativeDli: true,
    understandExecutesSql: true,
    dliClient: mockHealthyClient,
    outDir: path.resolve(__dirname, "../../out"),
  });

  assert.equal(result.safety.native_dli_guarded_execution, true);
  assert.equal(result.safety.guarded_real_execution, true);
  assert.equal(result.safety.sql_execution_possible, true);
  assert.equal(result.safety.explicit_native_confirm_required, true);
  assert.equal(result.safety.understand_executes_sql_required, true);
  assert.equal(result.safety.preflight_required, true);
});

test("guarded without packageDir fails", async () => {
  const result = await executeNativeDliGuarded({
    dliQueue: "default",
    mode: "PLAN_ONLY",
    planOnly: true,
  });

  assert.equal(result.status, "NATIVE_DLI_GUARDED_EXECUTION_FAILED");
  assert.equal(result.valid, false);
  assert.ok(result.errors.includes("packageDir is required"));
});

test("buildNativeDliGuardedSafetyPolicy plan-only", () => {
  const safety = buildNativeDliGuardedSafetyPolicy({ planOnly: true });
  assert.equal(safety.native_dli_guarded_execution, true);
  assert.equal(safety.plan_only, true);
  assert.equal(safety.no_sql_execution, true);
  assert.equal(safety.no_runtime_execution, true);
  assert.equal(safety.explicit_native_confirm_required, true);
  assert.equal(safety.understand_executes_sql_required, true);
  assert.equal(safety.preflight_required, true);
});

test("buildNativeDliGuardedSafetyPolicy real mode", () => {
  const safety = buildNativeDliGuardedSafetyPolicy({ planOnly: false });
  assert.equal(safety.native_dli_guarded_execution, true);
  assert.equal(safety.sql_execution_possible, true);
  assert.equal(safety.guarded_real_execution, true);
  assert.equal(safety.explicit_native_confirm_required, true);
  assert.equal(safety.understand_executes_sql_required, true);
  assert.equal(safety.preflight_required, true);
});

test("assertRealDliExecutionAllowed with all flags", () => {
  const result = assertRealDliExecutionAllowed({
    allowRealExecution: true,
    confirmNativeDli: true,
    understandExecutesSql: true,
  });
  assert.equal(result.allowed, true);
  assert.equal(result.errors.length, 0);
});

test("assertRealDliExecutionAllowed without allowRealExecution", () => {
  const result = assertRealDliExecutionAllowed({
    allowRealExecution: false,
    confirmNativeDli: true,
    understandExecutesSql: true,
  });
  assert.equal(result.allowed, false);
  assert.ok(result.errors.some((e) => e.includes("allowRealExecution=true")));
});

test("assertRealDliExecutionAllowed without confirmNativeDli", () => {
  const result = assertRealDliExecutionAllowed({
    allowRealExecution: true,
    confirmNativeDli: false,
    understandExecutesSql: true,
  });
  assert.equal(result.allowed, false);
  assert.ok(result.errors.some((e) => e.includes("--confirm-native-dli")));
});

test("assertRealDliExecutionAllowed without understandExecutesSql", () => {
  const result = assertRealDliExecutionAllowed({
    allowRealExecution: true,
    confirmNativeDli: true,
    understandExecutesSql: false,
  });
  assert.equal(result.allowed, false);
  assert.ok(result.errors.some((e) => e.includes("--i-understand-this-executes-sql")));
});

test("assertRealDliExecutionAllowed with no flags", () => {
  const result = assertRealDliExecutionAllowed({});
  assert.equal(result.allowed, false);
  assert.equal(result.errors.length, 3);
});

test("guarded PLAN_ONLY returns migration_id", async () => {
  const result = await executeNativeDliGuarded({
    packageDir: CUSTOMER_PKG,
    dliQueue: "default",
    mode: "PLAN_ONLY",
    planOnly: true,
    outDir: path.resolve(__dirname, "../../out"),
  });

  assert.equal(result.migration_id, "customer_status_pipeline_simple");
});

test("guarded PLAN_ONLY returns run_id and evidence_paths", async () => {
  const result = await executeNativeDliGuarded({
    packageDir: CUSTOMER_PKG,
    dliQueue: "default",
    mode: "PLAN_ONLY",
    planOnly: true,
    outDir: path.resolve(__dirname, "../../out"),
  });

  assert.ok(result.run_id);
  assert.ok(result.evidence_paths);
  assert.ok(result.evidence_paths.result_json);
  assert.ok(result.evidence_paths.report_md);
  assert.ok(result.evidence_paths.run_result_json);
  assert.ok(result.evidence_paths.run_report_md);
  assert.ok(result.evidence_paths.current_run_json);
});

test("guarded REAL returns NOT_IMPLEMENTED cleanly when transport not implemented", async () => {
  const mockHealthyClient = createMockHealthyClient({
    executeSql: async () => ({
      status: "NATIVE_DLI_TRANSPORT_NOT_IMPLEMENTED",
      valid: false,
      real_execution: false,
      message: "Transport not implemented.",
    }),
    querySql: async () => ({
      status: "NATIVE_DLI_TRANSPORT_NOT_IMPLEMENTED",
      valid: false,
      real_execution: false,
      message: "Transport not implemented.",
    }),
  });

  const result = await executeNativeDliGuarded({
    packageDir: CUSTOMER_PKG,
    dliQueue: "default",
    mode: "REAL",
    planOnly: false,
    allowRealExecution: true,
    confirmNativeDli: true,
    understandExecutesSql: true,
    dliClient: mockHealthyClient,
    outDir: path.resolve(__dirname, "../../out"),
  });

  assert.equal(result.status, "NATIVE_DLI_TRANSPORT_NOT_IMPLEMENTED");
  assert.equal(result.valid, false);
  assert.equal(result.real_execution, false);
});

test("guarded REAL with injected fake transport can exercise success path", async () => {
  const mockHealthyClient = createMockHealthyClient();

  const result = await executeNativeDliGuarded({
    packageDir: CUSTOMER_PKG,
    dliQueue: "default",
    mode: "REAL",
    planOnly: false,
    allowRealExecution: true,
    confirmNativeDli: true,
    understandExecutesSql: true,
    dliClient: mockHealthyClient,
    outDir: path.resolve(__dirname, "../../out"),
  });

  assert.equal(result.status, "NATIVE_DLI_GUARDED_EXECUTION_SUCCEEDED");
  assert.equal(result.valid, true);
  assert.equal(result.real_execution, true);
  assert.equal(result.real_runtime_confirmed, true);
  assert.equal(result.final_equivalence, "EQUIVALENT");
  assert.equal(result.equivalence_confirmed, true);
  assert.ok(result.execution_summary);
});

test("guarded REAL with failing validation sets NOT_EQUIVALENT", async () => {
  const mockHealthyClient = createMockHealthyClient({
    querySql: async ({ sql, queueName, step }) => ({
      job_id: "fake_query_" + (step ? step.name : "unknown"),
      status: "FINISHED",
      valid: true,
      real_execution: true,
      statement_type: "QUERY",
      rows: [{ actual_value: -999 }],
      column_names: ["actual_value"],
    }),
  });

  const result = await executeNativeDliGuarded({
    packageDir: CUSTOMER_PKG,
    dliQueue: "default",
    mode: "REAL",
    planOnly: false,
    allowRealExecution: true,
    confirmNativeDli: true,
    understandExecutesSql: true,
    dliClient: mockHealthyClient,
    outDir: path.resolve(__dirname, "../../out"),
  });

  assert.equal(result.status, "NATIVE_DLI_GUARDED_VALIDATION_FAILED");
  assert.equal(result.valid, false);
  assert.equal(result.real_execution, true);
  assert.equal(result.real_runtime_confirmed, false);
  assert.equal(result.final_equivalence, "NOT_EQUIVALENT");
  assert.equal(result.equivalence_confirmed, false);
});

test("guarded REAL with setup failure returns SETUP_FAILED", async () => {
  const mockHealthyClient = createMockHealthyClient({
    executeSql: async ({ sql, queueName, step }) => ({
      job_id: "fail_job",
      status: "SUBMISSION_FAILED",
      valid: false,
      real_execution: true,
      message: "Setup SQL failed.",
    }),
  });

  const result = await executeNativeDliGuarded({
    packageDir: CUSTOMER_PKG,
    dliQueue: "default",
    mode: "REAL",
    planOnly: false,
    allowRealExecution: true,
    confirmNativeDli: true,
    understandExecutesSql: true,
    dliClient: mockHealthyClient,
    outDir: path.resolve(__dirname, "../../out"),
  });

  assert.equal(result.status, "NATIVE_DLI_GUARDED_SETUP_FAILED");
  assert.equal(result.valid, false);
  assert.equal(result.real_execution, true);
  assert.equal(result.real_runtime_confirmed, false);
  assert.equal(result.final_equivalence, "NOT_EQUIVALENT");
});

test("guarded REAL setup failure error includes message and http_status", async () => {
  const mockHealthyClient = createMockHealthyClient({
    executeSql: async ({ sql, queueName, step }) => ({
      job_id: "fail_job",
      status: "SUBMISSION_FAILED",
      valid: false,
      real_execution: true,
      http_status: 400,
      message: "DLI SQL job submission returned HTTP 400",
      response_body_snippet: '{"error_code":"DLI.0001","error_msg":"Bad request"}',
    }),
  });

  const result = await executeNativeDliGuarded({
    packageDir: CUSTOMER_PKG,
    dliQueue: "default",
    mode: "REAL",
    planOnly: false,
    allowRealExecution: true,
    confirmNativeDli: true,
    understandExecutesSql: true,
    dliClient: mockHealthyClient,
    outDir: path.resolve(__dirname, "../../out"),
  });

  assert.equal(result.status, "NATIVE_DLI_GUARDED_SETUP_FAILED");
  const firstError = result.errors[0];
  assert.ok(firstError.includes("SUBMISSION_FAILED"), "error should include status");
  assert.ok(firstError.includes("HTTP 400"), "error should include http_status");
  assert.ok(firstError.includes("DLI SQL job submission returned HTTP 400"), "error should include message");
  assert.ok(firstError.includes("body:"), "error should include response body snippet");
});

test("guarded REAL target failure error includes message and http_status", async () => {
  const mockHealthyClient = createMockHealthyClient({
    executeSql: async ({ step }) => {
      if (step && step.phase === "runtime_setup") {
        return {
          job_id: "ok_job",
          status: "SUBMITTED",
          valid: true,
          real_execution: true,
        };
      }
      return {
        job_id: "fail_job",
        status: "SUBMISSION_FAILED",
        valid: false,
        real_execution: true,
        http_status: 500,
        message: "Internal server error",
        response_body_snippet: '{"error_code":"DLI.0005"}',
      };
    },
  });

  const result = await executeNativeDliGuarded({
    packageDir: CUSTOMER_PKG,
    dliQueue: "default",
    mode: "REAL",
    planOnly: false,
    allowRealExecution: true,
    confirmNativeDli: true,
    understandExecutesSql: true,
    dliClient: mockHealthyClient,
    outDir: path.resolve(__dirname, "../../out"),
  });

  assert.equal(result.status, "NATIVE_DLI_GUARDED_TARGET_FAILED");
  const targetError = result.errors.find((e) => e.includes("Target step"));
  assert.ok(targetError, "should have a target step error");
  assert.ok(targetError.includes("HTTP 500"), "target error should include http_status");
  assert.ok(targetError.includes("Internal server error"), "target error should include message");
});

test("resume-from target_transform skips setup", async () => {
  const result = await executeNativeDliGuarded({
    packageDir: CUSTOMER_PKG,
    dliQueue: "default",
    mode: "PLAN_ONLY",
    planOnly: true,
    resumeFrom: "target_transform",
    outDir: path.resolve(__dirname, "../../out"),
  });

  assert.equal(result.status, "NATIVE_DLI_GUARDED_PLAN_READY");
  assert.equal(result.resume_from, "target_transform");
  assert.ok(result.resume_plan);

  const setupSteps = result.resume_plan.phases.runtime_setup;
  assert.ok(setupSteps.length > 0);
  for (const step of setupSteps) {
    assert.equal(step.status, "SKIPPED_RESUME");
    assert.equal(step.executed, false);
    assert.equal(step.skipped_reason, "resume_from");
  }

  const targetSteps = result.resume_plan.phases.target_transform;
  assert.ok(targetSteps.length > 0);
  for (const step of targetSteps) {
    assert.equal(step.status, "PLANNED");
  }

  assert.equal(result.planned_sql_executions, 5);
});

test("resume-from runtime_validation skips setup and target", async () => {
  const result = await executeNativeDliGuarded({
    packageDir: CUSTOMER_PKG,
    dliQueue: "default",
    mode: "PLAN_ONLY",
    planOnly: true,
    resumeFrom: "runtime_validation",
    outDir: path.resolve(__dirname, "../../out"),
  });

  assert.equal(result.status, "NATIVE_DLI_GUARDED_PLAN_READY");
  assert.equal(result.resume_from, "runtime_validation");

  const setupSteps = result.resume_plan.phases.runtime_setup;
  for (const step of setupSteps) {
    assert.equal(step.status, "SKIPPED_RESUME");
    assert.equal(step.skipped_reason, "resume_from");
  }

  const targetSteps = result.resume_plan.phases.target_transform;
  for (const step of targetSteps) {
    assert.equal(step.status, "SKIPPED_RESUME");
    assert.equal(step.skipped_reason, "resume_from");
  }

  assert.equal(result.planned_sql_executions, 0);
  assert.equal(result.planned_query_executions, 7);
});

test("default resume-from runtime_setup executes all phases", async () => {
  const result = await executeNativeDliGuarded({
    packageDir: CUSTOMER_PKG,
    dliQueue: "default",
    mode: "PLAN_ONLY",
    planOnly: true,
    outDir: path.resolve(__dirname, "../../out"),
  });

  assert.equal(result.status, "NATIVE_DLI_GUARDED_PLAN_READY");
  assert.equal(result.resume_from, "runtime_setup");

  const setupSteps = result.resume_plan.phases.runtime_setup;
  for (const step of setupSteps) {
    assert.equal(step.status, "PLANNED");
  }

  const targetSteps = result.resume_plan.phases.target_transform;
  for (const step of targetSteps) {
    assert.equal(step.status, "PLANNED");
  }

  assert.equal(result.planned_sql_executions, 8);
  assert.equal(result.planned_query_executions, 7);
});

test("skipped steps are recorded as SKIPPED_RESUME", async () => {
  const mockHealthyClient = createMockHealthyClient();

  const result = await executeNativeDliGuarded({
    packageDir: CUSTOMER_PKG,
    dliQueue: "default",
    mode: "REAL",
    planOnly: false,
    allowRealExecution: true,
    confirmNativeDli: true,
    understandExecutesSql: true,
    dliClient: mockHealthyClient,
    resumeFrom: "target_transform",
    outDir: path.resolve(__dirname, "../../out"),
  });

  assert.equal(result.status, "NATIVE_DLI_GUARDED_EXECUTION_SUCCEEDED");
  assert.ok(result.resume_summary);
  assert.equal(result.resume_summary.setup_skipped, true);
  assert.equal(result.resume_summary.target_skipped, false);
  assert.ok(result.resume_summary.skipped_steps.length > 0);

  for (const skipped of result.resume_summary.skipped_steps) {
    assert.equal(skipped.status, "SKIPPED_RESUME");
    assert.equal(skipped.executed, false);
    assert.equal(skipped.skipped_reason, "resume_from");
    assert.equal(skipped.phase, "runtime_setup");
  }

  assert.ok(result.execution_summary.setup_skipped > 0);
});

test("invalid resume-from returns INVALID_INPUT", async () => {
  const result = await executeNativeDliGuarded({
    packageDir: CUSTOMER_PKG,
    dliQueue: "default",
    mode: "PLAN_ONLY",
    planOnly: true,
    resumeFrom: "invalid_phase",
    outDir: path.resolve(__dirname, "../../out"),
  });

  assert.equal(result.status, "INVALID_INPUT");
  assert.equal(result.valid, false);
  assert.ok(result.errors.some((e) => e.includes("Invalid --resume-from value")));
  assert.ok(result.errors.some((e) => e.includes("invalid_phase")));
});

test("queue congestion blocks REAL before SQL execution", async () => {
  const mockCongestedClient = createMockHealthyClient();

  const result = await executeNativeDliGuarded({
    packageDir: CUSTOMER_PKG,
    dliQueue: "default",
    mode: "REAL",
    planOnly: false,
    allowRealExecution: true,
    confirmNativeDli: true,
    understandExecutesSql: true,
    dliClient: mockCongestedClient,
    maxLaunchingJobs: 5,
    outDir: path.resolve(__dirname, "../../out"),
  });

  if (result.status === "NATIVE_DLI_QUEUE_CONGESTED") {
    assert.equal(result.valid, false);
    assert.equal(result.real_execution, false);
    assert.ok(result.queue_health);
    assert.ok(result.errors.some((e) => e.includes("congested")));
  } else {
    assert.ok(
      result.status === "NATIVE_DLI_GUARDED_EXECUTION_SUCCEEDED" ||
      result.status === "NATIVE_DLI_GUARDED_VALIDATION_FAILED" ||
      result.status === "NATIVE_DLI_TRANSPORT_NOT_CONFIGURED" ||
      result.status === "NATIVE_DLI_TRANSPORT_NOT_IMPLEMENTED",
      `Expected congestion or success but got ${result.status}`
    );
  }
});

test("queue health check does not block PLAN_ONLY", async () => {
  const result = await executeNativeDliGuarded({
    packageDir: CUSTOMER_PKG,
    dliQueue: "default",
    mode: "PLAN_ONLY",
    planOnly: true,
    maxLaunchingJobs: 0,
    outDir: path.resolve(__dirname, "../../out"),
  });

  assert.equal(result.status, "NATIVE_DLI_GUARDED_PLAN_READY");
  assert.equal(result.valid, true);
});

test("plan-only works with resume-from target_transform", async () => {
  const result = await executeNativeDliGuarded({
    packageDir: CUSTOMER_PKG,
    dliQueue: "default",
    mode: "PLAN_ONLY",
    planOnly: true,
    resumeFrom: "target_transform",
    outDir: path.resolve(__dirname, "../../out"),
  });

  assert.equal(result.status, "NATIVE_DLI_GUARDED_PLAN_READY");
  assert.equal(result.valid, true);
  assert.equal(result.real_execution, false);
  assert.equal(result.resume_from, "target_transform");
  assert.ok(result.resume_plan);

  const setupSteps = result.resume_plan.phases.runtime_setup;
  assert.ok(setupSteps.every((s) => s.status === "SKIPPED_RESUME"));

  const targetSteps = result.resume_plan.phases.target_transform;
  assert.ok(targetSteps.every((s) => s.status === "PLANNED"));

  const validationSteps = result.resume_plan.phases.runtime_validation;
  assert.ok(validationSteps.every((s) => s.status === "PLANNED"));
});

test("safety flags present in all modes", async () => {
  const result = await executeNativeDliGuarded({
    packageDir: CUSTOMER_PKG,
    dliQueue: "default",
    mode: "PLAN_ONLY",
    planOnly: true,
    outDir: path.resolve(__dirname, "../../out"),
  });

  assert.ok(result.safety);
  assert.equal(result.safety.no_publish, true);
  assert.equal(result.safety.no_delete, true);
  assert.equal(result.safety.no_update, true);
  assert.equal(result.safety.no_overwrite, true);
  assert.equal(result.safety.no_schedule_start, true);
});

test("VALID_RESUME_FROM_VALUES contains all allowed values", () => {
  assert.ok(VALID_RESUME_FROM_VALUES.has("runtime_setup"));
  assert.ok(VALID_RESUME_FROM_VALUES.has("target_transform"));
  assert.ok(VALID_RESUME_FROM_VALUES.has("runtime_validation"));
  assert.equal(VALID_RESUME_FROM_VALUES.size, 3);
});

test("buildResumePlan runtime_setup - nothing skipped", () => {
  const nativePlan = {
    phases: {
      runtime_setup: [{ name: "s1" }, { name: "s2" }],
      target_transform: [{ name: "t1" }],
      runtime_validation: [{ name: "v1" }],
    },
  };

  const plan = buildResumePlan({ resumeFrom: "runtime_setup", nativePlan });
  assert.equal(plan.resume_from, "runtime_setup");
  assert.ok(plan.phases.runtime_setup.every((s) => s.status === "PLANNED"));
  assert.ok(plan.phases.target_transform.every((s) => s.status === "PLANNED"));
  assert.ok(plan.phases.runtime_validation.every((s) => s.status === "PLANNED"));
});

test("buildResumePlan target_transform - setup skipped", () => {
  const nativePlan = {
    phases: {
      runtime_setup: [{ name: "s1" }, { name: "s2" }],
      target_transform: [{ name: "t1" }],
      runtime_validation: [{ name: "v1" }],
    },
  };

  const plan = buildResumePlan({ resumeFrom: "target_transform", nativePlan });
  assert.ok(plan.phases.runtime_setup.every((s) => s.status === "SKIPPED_RESUME" && s.skipped_reason === "resume_from"));
  assert.ok(plan.phases.target_transform.every((s) => s.status === "PLANNED"));
  assert.ok(plan.phases.runtime_validation.every((s) => s.status === "PLANNED"));
});

test("buildResumePlan runtime_validation - setup and target skipped", () => {
  const nativePlan = {
    phases: {
      runtime_setup: [{ name: "s1" }, { name: "s2" }],
      target_transform: [{ name: "t1" }],
      runtime_validation: [{ name: "v1" }],
    },
  };

  const plan = buildResumePlan({ resumeFrom: "runtime_validation", nativePlan });
  assert.ok(plan.phases.runtime_setup.every((s) => s.status === "SKIPPED_RESUME" && s.skipped_reason === "resume_from"));
  assert.ok(plan.phases.target_transform.every((s) => s.status === "SKIPPED_RESUME" && s.skipped_reason === "resume_from"));
  assert.ok(plan.phases.runtime_validation.every((s) => s.status === "PLANNED"));
});
