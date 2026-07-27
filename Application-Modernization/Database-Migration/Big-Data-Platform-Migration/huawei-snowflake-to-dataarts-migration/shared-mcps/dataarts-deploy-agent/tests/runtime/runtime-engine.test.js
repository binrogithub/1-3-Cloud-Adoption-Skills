const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { buildRuntimeCommandSequence, runRuntimeEngine } = require("../../src/runtime/runtime-engine");

const GOLDEN_DIR = path.resolve(__dirname, "../../cases/golden/orders_pipeline_simple");

test("buildRuntimeCommandSequence returns 16 commands", () => {
  const seq = buildRuntimeCommandSequence({ runId: "run_test_1234", jobName: "test_job" });
  assert.equal(seq.length, 16);
});

test("command sequence includes create-job and run-immediate but marks them as not executed in dry-run", () => {
  const seq = buildRuntimeCommandSequence({ runId: "run_test_1234", jobName: "test_job" });

  const createJob = seq.find((c) => c.name === "create-job");
  assert.ok(createJob, "create-job command should exist");
  assert.equal(createJob.executed_in_dry_run, false);
  assert.equal(createJob.category, "RUNTIME_CLOUD");

  const runImmediate = seq.find((c) => c.name === "run-immediate");
  assert.ok(runImmediate, "run-immediate command should exist");
  assert.equal(runImmediate.executed_in_dry_run, false);
  assert.equal(runImmediate.category, "RUNTIME_CLOUD");
});

test("runRuntimeEngine valid golden package returns RUNTIME_ENGINE_DRY_RUN_READY", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "runtime-engine-"));
  const result = runRuntimeEngine({
    packageDir: GOLDEN_DIR,
    jobName: "test_job",
    dliQueue: "default",
    mode: "DRY_RUN",
    outDir,
  });

  assert.equal(result.valid, true);
  assert.equal(result.status, "RUNTIME_ENGINE_DRY_RUN_READY");
  assert.equal(result.mode, "DRY_RUN");
  assert.equal(result.migration_id, "orders_pipeline_simple");
  assert.equal(result.job_name, "test_job");
  assert.equal(result.dli_queue, "default");
  assert.ok(result.run_id);
  assert.ok(result.runtime_artifacts_dir);
  assert.ok(result.runtime_nodes_dir);
  assert.equal(result.command_sequence.length, 16);
  assert.equal(result.errors.length, 0);
});

test("runRuntimeEngine requires packageDir", () => {
  const result = runRuntimeEngine({
    jobName: "test_job",
    mode: "DRY_RUN",
  });

  assert.equal(result.valid, false);
  assert.equal(result.status, "INVALID_INPUT");
  assert.ok(result.errors.some((e) => e.includes("packageDir is required")));
});

test("runRuntimeEngine requires jobName", () => {
  const result = runRuntimeEngine({
    packageDir: GOLDEN_DIR,
    mode: "DRY_RUN",
  });

  assert.equal(result.valid, false);
  assert.equal(result.status, "INVALID_INPUT");
  assert.ok(result.errors.some((e) => e.includes("jobName is required")));
});

test("runRuntimeEngine rejects unsupported mode", () => {
  const result = runRuntimeEngine({
    packageDir: GOLDEN_DIR,
    jobName: "test_job",
    mode: "LIVE",
  });

  assert.equal(result.valid, false);
  assert.equal(result.status, "UNSUPPORTED_MODE");
  assert.ok(result.errors.some((e) => e.includes("Unsupported mode")));
});

