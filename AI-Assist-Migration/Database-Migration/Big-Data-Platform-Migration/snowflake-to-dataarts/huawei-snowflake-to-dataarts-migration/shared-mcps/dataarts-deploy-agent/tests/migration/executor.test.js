const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { executeMigration } = require("../../src/migration/executor");

const GOLDEN_DIR = path.resolve(__dirname, "../../cases/golden/orders_pipeline_simple");
const CUSTOMER_GOLDEN_DIR = path.resolve(__dirname, "../../cases/golden/customer_status_pipeline_simple");

test("dry-run golden package returns MIGRATION_EXECUTE_DRY_RUN_READY", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "mig-exec-"));
  const result = executeMigration({
    packageDir: GOLDEN_DIR,
    jobName: "test_migration_execute",
    dliQueue: "default",
    dryRun: true,
    outDir,
  });

  assert.equal(result.valid, true);
  assert.equal(result.status, "MIGRATION_EXECUTE_DRY_RUN_READY");
  assert.equal(result.mode, "DRY_RUN");
  assert.equal(result.migration_id, "orders_pipeline_simple");
  assert.equal(result.job_name, "test_migration_execute");
  assert.ok(result.run_id);
  assert.ok(result.runtime_artifacts_dir);
});

test("missing packageDir invalid", () => {
  const result = executeMigration({
    jobName: "test_job",
    dryRun: true,
  });

  assert.equal(result.valid, false);
  assert.equal(result.status, "RUNTIME_ENGINE_FAILED");
  assert.ok(result.errors.some((e) => e.includes("packageDir")));
});

test("missing jobName invalid", () => {
  const result = executeMigration({
    packageDir: GOLDEN_DIR,
    dryRun: true,
  });

  assert.equal(result.valid, false);
  assert.equal(result.status, "RUNTIME_ENGINE_FAILED");
  assert.ok(result.errors.some((e) => e.includes("jobName")));
});

test("neither dryRun nor confirm invalid", () => {
  const result = executeMigration({
    packageDir: GOLDEN_DIR,
    jobName: "test_job",
  });

  assert.equal(result.valid, false);
  assert.equal(result.status, "INVALID_INPUT");
  assert.ok(result.errors.some((e) => e.includes("--dry-run") || e.includes("--confirm")));
});

test("confirm mode without legacy-demo adapter returns UNSUPPORTED_MODE", () => {
  const result = executeMigration({
    packageDir: GOLDEN_DIR,
    jobName: "test_job",
    confirm: true,
  });

  assert.equal(result.valid, false);
  assert.equal(result.status, "UNSUPPORTED_MODE");
  assert.equal(result.mode, "CONFIRM");
  assert.ok(result.errors.some((e) => e.includes("adapter=legacy-demo")));
});

test("dry-run returns 16 planned commands", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "mig-exec-"));
  const result = executeMigration({
    packageDir: GOLDEN_DIR,
    jobName: "test_migration_execute",
    dliQueue: "default",
    dryRun: true,
    outDir,
  });

  assert.equal(result.valid, true);
  assert.equal(result.command_sequence.length, 16);
});

test("safety.no_commands_executed true", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "mig-exec-"));
  const result = executeMigration({
    packageDir: GOLDEN_DIR,
    jobName: "test_migration_execute",
    dliQueue: "default",
    dryRun: true,
    outDir,
  });

  assert.equal(result.valid, true);
  assert.equal(result.safety.no_commands_executed, true);
});

test("safety.no_runtime_execution true", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "mig-exec-"));
  const result = executeMigration({
    packageDir: GOLDEN_DIR,
    jobName: "test_migration_execute",
    dliQueue: "default",
    dryRun: true,
    outDir,
  });

  assert.equal(result.valid, true);
  assert.equal(result.safety.no_runtime_execution, true);
});

