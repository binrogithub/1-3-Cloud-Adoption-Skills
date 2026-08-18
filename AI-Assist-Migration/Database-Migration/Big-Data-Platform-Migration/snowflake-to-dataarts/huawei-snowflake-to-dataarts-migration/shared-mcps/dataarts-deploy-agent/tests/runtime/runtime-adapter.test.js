const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { resolveRuntimeAdapter, executeWithRuntimeAdapter } = require("../../src/runtime/adapters/runtime-adapter");
const { runKooCliDoctor } = require("../../src/koocli/koocli-doctor");

const GOLDEN_DIR = path.resolve(__dirname, "../../cases/golden/orders_pipeline_simple");

test("default adapter resolves to runtime-engine", () => {
  const resolved = resolveRuntimeAdapter({});
  assert.equal(resolved.valid, true);
  assert.equal(resolved.adapter, "runtime-engine");
});

test("runtime-engine adapter dry-run returns RUNTIME_ADAPTER_DRY_RUN_READY", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "rt-adapter-"));
  const result = executeWithRuntimeAdapter({
    adapter: "runtime-engine",
    packageDir: GOLDEN_DIR,
    jobName: "test_adapter",
    dliQueue: "default",
    mode: "DRY_RUN",
    outDir,
  });

  assert.equal(result.valid, true);
  assert.equal(result.status, "RUNTIME_ADAPTER_DRY_RUN_READY");
  assert.equal(result.adapter, "runtime-engine");
  assert.equal(result.mode, "DRY_RUN");
  assert.ok(result.run_id);
  assert.equal(result.migration_id, "orders_pipeline_simple");
});

test("runtime-engine adapter returns 16 command sequence entries", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "rt-adapter-cmds-"));
  const result = executeWithRuntimeAdapter({
    adapter: "runtime-engine",
    packageDir: GOLDEN_DIR,
    jobName: "test_adapter",
    dliQueue: "default",
    mode: "DRY_RUN",
    outDir,
  });

  assert.equal(result.valid, true);
  assert.equal(result.command_sequence.length, 16);
});

test("legacy-demo adapter dry-run returns LEGACY_DEMO_ADAPTER_DRY_RUN_READY", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "rt-adapter-legacy-"));
  const result = executeWithRuntimeAdapter({
    adapter: "legacy-demo",
    packageDir: GOLDEN_DIR,
    jobName: "test_adapter_legacy",
    dliQueue: "default",
    mode: "DRY_RUN",
    outDir,
  });

  assert.equal(result.valid, true);
  assert.equal(result.status, "LEGACY_DEMO_ADAPTER_DRY_RUN_READY");
  assert.equal(result.adapter, "legacy-demo");
  assert.equal(result.mode, "DRY_RUN");
  assert.ok(result.run_id);
  assert.equal(result.migration_id, "orders_pipeline_simple");
});

test("legacy-demo adapter includes planned_legacy_command", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "rt-adapter-legacy-cmd-"));
  const result = executeWithRuntimeAdapter({
    adapter: "legacy-demo",
    packageDir: GOLDEN_DIR,
    jobName: "test_adapter_legacy",
    dliQueue: "default",
    mode: "DRY_RUN",
    outDir,
  });

  assert.equal(result.valid, true);
  assert.ok(result.planned_legacy_command);
  assert.ok(result.planned_legacy_command.includes("npm run demo:one-shot"));
  assert.ok(result.planned_legacy_command.includes("--confirm"));
  assert.ok(result.planned_legacy_command.includes("--job-name test_adapter_legacy"));
  assert.ok(result.planned_legacy_command.includes("--dli-queue default"));
});

test("legacy-demo normalized_result marks executed false and dry_run_only true", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "rt-adapter-legacy-norm-"));
  const result = executeWithRuntimeAdapter({
    adapter: "legacy-demo",
    packageDir: GOLDEN_DIR,
    jobName: "test_adapter_legacy",
    dliQueue: "default",
    mode: "DRY_RUN",
    outDir,
  });

  assert.equal(result.valid, true);
  assert.equal(result.normalized_result.executed, false);
  assert.equal(result.normalized_result.dry_run_only, true);
});

test("unsupported adapter returns UNSUPPORTED_ADAPTER", () => {
  const result = executeWithRuntimeAdapter({
    adapter: "nonexistent",
    packageDir: GOLDEN_DIR,
    jobName: "test_adapter",
    dliQueue: "default",
    mode: "DRY_RUN",
  });

  assert.equal(result.valid, false);
  assert.equal(result.status, "UNSUPPORTED_ADAPTER");
  assert.equal(result.adapter, "nonexistent");
});

