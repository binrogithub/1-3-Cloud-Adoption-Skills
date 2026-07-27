const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const os = require("os");
const path = require("path");
const {
  validateMigrationPackage,
  batchValidateMigrationPackages,
  generateDryRunJobName,
} = require("../../src/migration/batch-validator");

const GOLDEN_DIR = path.resolve(__dirname, "../../cases/golden");
const ORDERS_DIR = path.join(GOLDEN_DIR, "orders_pipeline_simple");
const CUSTOMER_DIR = path.join(GOLDEN_DIR, "customer_status_pipeline_simple");

function createTempPackage(overrides = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "batch-val-pkg-"));
  fs.mkdirSync(path.join(dir, "source"), { recursive: true });
  fs.mkdirSync(path.join(dir, "target", "sql"), { recursive: true });
  fs.mkdirSync(path.join(dir, "validation"), { recursive: true });

  const sourceSql = overrides.sourceSql || "-- Migration: test_pkg\nSELECT 1;";
  fs.writeFileSync(path.join(dir, "source", "snowflake_task_graph.sql"), sourceSql, "utf-8");

  const sqlContent = overrides.nodeSql || "SELECT 1;";
  fs.writeFileSync(path.join(dir, "target", "sql", "node.sql"), sqlContent, "utf-8");

  const manifest = {
    manifest_version: "0.1",
    migration_id: overrides.migration_id || "test_pkg",
    source_type: "snowflake_task_graph",
    target: {
      orchestrator: overrides.orchestrator || "DATAARTS_FACTORY",
      runtime: overrides.runtime || "DLI",
      node_type: "DLISQL",
    },
    runtime_policy: overrides.runtime_policy || {
      single_statement_per_node: true,
      allow_full_refresh: false,
      requires_runtime_validation: true,
    },
    nodes: overrides.nodes || [
      {
        id: "node",
        name: "node",
        type: "DLISQL",
        sql_file: "sql/node.sql",
        depends_on: [],
      },
    ],
    safety: overrides.safety || {
      no_publish: true,
      no_start: true,
      no_delete: true,
      no_update: true,
      no_overwrite: true,
    },
  };
  fs.writeFileSync(path.join(dir, "target", "artifact_manifest.json"), JSON.stringify(manifest, null, 2));

  const validationPlan = {
    validation_plan_version: "0.1",
    migration_id: overrides.migration_id || "test_pkg",
    checks: overrides.checks || [{ type: "TABLE_COUNT", object_name: "T", expected: 1 }],
  };
  fs.writeFileSync(path.join(dir, "validation", "validation_plan.json"), JSON.stringify(validationPlan, null, 2));

  return dir;
}

test("batch validation detects both golden packages", () => {
  const result = batchValidateMigrationPackages({ packagesDir: GOLDEN_DIR });

  assert.equal(result.status, "BATCH_VALIDATE_COMPLETE");
  assert.equal(result.package_count, 2);

  const names = result.packages.map((p) => p.package_name);
  assert.ok(names.includes("orders_pipeline_simple"));
  assert.ok(names.includes("customer_status_pipeline_simple"));
});

test("both golden packages return BATCH_DRY_RUN_VALIDATED", () => {
  const result = batchValidateMigrationPackages({ packagesDir: GOLDEN_DIR });

  for (const pkg of result.packages) {
    assert.equal(pkg.validation_status, "BATCH_DRY_RUN_VALIDATED");
    assert.equal(pkg.valid, true);
  }
});

test("summary.dry_run_validated = 2", () => {
  const result = batchValidateMigrationPackages({ packagesDir: GOLDEN_DIR });

  assert.equal(result.summary.dry_run_validated, 2);
  assert.equal(result.summary.invalid, 0);
  assert.equal(result.summary.blocked, 0);
  assert.equal(result.summary.failed, 0);
});

