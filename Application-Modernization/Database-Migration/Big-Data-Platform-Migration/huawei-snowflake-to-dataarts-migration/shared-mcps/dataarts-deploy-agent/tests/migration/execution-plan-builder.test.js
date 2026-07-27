const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { buildExecutionPlan, buildPlannedExecutionSteps } = require("../../src/migration/execution-plan-builder");

const GOLDEN_DIR = path.resolve(__dirname, "../../cases/golden/orders_pipeline_simple");
const CUSTOMER_GOLDEN_DIR = path.resolve(__dirname, "../../cases/golden/customer_status_pipeline_simple");

test("valid golden package produces EXECUTION_PLAN_READY", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "exec-plan-"));
  const result = buildExecutionPlan({ packageDir: GOLDEN_DIR, outDir });

  assert.equal(result.valid, true);
  assert.equal(result.status, "EXECUTION_PLAN_READY");
  assert.equal(result.migration_id, "orders_pipeline_simple");
  assert.equal(result.summary.node_count, 5);
  assert.equal(result.summary.validation_check_count, 7);
  assert.equal(result.planned_execution_steps.length, 11);
  assert.ok(fs.existsSync(result.runtime_artifacts_dir));
});

test("valid golden package has correct target", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "exec-plan-"));
  const result = buildExecutionPlan({ packageDir: GOLDEN_DIR, outDir });

  assert.equal(result.valid, true);
  assert.equal(result.target.orchestrator, "DATAARTS_FACTORY");
  assert.equal(result.target.runtime, "DLI");
});

test("valid golden package execution steps have correct structure", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "exec-plan-"));
  const result = buildExecutionPlan({ packageDir: GOLDEN_DIR, outDir });

  assert.equal(result.valid, true);
  const steps = result.planned_execution_steps;

  const expectedNames = [
    "validate-package",
    "doctor-package",
    "prepare-runtime-artifacts",
    "reset-runtime-validation-data",
    "create-dataarts-job",
    "verify-dataarts-job",
    "export-job-definition",
    "run-immediate",
    "runtime-validation",
    "execution-doctor",
    "equivalence-summary",
  ];

  for (let i = 0; i < steps.length; i++) {
    assert.equal(steps[i].step_number, i + 1);
    assert.equal(steps[i].step_name, expectedNames[i]);
    assert.ok(steps[i].category);
    assert.ok(steps[i].description);
    assert.equal(typeof steps[i].execution_required, "boolean");
  }
});

test("valid golden package first 3 steps do not require execution", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "exec-plan-"));
  const result = buildExecutionPlan({ packageDir: GOLDEN_DIR, outDir });

  assert.equal(result.valid, true);
  const steps = result.planned_execution_steps;

  assert.equal(steps[0].execution_required, false);
  assert.equal(steps[1].execution_required, false);
  assert.equal(steps[2].execution_required, false);
});

test("valid golden package steps 4-11 require execution", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "exec-plan-"));
  const result = buildExecutionPlan({ packageDir: GOLDEN_DIR, outDir });

  assert.equal(result.valid, true);
  const steps = result.planned_execution_steps;

  for (let i = 3; i < 11; i++) {
    assert.equal(steps[i].execution_required, true, `step ${i + 1} should require execution`);
  }
});

test("missing packageDir returns INVALID_INPUT", () => {
  const result = buildExecutionPlan({});

  assert.equal(result.valid, false);
  assert.equal(result.status, "INVALID_INPUT");
  assert.ok(result.errors.some((e) => e.includes("packageDir is required")));
});

test("missing package directory returns INVALID_PACKAGE", () => {
  const result = buildExecutionPlan({
    packageDir: "/tmp/package-dir-does-not-exist-xyz-exec-plan",
  });

  assert.equal(result.valid, false);
  assert.equal(result.status, "INVALID_PACKAGE");
});

test("unhealthy doctor blocks execution plan", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "exec-plan-unhealthy-"));
  const targetDir = path.join(tmpDir, "target");
  const sourceDir = path.join(tmpDir, "source");
  const validationDir = path.join(tmpDir, "validation");

  fs.mkdirSync(targetDir, { recursive: true });
  fs.mkdirSync(sourceDir, { recursive: true });
  fs.mkdirSync(validationDir, { recursive: true });

  const sqlContent = "INSERT INTO t1 SELECT * FROM t2;";
  const sqlPath = path.join(targetDir, "n1.sql");
  fs.writeFileSync(sqlPath, sqlContent);

  const manifest = {
    manifest_version: "0.1",
    migration_id: "broken_test",
    target: { orchestrator: "DATAARTS_FACTORY", runtime: "DLI", node_type: "DLISQL" },
    nodes: [{ id: "n1", name: "bad", type: "WRONG_TYPE", sql_file: "n1.sql", statement_count: 1, depends_on: [] }],
    runtime_policy: { requires_runtime_validation: true, allow_full_refresh: false },
    safety: { no_publish: true, no_start: true, no_delete: true, no_update: true, no_overwrite: true },
  };

  fs.writeFileSync(path.join(targetDir, "artifact_manifest.json"), JSON.stringify(manifest, null, 2));
  fs.writeFileSync(path.join(sourceDir, "snowflake_task_graph.sql"), "SELECT 1;");
  fs.writeFileSync(path.join(validationDir, "validation_plan.json"), JSON.stringify({ migration_id: "broken_test", checks: [{ id: "c1" }] }));

  const result = buildExecutionPlan({ packageDir: tmpDir });

  assert.equal(result.valid, false);
  assert.equal(result.status, "DOCTOR_UNHEALTHY");
  assert.ok(result.errors.length > 0);
});

test("buildPlannedExecutionSteps returns 11 steps", () => {
  const steps = buildPlannedExecutionSteps();
  assert.equal(steps.length, 11);
  assert.equal(steps[0].step_name, "validate-package");
  assert.equal(steps[10].step_name, "equivalence-summary");
});

test("runtime_artifacts_dir exists for valid package", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "exec-plan-"));
  const result = buildExecutionPlan({ packageDir: GOLDEN_DIR, outDir });

  assert.equal(result.valid, true);
  assert.ok(fs.existsSync(result.runtime_artifacts_dir));
  assert.ok(fs.existsSync(result.runtime_nodes_dir));
});

test("customer status valid package produces EXECUTION_PLAN_READY", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "exec-plan-"));
  const result = buildExecutionPlan({ packageDir: CUSTOMER_GOLDEN_DIR, outDir });

  assert.equal(result.valid, true);
  assert.equal(result.status, "EXECUTION_PLAN_READY");
  assert.equal(result.migration_id, "customer_status_pipeline_simple");
  assert.equal(result.summary.node_count, 5);
  assert.equal(result.summary.validation_check_count, 8);
  assert.equal(result.planned_execution_steps.length, 11);
  assert.ok(fs.existsSync(result.runtime_artifacts_dir));
});