test("unsupported mode returns UNSUPPORTED_MODE", () => {
  const result = executeWithRuntimeAdapter({
    adapter: "runtime-engine",
    packageDir: GOLDEN_DIR,
    jobName: "test_adapter",
    dliQueue: "default",
    mode: "LIVE",
  });

  assert.equal(result.valid, false);
  assert.equal(result.status, "UNSUPPORTED_MODE");
});

test("safety.no_commands_executed true", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "rt-adapter-safety1-"));
  const result = executeWithRuntimeAdapter({
    adapter: "runtime-engine",
    packageDir: GOLDEN_DIR,
    jobName: "test_adapter",
    dliQueue: "default",
    mode: "DRY_RUN",
    outDir,
  });

  assert.equal(result.valid, true);
  assert.equal(result.safety.no_commands_executed, true);
});

test("safety.no_runtime_execution true", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "rt-adapter-safety2-"));
  const result = executeWithRuntimeAdapter({
    adapter: "runtime-engine",
    packageDir: GOLDEN_DIR,
    jobName: "test_adapter",
    dliQueue: "default",
    mode: "DRY_RUN",
    outDir,
  });

  assert.equal(result.valid, true);
  assert.equal(result.safety.no_runtime_execution, true);
});

test("safety.adapter_layer true", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "rt-adapter-safety3-"));
  const result = executeWithRuntimeAdapter({
    adapter: "runtime-engine",
    packageDir: GOLDEN_DIR,
    jobName: "test_adapter",
    dliQueue: "default",
    mode: "DRY_RUN",
    outDir,
  });

  assert.equal(result.valid, true);
  assert.equal(result.safety.adapter_layer, true);
});

test("default adapter (no adapter specified) uses runtime-engine", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "rt-adapter-default-"));
  const result = executeWithRuntimeAdapter({
    packageDir: GOLDEN_DIR,
    jobName: "test_adapter_default",
    dliQueue: "default",
    mode: "DRY_RUN",
    outDir,
  });

  assert.equal(result.valid, true);
  assert.equal(result.adapter, "runtime-engine");
  assert.equal(result.status, "RUNTIME_ADAPTER_DRY_RUN_READY");
});

test("koocli adapter dry-run returns KOOCLI_ADAPTER_DRY_RUN_READY or KOOCLI_ADAPTER_UNAVAILABLE", () => {
  const result = executeWithRuntimeAdapter({
    adapter: "koocli",
    packageDir: GOLDEN_DIR,
    jobName: "test_koocli_adapter",
    dliQueue: "default",
    mode: "DRY_RUN",
  });

  assert.equal(result.adapter, "koocli");
  assert.equal(result.mode, "DRY_RUN");
  assert.ok(
    result.status === "KOOCLI_ADAPTER_DRY_RUN_READY" ||
    result.status === "KOOCLI_ADAPTER_UNAVAILABLE"
  );

  if (result.status === "KOOCLI_ADAPTER_DRY_RUN_READY") {
    assert.equal(result.valid, true);
    assert.ok(result.koocli_diagnostics);
    assert.ok(result.future_command_plan);
  } else {
    assert.equal(result.valid, false);
  }
});

test("koocli adapter uses DRY_RUN only", () => {
  const result = executeWithRuntimeAdapter({
    adapter: "koocli",
    packageDir: GOLDEN_DIR,
    jobName: "test_koocli_adapter",
    dliQueue: "default",
    mode: "DRY_RUN",
  });

  assert.equal(result.mode, "DRY_RUN");
  assert.equal(result.safety.no_runtime_execution, true);
});

test("koocli adapter unsupported non-dry-run mode rejected", () => {
  const result = executeWithRuntimeAdapter({
    adapter: "koocli",
    packageDir: GOLDEN_DIR,
    jobName: "test_koocli_adapter",
    dliQueue: "default",
    mode: "LIVE",
  });

  assert.equal(result.valid, false);
  assert.equal(result.status, "UNSUPPORTED_MODE");
});

test("koocli adapter safety flags present", () => {
  const result = executeWithRuntimeAdapter({
    adapter: "koocli",
    packageDir: GOLDEN_DIR,
    jobName: "test_koocli_adapter",
    dliQueue: "default",
    mode: "DRY_RUN",
  });

  assert.equal(result.safety.adapter_layer, true);
  assert.equal(result.safety.no_commands_executed, true);
  assert.equal(result.safety.no_api_write_calls, true);
  assert.equal(result.safety.no_runtime_execution, true);
});