test("full-refresh warnings are preserved but non-fatal", () => {
  const result = batchValidateMigrationPackages({ packagesDir: GOLDEN_DIR });

  const hasFullRefreshWarning = result.packages.some((p) =>
    p.warnings.some((w) => w.toLowerCase().includes("full-refresh") || w.toLowerCase().includes("full refresh"))
  );

  assert.ok(hasFullRefreshWarning, "at least one package should have a full-refresh warning");

  for (const pkg of result.packages) {
    assert.equal(pkg.valid, true, "warnings should not invalidate packages");
  }
});

test("MERGE+DLI warning is preserved but non-fatal", () => {
  const ordersResult = validateMigrationPackage({
    packageDir: ORDERS_DIR,
    adapter: "legacy-demo",
    dliQueue: "default",
  });

  const hasMergeDliWarning = ordersResult.warnings.some(
    (w) => w.includes("MERGE") && w.includes("DLI")
  );

  assert.ok(hasMergeDliWarning, "orders package should have a MERGE+DLI warning");
  assert.equal(ordersResult.valid, true, "MERGE+DLI warning should not invalidate the package");
  assert.equal(ordersResult.validation_status, "BATCH_DRY_RUN_VALIDATED");
});

test("invalid package returns INVALID_PACKAGE", () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "batch-val-invalid-"));
  fs.mkdirSync(path.join(tempDir, "source"), { recursive: true });

  const result = validateMigrationPackage({ packageDir: tempDir });

  assert.equal(result.validation_status, "INVALID_PACKAGE");
  assert.equal(result.valid, false);
});

test("doctor findings block package", () => {
  const tempDir = createTempPackage({
    runtime_policy: {
      single_statement_per_node: true,
      allow_full_refresh: false,
      requires_runtime_validation: false,
    },
  });

  const result = validateMigrationPackage({ packageDir: tempDir });

  assert.equal(result.validation_status, "DOCTOR_UNHEALTHY");
  assert.equal(result.valid, false);
  assert.ok(result.findings.length > 0, "should have doctor findings");
  assert.equal(result.stages.doctor.healthy, false);
});

test("missing packagesDir returns INVALID_INPUT", () => {
  const result = batchValidateMigrationPackages({ packagesDir: undefined });

  assert.equal(result.status, "INVALID_INPUT");
  assert.equal(result.valid, false);
  assert.equal(result.package_count, 0);
});

test("empty packagesDir returns NO_PACKAGES_FOUND", () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "batch-val-empty-"));

  const result = batchValidateMigrationPackages({ packagesDir: tempDir });

  assert.equal(result.status, "NO_PACKAGES_FOUND");
  assert.equal(result.package_count, 0);
});

test("safety flags are present", () => {
  const result = batchValidateMigrationPackages({ packagesDir: GOLDEN_DIR });

  assert.equal(result.safety.batch_validation_only, true);
  assert.equal(result.safety.dry_run_only, true);
  assert.equal(result.safety.no_cloud_api_calls, true);
  assert.equal(result.safety.no_runtime_execution, true);
  assert.equal(result.safety.no_sql_execution, true);
  assert.equal(result.safety.no_confirm, true);
});

test("dry-run job names are deterministic and safe", () => {
  const result = batchValidateMigrationPackages({ packagesDir: GOLDEN_DIR });

  for (const pkg of result.packages) {
    const expectedJobName = generateDryRunJobName(pkg.migration_id);
    assert.ok(
      expectedJobName.startsWith("batch_validate_"),
      `job name should start with batch_validate_: ${expectedJobName}`
    );
    assert.ok(
      !/[^\w-]/.test(expectedJobName),
      `job name should be safe (alphanumeric + underscore + hyphen only): ${expectedJobName}`
    );
  }

  assert.equal(generateDryRunJobName("orders_pipeline_simple"), "batch_validate_orders_pipeline_simple");
  assert.equal(generateDryRunJobName("test pkg!@#"), "batch_validate_test_pkg");
  assert.equal(generateDryRunJobName(null), "batch_validate_unknown");
});

