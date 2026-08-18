const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const os = require("os");
const path = require("path");
const {
  simulateNativeDliExecution,
  simulateNativeStep,
  buildSimulatedEquivalenceSummary,
  buildSimulationSafetyPolicy,
} = require("../../src/runtime/native-dli-simulator");

const ORDERS_DIR = path.resolve(__dirname, "../../cases/golden/orders_pipeline_simple");
const CUSTOMER_DIR = path.resolve(__dirname, "../../cases/golden/customer_status_pipeline_simple");

test("simulate orders package succeeds", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "native-sim-"));
  const result = simulateNativeDliExecution({
    packageDir: ORDERS_DIR,
    dliQueue: "default",
    outDir,
  });

  assert.equal(result.valid, true);
  assert.equal(result.status, "NATIVE_DLI_SIMULATION_COMPLETE");
});

test("simulate customer package succeeds", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "native-sim-cust-"));
  const result = simulateNativeDliExecution({
    packageDir: CUSTOMER_DIR,
    dliQueue: "default",
    outDir,
  });

  assert.equal(result.valid, true);
  assert.equal(result.status, "NATIVE_DLI_SIMULATION_COMPLETE");
});

test("status NATIVE_DLI_SIMULATION_COMPLETE", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "native-sim-status-"));
  const result = simulateNativeDliExecution({
    packageDir: ORDERS_DIR,
    dliQueue: "default",
    outDir,
  });

  assert.equal(result.status, "NATIVE_DLI_SIMULATION_COMPLETE");
});

test("final_equivalence SIMULATED_EQUIVALENT", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "native-sim-eq-"));
  const result = simulateNativeDliExecution({
    packageDir: ORDERS_DIR,
    dliQueue: "default",
    outDir,
  });

  assert.equal(result.final_equivalence, "SIMULATED_EQUIVALENT");
});

test("equivalence_confirmed false", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "native-sim-conf-"));
  const result = simulateNativeDliExecution({
    packageDir: ORDERS_DIR,
    dliQueue: "default",
    outDir,
  });

  assert.equal(result.equivalence_confirmed, false);
});

test("simulation_only true", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "native-sim-only-"));
  const result = simulateNativeDliExecution({
    packageDir: ORDERS_DIR,
    dliQueue: "default",
    outDir,
  });

  assert.equal(result.simulation_only, true);
});

test("total steps simulated 16", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "native-sim-steps-"));
  const result = simulateNativeDliExecution({
    packageDir: ORDERS_DIR,
    dliQueue: "default",
    outDir,
  });

  assert.equal(result.steps_simulated, 16);
});

test("no step has executed true", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "native-sim-noexec-"));
  const result = simulateNativeDliExecution({
    packageDir: ORDERS_DIR,
    dliQueue: "default",
    outDir,
  });

  for (const step of result.simulated_step_results) {
    assert.equal(step.executed, false);
    assert.equal(step.simulated, true);
    assert.equal(step.status, "SIMULATED_PASS");
  }
});

test("safety.no_sql_execution true", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "native-sim-sql-"));
  const result = simulateNativeDliExecution({
    packageDir: ORDERS_DIR,
    dliQueue: "default",
    outDir,
  });

  assert.equal(result.safety.no_sql_execution, true);
});

test("safety.no_cloud_api_calls true", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "native-sim-cloud-"));
  const result = simulateNativeDliExecution({
    packageDir: ORDERS_DIR,
    dliQueue: "default",
    outDir,
  });

  assert.equal(result.safety.no_cloud_api_calls, true);
});

test("evidence files written", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "native-sim-evidence-"));
  const result = simulateNativeDliExecution({
    packageDir: ORDERS_DIR,
    dliQueue: "default",
    outDir,
  });

  assert.ok(result.evidence_paths);
  assert.ok(fs.existsSync(result.evidence_paths.result_json));
  assert.ok(fs.existsSync(result.evidence_paths.report_md));
  assert.ok(fs.existsSync(result.evidence_paths.run_result_json));
  assert.ok(fs.existsSync(result.evidence_paths.run_report_md));
  assert.ok(fs.existsSync(result.evidence_paths.current_run_json));
});