test("legacy-demo confirm uses injected commandRunner and does not execute real command", () => {
  let capturedCmd = null;
  let capturedEnv = null;
  const mockRunner = (cmdSpec, opts) => {
    capturedCmd = cmdSpec;
    capturedEnv = opts.env;
    return { exit_code: 0, success: true, outputTail: "", lastLines: [] };
  };

  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "rt-adapter-confirm-"));
  const result = executeWithRuntimeAdapter({
    adapter: "legacy-demo",
    packageDir: GOLDEN_DIR,
    jobName: "test_confirm_injected",
    dliQueue: "default",
    mode: "CONFIRM",
    outDir,
    commandRunner: mockRunner,
  });

  assert.equal(result.valid, true);
  assert.equal(result.status, "LEGACY_DEMO_EXECUTION_COMPLETE");
  assert.ok(capturedCmd);
  assert.ok(capturedCmd.cmd.includes("npm run demo:one-shot"));
  assert.ok(capturedEnv);
  assert.equal(capturedEnv.DATAARTS_JOB_NAME, "test_confirm_injected");
  assert.equal(capturedEnv.DLI_QUEUE_NAME, "default");
});

test("legacy-demo confirm builds correct npm run demo:one-shot command", () => {
  let capturedCmd = null;
  const mockRunner = (cmdSpec) => {
    capturedCmd = cmdSpec;
    return { exit_code: 0, success: true, outputTail: "", lastLines: [] };
  };

  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "rt-adapter-confirm-cmd-"));
  const result = executeWithRuntimeAdapter({
    adapter: "legacy-demo",
    packageDir: GOLDEN_DIR,
    jobName: "test_confirm_cmd",
    dliQueue: "default",
    mode: "CONFIRM",
    outDir,
    commandRunner: mockRunner,
  });

  assert.equal(result.valid, true);
  assert.ok(capturedCmd.cmd.includes("npm run demo:one-shot -- --confirm"));
  assert.ok(capturedCmd.cmd.includes("--job-name test_confirm_cmd"));
  assert.ok(capturedCmd.cmd.includes("--dli-queue default"));
  assert.ok(capturedCmd.cmd.includes("--artifacts-dir"));
});

test("legacy-demo confirm passes env overrides", () => {
  let capturedEnv = null;
  const mockRunner = (cmdSpec, opts) => {
    capturedEnv = opts.env;
    return { exit_code: 0, success: true, outputTail: "", lastLines: [] };
  };

  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "rt-adapter-confirm-env-"));
  executeWithRuntimeAdapter({
    adapter: "legacy-demo",
    packageDir: GOLDEN_DIR,
    jobName: "test_confirm_env",
    dliQueue: "custom_queue",
    mode: "CONFIRM",
    outDir,
    commandRunner: mockRunner,
  });

  assert.equal(capturedEnv.DATAARTS_JOB_NAME, "test_confirm_env");
  assert.equal(capturedEnv.DLI_QUEUE_NAME, "custom_queue");
  assert.ok(capturedEnv.DATAARTS_ARTIFACTS_DIR);
});

test("legacy-demo confirm returns LEGACY_DEMO_EXECUTION_COMPLETE on mocked success", () => {
  const mockRunner = () => ({ exit_code: 0, success: true, outputTail: "", lastLines: [] });

  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "rt-adapter-confirm-ok-"));
  const result = executeWithRuntimeAdapter({
    adapter: "legacy-demo",
    packageDir: GOLDEN_DIR,
    jobName: "test_confirm_success",
    dliQueue: "default",
    mode: "CONFIRM",
    outDir,
    commandRunner: mockRunner,
  });

  assert.equal(result.valid, true);
  assert.equal(result.status, "LEGACY_DEMO_EXECUTION_COMPLETE");
  assert.equal(result.adapter, "legacy-demo");
  assert.equal(result.mode, "CONFIRM");
  assert.equal(result.executed, true);
  assert.equal(result.exit_code, 0);
  assert.ok(result.run_id);
  assert.ok(result.command);
  assert.ok(result.safety.confirm_required);
  assert.ok(result.safety.only_run_immediate_for_execution);
});