test("dry-run writes result/report/current_run evidence", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "runtime-engine-evidence-"));
  const result = runRuntimeEngine({
    packageDir: GOLDEN_DIR,
    jobName: "test_job",
    dliQueue: "default",
    mode: "DRY_RUN",
    outDir,
  });

  assert.equal(result.valid, true);

  assert.ok(
    fs.existsSync(path.join(outDir, "runtime_engine_dry_run_result.json")),
    "runtime_engine_dry_run_result.json should exist"
  );
  assert.ok(
    fs.existsSync(path.join(outDir, "runtime_engine_dry_run_report.md")),
    "runtime_engine_dry_run_report.md should exist"
  );

  const runDir = path.join(outDir, "runs", result.run_id);
  assert.ok(
    fs.existsSync(path.join(runDir, "runtime_engine_dry_run_result.json")),
    "run-specific result.json should exist"
  );
  assert.ok(
    fs.existsSync(path.join(runDir, "runtime_engine_dry_run_report.md")),
    "run-specific report.md should exist"
  );
  assert.ok(
    fs.existsSync(path.join(runDir, "current_run.json")),
    "current_run.json should exist"
  );

  const currentRun = JSON.parse(
    fs.readFileSync(path.join(runDir, "current_run.json"), "utf-8")
  );
  assert.equal(currentRun.run_id, result.run_id);
  assert.equal(currentRun.migration_id, result.migration_id);
  assert.equal(currentRun.job_name, result.job_name);
  assert.equal(currentRun.status, "DRY_RUN_READY");
  assert.equal(currentRun.current_step, 0);
  assert.equal(currentRun.current_step_name, "dry-run");
  assert.deepEqual(currentRun.completed_steps, []);
  assert.equal(currentRun.failed_step, null);
  assert.equal(currentRun.failed_step_name, null);
});

test("env_overrides contains DATAARTS_JOB_NAME, DATAARTS_ARTIFACTS_DIR, DLI_QUEUE_NAME", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "runtime-engine-env-"));
  const result = runRuntimeEngine({
    packageDir: GOLDEN_DIR,
    jobName: "test_job",
    dliQueue: "default",
    mode: "DRY_RUN",
    outDir,
  });

  assert.equal(result.valid, true);
  assert.equal(result.env_overrides.DATAARTS_JOB_NAME, "test_job");
  assert.ok(result.env_overrides.DATAARTS_ARTIFACTS_DIR);
  assert.equal(result.env_overrides.DLI_QUEUE_NAME, "default");
});

test("safety.no_commands_executed true", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "runtime-engine-safety1-"));
  const result = runRuntimeEngine({
    packageDir: GOLDEN_DIR,
    jobName: "test_job",
    mode: "DRY_RUN",
    outDir,
  });

  assert.equal(result.valid, true);
  assert.equal(result.safety.no_commands_executed, true);
});

test("safety.no_runtime_execution true", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "runtime-engine-safety2-"));
  const result = runRuntimeEngine({
    packageDir: GOLDEN_DIR,
    jobName: "test_job",
    mode: "DRY_RUN",
    outDir,
  });

  assert.equal(result.valid, true);
  assert.equal(result.safety.no_runtime_execution, true);
});

test("command sequence categories are correct", () => {
  const seq = buildRuntimeCommandSequence({ runId: "run_test_1234", jobName: "test_job" });

  const readOnlyNames = [
    "validate-env", "dry-run", "inspect-request", "audit-payload",
    "live-validate", "deploy-plan", "run-immediate-plan",
    "execution-doctor", "equivalence-summary",
  ];

  const cloudNames = [
    "reset-runtime-data", "validate-runtime-data", "create-job",
    "verify-job", "export-job-definition", "run-immediate", "runtime-validate",
  ];

  for (const cmd of seq) {
    if (readOnlyNames.includes(cmd.name)) {
      assert.equal(cmd.category, "LOCAL_READ_ONLY", `${cmd.name} should be LOCAL_READ_ONLY`);
    } else if (cloudNames.includes(cmd.name)) {
      assert.equal(cmd.category, "RUNTIME_CLOUD", `${cmd.name} should be RUNTIME_CLOUD`);
    }
  }
});

test("all commands have executed_in_dry_run false", () => {
  const seq = buildRuntimeCommandSequence({ runId: "run_test_1234", jobName: "test_job" });

  for (const cmd of seq) {
    assert.equal(cmd.executed_in_dry_run, false, `${cmd.name} should not be executed in dry-run`);
  }
});

test("safety includes dry_run and local_evidence_only", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "runtime-engine-safety3-"));
  const result = runRuntimeEngine({
    packageDir: GOLDEN_DIR,
    jobName: "test_job",
    mode: "DRY_RUN",
    outDir,
  });

  assert.equal(result.valid, true);
  assert.equal(result.safety.dry_run, true);
  assert.equal(result.safety.local_evidence_only, true);
  assert.equal(result.safety.no_api_write_calls, true);
});