test("per-package shape has all required fields", () => {
  const result = batchValidateMigrationPackages({ packagesDir: GOLDEN_DIR });

  for (const pkg of result.packages) {
    assert.ok(typeof pkg.package_name === "string");
    assert.ok(typeof pkg.migration_id === "string" || pkg.migration_id === null);
    assert.ok(typeof pkg.package_dir === "string");
    assert.ok(typeof pkg.valid === "boolean");
    assert.ok(typeof pkg.validation_status === "string");
    assert.ok(typeof pkg.target_runtime === "string" || pkg.target_runtime === null);
    assert.ok(typeof pkg.node_count === "number");
    assert.ok(typeof pkg.validation_check_count === "number");
    assert.ok(Array.isArray(pkg.warnings));
    assert.ok(Array.isArray(pkg.findings));
    assert.ok(Array.isArray(pkg.errors));

    assert.ok(typeof pkg.stages.package_load === "object");
    assert.ok(typeof pkg.stages.plan === "object");
    assert.ok(typeof pkg.stages.doctor === "object");
    assert.ok(typeof pkg.stages.prepare_runtime === "object");
    assert.ok(typeof pkg.stages.execute_plan === "object");
    assert.ok(typeof pkg.stages.execute_dry_run === "object");

    assert.ok(typeof pkg.stages.package_load.status === "string");
    assert.ok(typeof pkg.stages.package_load.valid === "boolean");
    assert.ok(typeof pkg.stages.plan.status === "string");
    assert.ok(typeof pkg.stages.plan.valid === "boolean");
    assert.ok(typeof pkg.stages.doctor.status === "string");
    assert.ok(typeof pkg.stages.doctor.healthy === "boolean");
    assert.ok(typeof pkg.stages.doctor.findings_count === "number");
    assert.ok(typeof pkg.stages.doctor.warnings_count === "number");
    assert.ok(typeof pkg.stages.prepare_runtime.status === "string");
    assert.ok(typeof pkg.stages.prepare_runtime.valid === "boolean");
    assert.ok(typeof pkg.stages.execute_plan.status === "string");
    assert.ok(typeof pkg.stages.execute_plan.valid === "boolean");
    assert.ok(typeof pkg.stages.execute_plan.steps === "number");
    assert.ok(typeof pkg.stages.execute_dry_run.status === "string");
    assert.ok(typeof pkg.stages.execute_dry_run.valid === "boolean");
    assert.ok(typeof pkg.stages.execute_dry_run.adapter === "string");
  }
});

test("all stages pass for golden packages", () => {
  const result = batchValidateMigrationPackages({ packagesDir: GOLDEN_DIR });

  for (const pkg of result.packages) {
    assert.equal(pkg.stages.package_load.valid, true);
    assert.equal(pkg.stages.plan.valid, true);
    assert.equal(pkg.stages.doctor.healthy, true);
    assert.equal(pkg.stages.prepare_runtime.valid, true);
    assert.equal(pkg.stages.execute_plan.valid, true);
    assert.equal(pkg.stages.execute_dry_run.valid, true);
    assert.ok(pkg.stages.execute_plan.steps > 0, "should have planned execution steps");
    assert.ok(pkg.stages.execute_dry_run.planned_command, "should have a planned command");
  }
});

test("adapter and dli_queue are propagated", () => {
  const result = batchValidateMigrationPackages({
    packagesDir: GOLDEN_DIR,
    adapter: "legacy-demo",
    dliQueue: "default",
  });

  assert.equal(result.adapter, "legacy-demo");
  assert.equal(result.dli_queue, "default");

  for (const pkg of result.packages) {
    assert.equal(pkg.stages.execute_dry_run.adapter, "legacy-demo");
  }
});

test("batch validate with nonexistent packagesDir returns INVALID_INPUT", () => {
  const result = batchValidateMigrationPackages({
    packagesDir: "/tmp/does-not-exist-batch-validate-xyz",
  });

  assert.equal(result.status, "INVALID_INPUT");
  assert.equal(result.valid, false);
});