test("validation rows derived from validation queries", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "native-sim-rows-"));
  const result = simulateNativeDliExecution({
    packageDir: ORDERS_DIR,
    dliQueue: "default",
    outDir,
  });

  const eq = result.simulated_equivalence_summary;
  assert.ok(eq);
  assert.equal(eq.final_equivalence, "SIMULATED_EQUIVALENT");
  assert.equal(eq.equivalence_confirmed, false);
  assert.equal(eq.simulation_only, true);
  assert.ok(eq.table_rows.length > 0);

  for (const row of eq.table_rows) {
    assert.ok(row.object_name);
    assert.ok(row.query_id);
    assert.equal(row.simulated_match, true);
    assert.equal(row.simulated_only, true);
  }
});

test("customer simulation has correct migration_id", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "native-sim-cust-id-"));
  const result = simulateNativeDliExecution({
    packageDir: CUSTOMER_DIR,
    dliQueue: "default",
    outDir,
  });

  assert.equal(result.valid, true);
  assert.equal(result.migration_id, "customer_status_pipeline_simple");
  assert.equal(result.steps_simulated, 16);
});

test("missing packageDir returns NATIVE_DLI_SIMULATION_FAILED", () => {
  const result = simulateNativeDliExecution({});

  assert.equal(result.valid, false);
  assert.equal(result.status, "NATIVE_DLI_SIMULATION_FAILED");
  assert.ok(result.errors.some((e) => e.includes("packageDir")));
});

test("safety.simulation_only true", () => {
  const safety = buildSimulationSafetyPolicy();
  assert.equal(safety.simulation_only, true);
  assert.equal(safety.native_dli_simulation_only, true);
  assert.equal(safety.no_cloud_api_calls, true);
  assert.equal(safety.no_sql_execution, true);
  assert.equal(safety.no_runtime_execution, true);
  assert.equal(safety.no_confirm, true);
  assert.equal(safety.no_commands_executed, true);
});

test("simulateNativeStep produces correct structure", () => {
  const step = {
    execution_order: 1,
    phase: "runtime_setup",
    type: "DLI_SQL",
    name: "01_create_schema.sql",
    file_path: "/some/path",
    statement_count: 1,
    execution_required: true,
    executed: false,
  };

  const result = simulateNativeStep(step);
  assert.equal(result.executed, false);
  assert.equal(result.simulated, true);
  assert.equal(result.status, "SIMULATED_PASS");
  assert.equal(result.phase, "runtime_setup");
  assert.equal(result.name, "01_create_schema.sql");
});

test("buildSimulatedEquivalenceSummary excludes FINAL_EQUIVALENCE queries", () => {
  const queries = [
    { id: "raw_count", type: "TABLE_COUNT", object_name: "RAW", expected: 5 },
    { id: "final_equivalence", type: "FINAL_EQUIVALENCE", object_name: "EQ", expected: "EQUIVALENT" },
  ];

  const summary = buildSimulatedEquivalenceSummary({
    validationQueries: queries,
    migrationId: "test",
  });

  assert.equal(summary.table_rows.length, 1);
  assert.equal(summary.table_rows[0].query_id, "raw_count");
});

test("run_id is generated", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "native-sim-runid-"));
  const result = simulateNativeDliExecution({
    packageDir: ORDERS_DIR,
    dliQueue: "default",
    outDir,
  });

  assert.ok(result.run_id);
  assert.ok(result.run_id.startsWith("run_"));
});

test("setup + target + validation + equivalence = steps_simulated", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "native-sim-count-"));
  const result = simulateNativeDliExecution({
    packageDir: ORDERS_DIR,
    dliQueue: "default",
    outDir,
  });

  const expected =
    result.setup_steps + result.target_steps + result.validation_steps + 1;
  assert.equal(result.steps_simulated, expected);
});