test("migration execute dry-run includes adapter runtime-engine", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "mig-exec-adapter-"));
  const result = executeMigration({
    packageDir: GOLDEN_DIR,
    jobName: "test_migration_execute_adapter",
    dliQueue: "default",
    dryRun: true,
    outDir,
  });

  assert.equal(result.valid, true);
  assert.equal(result.adapter, "runtime-engine");
  assert.equal(result.adapter_status, "RUNTIME_ADAPTER_DRY_RUN_READY");
});

test("migration execute dry-run supports adapter legacy-demo", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "mig-exec-legacy-"));
  const result = executeMigration({
    packageDir: GOLDEN_DIR,
    jobName: "test_migration_execute_legacy",
    dliQueue: "default",
    dryRun: true,
    adapter: "legacy-demo",
    outDir,
  });

  assert.equal(result.valid, true);
  assert.equal(result.status, "MIGRATION_EXECUTE_DRY_RUN_READY");
  assert.equal(result.adapter, "legacy-demo");
  assert.equal(result.adapter_status, "LEGACY_DEMO_ADAPTER_DRY_RUN_READY");
});

test("migration execute supports adapter koocli in dry-run", () => {
  const result = executeMigration({
    packageDir: GOLDEN_DIR,
    jobName: "test_migration_execute_koocli",
    dliQueue: "default",
    dryRun: true,
    adapter: "koocli",
  });

  assert.equal(result.adapter, "koocli");
  assert.equal(result.mode, "DRY_RUN");
  assert.ok(
    result.status === "MIGRATION_EXECUTE_DRY_RUN_READY" ||
    result.status === "KOOCLI_ADAPTER_UNAVAILABLE"
  );

  if (result.status === "MIGRATION_EXECUTE_DRY_RUN_READY") {
    assert.equal(result.valid, true);
  } else {
    assert.equal(result.valid, false);
    assert.ok(result.errors.some((e) => e.includes("hcloud")));
  }
});

test("migration execute koocli unavailable returns KOOCLI_ADAPTER_UNAVAILABLE cleanly", () => {
  const result = executeMigration({
    packageDir: GOLDEN_DIR,
    jobName: "test_koocli_unavail",
    dliQueue: "default",
    dryRun: true,
    adapter: "koocli",
  });

  if (!result.valid) {
    assert.equal(result.status, "KOOCLI_ADAPTER_UNAVAILABLE");
    assert.ok(result.errors.some((e) => e.includes("hcloud")));
  }
});

test("migration execute confirm with legacy-demo returns MIGRATION_EXECUTION_COMPLETE on mocked success", () => {
  const mockRunner = () => ({ exit_code: 0, success: true, outputTail: "", lastLines: [] });

  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "mig-exec-confirm-"));
  const result = executeMigration({
    packageDir: GOLDEN_DIR,
    jobName: "test_confirm_legacy",
    dliQueue: "default",
    confirm: true,
    adapter: "legacy-demo",
    outDir,
    commandRunner: mockRunner,
  });

  assert.equal(result.valid, true);
  assert.equal(result.status, "MIGRATION_EXECUTION_COMPLETE");
  assert.equal(result.mode, "CONFIRM");
  assert.equal(result.adapter, "legacy-demo");
  assert.ok(result.run_id);
  assert.ok(result.command);
});

test("migration execute confirm with runtime-engine returns UNSUPPORTED_MODE", () => {
  const result = executeMigration({
    packageDir: GOLDEN_DIR,
    jobName: "test_confirm_re",
    dliQueue: "default",
    confirm: true,
    adapter: "runtime-engine",
  });

  assert.equal(result.valid, false);
  assert.equal(result.status, "UNSUPPORTED_MODE");
  assert.equal(result.mode, "CONFIRM");
  assert.ok(result.errors.some((e) => e.includes("adapter=legacy-demo")));
});

test("migration execute confirm with koocli returns UNSUPPORTED_MODE", () => {
  const result = executeMigration({
    packageDir: GOLDEN_DIR,
    jobName: "test_confirm_koocli",
    dliQueue: "default",
    confirm: true,
    adapter: "koocli",
  });

  assert.equal(result.valid, false);
  assert.equal(result.status, "UNSUPPORTED_MODE");
  assert.ok(result.errors.some((e) => e.includes("adapter=legacy-demo")));
});