test("legacy-demo confirm returns LEGACY_DEMO_EXECUTION_FAILED on mocked failure", () => {
  const mockRunner = () => ({ exit_code: 1, success: false, outputTail: "error", lastLines: ["error"] });

  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "rt-adapter-confirm-fail-"));
  const result = executeWithRuntimeAdapter({
    adapter: "legacy-demo",
    packageDir: GOLDEN_DIR,
    jobName: "test_confirm_fail",
    dliQueue: "default",
    mode: "CONFIRM",
    outDir,
    commandRunner: mockRunner,
  });

  assert.equal(result.valid, false);
  assert.equal(result.status, "LEGACY_DEMO_EXECUTION_FAILED");
  assert.equal(result.adapter, "legacy-demo");
  assert.equal(result.mode, "CONFIRM");
  assert.equal(result.executed, true);
  assert.equal(result.exit_code, 1);
  assert.ok(result.errors.some((e) => e.includes("exited with code")));
});

test("runtime-engine confirm returns UNSUPPORTED_MODE", () => {
  const result = executeWithRuntimeAdapter({
    adapter: "runtime-engine",
    packageDir: GOLDEN_DIR,
    jobName: "test_confirm_re",
    dliQueue: "default",
    mode: "CONFIRM",
  });

  assert.equal(result.valid, false);
  assert.equal(result.status, "UNSUPPORTED_MODE");
  assert.ok(result.errors.some((e) => e.includes("legacy-demo")));
});

test("koocli confirm returns UNSUPPORTED_MODE", () => {
  const result = executeWithRuntimeAdapter({
    adapter: "koocli",
    packageDir: GOLDEN_DIR,
    jobName: "test_confirm_koocli",
    dliQueue: "default",
    mode: "CONFIRM",
  });

  assert.equal(result.valid, false);
  assert.equal(result.status, "UNSUPPORTED_MODE");
  assert.ok(result.errors.some((e) => e.includes("legacy-demo")));
});

test("native-dli adapter dry-run returns NATIVE_DLI_ADAPTER_DRY_RUN_READY", () => {
  const result = executeWithRuntimeAdapter({
    adapter: "native-dli",
    packageDir: GOLDEN_DIR,
    jobName: "test_native_dli",
    dliQueue: "default",
    mode: "DRY_RUN",
  });

  assert.equal(result.valid, true);
  assert.equal(result.status, "NATIVE_DLI_ADAPTER_DRY_RUN_READY");
  assert.equal(result.adapter, "native-dli");
  assert.equal(result.mode, "DRY_RUN");
  assert.equal(result.migration_id, "orders_pipeline_simple");
  assert.ok(result.native_runtime_plan);
});

test("native-dli adapter command_sequence length equals native plan total steps", () => {
  const result = executeWithRuntimeAdapter({
    adapter: "native-dli",
    packageDir: GOLDEN_DIR,
    jobName: "test_native_dli_cmds",
    dliQueue: "default",
    mode: "DRY_RUN",
  });

  assert.equal(result.valid, true);
  assert.equal(result.command_sequence.length, result.native_runtime_plan.summary.total_steps);
  assert.equal(result.command_sequence.length, 16);
});

test("native-dli confirm returns UNSUPPORTED_MODE", () => {
  const result = executeWithRuntimeAdapter({
    adapter: "native-dli",
    packageDir: GOLDEN_DIR,
    jobName: "test_confirm_native_dli",
    dliQueue: "default",
    mode: "CONFIRM",
  });

  assert.equal(result.valid, false);
  assert.equal(result.status, "UNSUPPORTED_MODE");
  assert.ok(result.errors.some((e) => e.includes("legacy-demo")));
});

test("native-dli adapter safety flags present", () => {
  const result = executeWithRuntimeAdapter({
    adapter: "native-dli",
    packageDir: GOLDEN_DIR,
    jobName: "test_native_dli_safety",
    dliQueue: "default",
    mode: "DRY_RUN",
  });

  assert.equal(result.valid, true);
  assert.equal(result.safety.adapter_layer, true);
  assert.equal(result.safety.no_commands_executed, true);
  assert.equal(result.safety.no_runtime_execution, true);
});

test("native-dli simulate mode succeeds", () => {
  const result = executeWithRuntimeAdapter({
    adapter: "native-dli",
    packageDir: GOLDEN_DIR,
    jobName: "test_native_dli_simulate",
    dliQueue: "default",
    mode: "SIMULATE",
  });

  assert.equal(result.valid, true);
  assert.equal(result.status, "NATIVE_DLI_ADAPTER_SIMULATION_COMPLETE");
  assert.equal(result.adapter, "native-dli");
  assert.equal(result.mode, "SIMULATE");
  assert.equal(result.simulation_only, true);
  assert.ok(result.run_id);
  assert.ok(result.native_simulation_result);
});