test("migration execute confirm without explicit adapter returns UNSUPPORTED_MODE", () => {
  const result = executeMigration({
    packageDir: GOLDEN_DIR,
    jobName: "test_confirm_no_adapter",
    dliQueue: "default",
    confirm: true,
  });

  assert.equal(result.valid, false);
  assert.equal(result.status, "UNSUPPORTED_MODE");
  assert.ok(result.errors.some((e) => e.includes("adapter=legacy-demo")));
});

test("confirm result includes safety.confirm_required true", () => {
  const mockRunner = () => ({ exit_code: 0, success: true, outputTail: "", lastLines: [] });

  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "mig-exec-confirm-safety1-"));
  const result = executeMigration({
    packageDir: GOLDEN_DIR,
    jobName: "test_confirm_safety1",
    dliQueue: "default",
    confirm: true,
    adapter: "legacy-demo",
    outDir,
    commandRunner: mockRunner,
  });

  assert.equal(result.valid, true);
  assert.equal(result.safety.confirm_required, true);
});

test("confirm result includes only_run_immediate_for_execution true", () => {
  const mockRunner = () => ({ exit_code: 0, success: true, outputTail: "", lastLines: [] });

  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "mig-exec-confirm-safety2-"));
  const result = executeMigration({
    packageDir: GOLDEN_DIR,
    jobName: "test_confirm_safety2",
    dliQueue: "default",
    confirm: true,
    adapter: "legacy-demo",
    outDir,
    commandRunner: mockRunner,
  });

  assert.equal(result.valid, true);
  assert.equal(result.safety.only_run_immediate_for_execution, true);
});

test("migration execute dry-run legacy-demo includes planned_legacy_command", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "mig-exec-legacy-cmd-"));
  const result = executeMigration({
    packageDir: GOLDEN_DIR,
    jobName: "test_legacy_cmd",
    dliQueue: "default",
    dryRun: true,
    adapter: "legacy-demo",
    outDir,
  });

  assert.equal(result.valid, true);
  assert.ok(result.planned_legacy_command);
  assert.ok(result.planned_legacy_command.includes("npm run demo:one-shot"));
  assert.ok(result.planned_legacy_command.includes("--confirm"));
  assert.ok(result.planned_legacy_command.includes("--job-name test_legacy_cmd"));
});

test("customer status dry-run returns MIGRATION_EXECUTE_DRY_RUN_READY", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "mig-exec-"));
  const result = executeMigration({
    packageDir: CUSTOMER_GOLDEN_DIR,
    jobName: "customer_status_dryrun",
    dliQueue: "default",
    dryRun: true,
    outDir,
  });

  assert.equal(result.valid, true);
  assert.equal(result.status, "MIGRATION_EXECUTE_DRY_RUN_READY");
  assert.equal(result.mode, "DRY_RUN");
  assert.equal(result.migration_id, "customer_status_pipeline_simple");
  assert.equal(result.job_name, "customer_status_dryrun");
  assert.ok(result.run_id);
  assert.ok(result.runtime_artifacts_dir);
});

test("customer status dry-run legacy-demo includes planned_legacy_command", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "mig-exec-cust-legacy-"));
  const result = executeMigration({
    packageDir: CUSTOMER_GOLDEN_DIR,
    jobName: "customer_status_legacy_dryrun",
    dliQueue: "default",
    dryRun: true,
    adapter: "legacy-demo",
    outDir,
  });

  assert.equal(result.valid, true);
  assert.equal(result.status, "MIGRATION_EXECUTE_DRY_RUN_READY");
  assert.equal(result.adapter, "legacy-demo");
  assert.ok(result.planned_legacy_command);
  assert.ok(result.planned_legacy_command.includes("npm run demo:one-shot"));
  assert.ok(result.planned_legacy_command.includes("--job-name customer_status_legacy_dryrun"));
});