test("native-dli simulate returns SIMULATED_EQUIVALENT", () => {
  const result = executeWithRuntimeAdapter({
    adapter: "native-dli",
    packageDir: GOLDEN_DIR,
    jobName: "test_native_dli_sim_eq",
    dliQueue: "default",
    mode: "SIMULATE",
  });

  assert.equal(result.valid, true);
  assert.equal(result.final_equivalence, "SIMULATED_EQUIVALENT");
  assert.equal(result.equivalence_confirmed, false);
});

test("native-dli simulate with legacy-demo returns UNSUPPORTED_MODE", () => {
  const result = executeWithRuntimeAdapter({
    adapter: "legacy-demo",
    packageDir: GOLDEN_DIR,
    jobName: "test_simulate_legacy",
    dliQueue: "default",
    mode: "SIMULATE",
  });

  assert.equal(result.valid, false);
  assert.equal(result.status, "UNSUPPORTED_MODE");
  assert.ok(result.errors.some((e) => e.includes("native-dli")));
});

test("native-dli simulate with koocli returns UNSUPPORTED_MODE", () => {
  const result = executeWithRuntimeAdapter({
    adapter: "koocli",
    packageDir: GOLDEN_DIR,
    jobName: "test_simulate_koocli",
    dliQueue: "default",
    mode: "SIMULATE",
  });

  assert.equal(result.valid, false);
  assert.equal(result.status, "UNSUPPORTED_MODE");
  assert.ok(result.errors.some((e) => e.includes("native-dli")));
});

test("native-dli simulate with runtime-engine returns UNSUPPORTED_MODE", () => {
  const result = executeWithRuntimeAdapter({
    adapter: "runtime-engine",
    packageDir: GOLDEN_DIR,
    jobName: "test_simulate_re",
    dliQueue: "default",
    mode: "SIMULATE",
  });

  assert.equal(result.valid, false);
  assert.equal(result.status, "UNSUPPORTED_MODE");
  assert.ok(result.errors.some((e) => e.includes("native-dli")));
});

test("native-dli MOCK mode succeeds", () => {
  const result = executeWithRuntimeAdapter({
    adapter: "native-dli",
    packageDir: GOLDEN_DIR,
    jobName: "test_native_dli_mock",
    dliQueue: "default",
    mode: "MOCK",
  });

  assert.equal(result.valid, true);
  assert.equal(result.status, "NATIVE_DLI_ADAPTER_MOCK_EXECUTION_COMPLETE");
  assert.equal(result.adapter, "native-dli");
  assert.equal(result.mode, "MOCK");
  assert.ok(result.run_id);
  assert.ok(result.native_mock_execution_result);
});

test("native-dli MOCK mode returns MOCK_EQUIVALENT", () => {
  const result = executeWithRuntimeAdapter({
    adapter: "native-dli",
    packageDir: GOLDEN_DIR,
    jobName: "test_native_dli_mock_eq",
    dliQueue: "default",
    mode: "MOCK",
  });

  assert.equal(result.valid, true);
  assert.equal(result.final_equivalence, "MOCK_EQUIVALENT");
  assert.equal(result.equivalence_confirmed, false);
  assert.equal(result.real_runtime_confirmed, false);
});

test("native-dli MOCK with legacy-demo returns UNSUPPORTED_MODE", () => {
  const result = executeWithRuntimeAdapter({
    adapter: "legacy-demo",
    packageDir: GOLDEN_DIR,
    jobName: "test_mock_legacy",
    dliQueue: "default",
    mode: "MOCK",
  });

  assert.equal(result.valid, false);
  assert.equal(result.status, "UNSUPPORTED_MODE");
  assert.ok(result.errors.some((e) => e.includes("native-dli")));
});

test("native-dli MOCK with koocli returns UNSUPPORTED_MODE", () => {
  const result = executeWithRuntimeAdapter({
    adapter: "koocli",
    packageDir: GOLDEN_DIR,
    jobName: "test_mock_koocli",
    dliQueue: "default",
    mode: "MOCK",
  });

  assert.equal(result.valid, false);
  assert.equal(result.status, "UNSUPPORTED_MODE");
  assert.ok(result.errors.some((e) => e.includes("native-dli")));
});

test("native-dli CONFIRM remains unsupported", () => {
  const result = executeWithRuntimeAdapter({
    adapter: "native-dli",
    packageDir: GOLDEN_DIR,
    jobName: "test_confirm_native_dli_mock",
    dliQueue: "default",
    mode: "CONFIRM",
  });

  assert.equal(result.valid, false);
  assert.equal(result.status, "UNSUPPORTED_MODE");
});