test("migration execute dry-run supports adapter native-dli", () => {
  const result = executeMigration({
    packageDir: GOLDEN_DIR,
    jobName: "test_native_dli_dryrun",
    dliQueue: "default",
    dryRun: true,
    adapter: "native-dli",
  });

  assert.equal(result.valid, true);
  assert.equal(result.status, "MIGRATION_EXECUTE_DRY_RUN_READY");
  assert.equal(result.adapter, "native-dli");
  assert.equal(result.mode, "DRY_RUN");
  assert.equal(result.migration_id, "orders_pipeline_simple");
  assert.ok(result.command_sequence.length > 0);
  assert.equal(result.command_sequence.length, 16);
});

test("migration execute confirm with adapter native-dli returns UNSUPPORTED_MODE", () => {
  const result = executeMigration({
    packageDir: GOLDEN_DIR,
    jobName: "test_confirm_native_dli",
    dliQueue: "default",
    confirm: true,
    adapter: "native-dli",
  });

  assert.equal(result.valid, false);
  assert.equal(result.status, "UNSUPPORTED_MODE");
  assert.equal(result.mode, "CONFIRM");
  assert.ok(result.errors.some((e) => e.includes("adapter=legacy-demo")));
});

test("migration execute dry-run native-dli for customer_status", () => {
  const result = executeMigration({
    packageDir: CUSTOMER_GOLDEN_DIR,
    jobName: "customer_native_dli_dryrun",
    dliQueue: "default",
    dryRun: true,
    adapter: "native-dli",
  });

  assert.equal(result.valid, true);
  assert.equal(result.status, "MIGRATION_EXECUTE_DRY_RUN_READY");
  assert.equal(result.adapter, "native-dli");
  assert.equal(result.migration_id, "customer_status_pipeline_simple");
  assert.equal(result.command_sequence.length, 16);
});

test("migration execute simulate native-dli succeeds", () => {
  const result = executeMigration({
    packageDir: GOLDEN_DIR,
    jobName: "test_simulate_native_dli",
    dliQueue: "default",
    simulate: true,
    adapter: "native-dli",
  });

  assert.equal(result.valid, true);
  assert.equal(result.status, "MIGRATION_EXECUTE_SIMULATION_COMPLETE");
  assert.equal(result.mode, "SIMULATE");
  assert.equal(result.adapter, "native-dli");
  assert.equal(result.final_equivalence, "SIMULATED_EQUIVALENT");
  assert.equal(result.equivalence_confirmed, false);
  assert.equal(result.simulation_only, true);
  assert.ok(result.run_id);
  assert.ok(result.native_simulation_result);
});

test("migration execute simulate with legacy-demo unsupported", () => {
  const result = executeMigration({
    packageDir: GOLDEN_DIR,
    jobName: "test_simulate_legacy",
    dliQueue: "default",
    simulate: true,
    adapter: "legacy-demo",
  });

  assert.equal(result.valid, false);
  assert.equal(result.status, "UNSUPPORTED_MODE");
  assert.equal(result.mode, "SIMULATE");
  assert.ok(result.errors.some((e) => e.includes("native-dli")));
});

test("migration execute simulate with koocli unsupported", () => {
  const result = executeMigration({
    packageDir: GOLDEN_DIR,
    jobName: "test_simulate_koocli",
    dliQueue: "default",
    simulate: true,
    adapter: "koocli",
  });

  assert.equal(result.valid, false);
  assert.equal(result.status, "UNSUPPORTED_MODE");
  assert.ok(result.errors.some((e) => e.includes("native-dli")));
});

test("migration execute simulate result equivalence_confirmed false", () => {
  const result = executeMigration({
    packageDir: GOLDEN_DIR,
    jobName: "test_simulate_eq_false",
    dliQueue: "default",
    simulate: true,
    adapter: "native-dli",
  });

  assert.equal(result.valid, true);
  assert.equal(result.equivalence_confirmed, false);
  assert.equal(result.final_equivalence, "SIMULATED_EQUIVALENT");
});

test("migration execute simulate native-dli for customer_status", () => {
  const result = executeMigration({
    packageDir: CUSTOMER_GOLDEN_DIR,
    jobName: "customer_sim_native_dli",
    dliQueue: "default",
    simulate: true,
    adapter: "native-dli",
  });

  assert.equal(result.valid, true);
  assert.equal(result.status, "MIGRATION_EXECUTE_SIMULATION_COMPLETE");
  assert.equal(result.migration_id, "customer_status_pipeline_simple");
  assert.equal(result.final_equivalence, "SIMULATED_EQUIVALENT");
  assert.equal(result.equivalence_confirmed, false);
});

test("migration execute simulate without adapter defaults to runtime-engine and returns UNSUPPORTED_MODE", () => {
  const result = executeMigration({
    packageDir: GOLDEN_DIR,
    jobName: "test_simulate_no_adapter",
    dliQueue: "default",
    simulate: true,
  });

  assert.equal(result.valid, false);
  assert.equal(result.status, "UNSUPPORTED_MODE");
  assert.ok(result.errors.some((e) => e.includes("native-dli")));
});

test("migration execute mock native-dli succeeds", () => {
  const result = executeMigration({
    packageDir: GOLDEN_DIR,
    jobName: "test_mock_native_dli",
    dliQueue: "default",
    mock: true,
    adapter: "native-dli",
  });

  assert.equal(result.valid, true);
  assert.equal(result.status, "MIGRATION_EXECUTE_MOCK_COMPLETE");
  assert.equal(result.mode, "MOCK");
  assert.equal(result.adapter, "native-dli");
  assert.equal(result.final_equivalence, "MOCK_EQUIVALENT");
  assert.equal(result.equivalence_confirmed, false);
  assert.equal(result.real_runtime_confirmed, false);
  assert.equal(result.mock_execution, true);
  assert.ok(result.run_id);
  assert.ok(result.native_mock_execution_result);
});

test("migration execute mock with legacy-demo unsupported", () => {
  const result = executeMigration({
    packageDir: GOLDEN_DIR,
    jobName: "test_mock_legacy",
    dliQueue: "default",
    mock: true,
    adapter: "legacy-demo",
  });

  assert.equal(result.valid, false);
  assert.equal(result.status, "UNSUPPORTED_MODE");
  assert.equal(result.mode, "MOCK");
  assert.ok(result.errors.some((e) => e.includes("native-dli")));
});

test("migration execute mock with koocli unsupported", () => {
  const result = executeMigration({
    packageDir: GOLDEN_DIR,
    jobName: "test_mock_koocli",
    dliQueue: "default",
    mock: true,
    adapter: "koocli",
  });

  assert.equal(result.valid, false);
  assert.equal(result.status, "UNSUPPORTED_MODE");
  assert.ok(result.errors.some((e) => e.includes("native-dli")));
});

test("migration execute mock result real_runtime_confirmed false", () => {
  const result = executeMigration({
    packageDir: GOLDEN_DIR,
    jobName: "test_mock_rrf",
    dliQueue: "default",
    mock: true,
    adapter: "native-dli",
  });

  assert.equal(result.valid, true);
  assert.equal(result.real_runtime_confirmed, false);
  assert.equal(result.equivalence_confirmed, false);
});

test("migration execute mock native-dli for customer_status", () => {
  const result = executeMigration({
    packageDir: CUSTOMER_GOLDEN_DIR,
    jobName: "customer_mock_native_dli",
    dliQueue: "default",
    mock: true,
    adapter: "native-dli",
  });

  assert.equal(result.valid, true);
  assert.equal(result.status, "MIGRATION_EXECUTE_MOCK_COMPLETE");
  assert.equal(result.migration_id, "customer_status_pipeline_simple");
  assert.equal(result.final_equivalence, "MOCK_EQUIVALENT");
  assert.equal(result.equivalence_confirmed, false);
  assert.equal(result.real_runtime_confirmed, false);
});
