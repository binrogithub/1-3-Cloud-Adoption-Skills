const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { discoverMigrationPackages, assessMigrationPackage, batchAssessMigrationPackages } = require("../../src/migration/batch-assessor");

const GOLDEN_DIR = path.resolve(__dirname, "../../cases/golden");
const ORDERS_DIR = path.join(GOLDEN_DIR, "orders_pipeline_simple");
const CUSTOMER_DIR = path.join(GOLDEN_DIR, "customer_status_pipeline_simple");

function createTempPackage(overrides = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "batch-pkg-"));
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

test("discoverMigrationPackages finds both golden packages", () => {
  const result = discoverMigrationPackages({ packagesDir: GOLDEN_DIR });

  assert.equal(result.errors.length, 0);
  assert.equal(result.packages.length, 2);

  const names = result.packages.map((p) => p.name);
  assert.ok(names.includes("orders_pipeline_simple"));
  assert.ok(names.includes("customer_status_pipeline_simple"));
});

test("discoverMigrationPackages returns sorted by name", () => {
  const result = discoverMigrationPackages({ packagesDir: GOLDEN_DIR });

  assert.equal(result.packages[0].name, "customer_status_pipeline_simple");
  assert.equal(result.packages[1].name, "orders_pipeline_simple");
});

test("batch assessment returns package_count 2", () => {
  const result = batchAssessMigrationPackages({ packagesDir: GOLDEN_DIR });

  assert.equal(result.status, "BATCH_ASSESS_COMPLETE");
  assert.equal(result.package_count, 2);
});

test("orders_pipeline_simple classified as RUNTIME_CONFIRMED", () => {
  const result = assessMigrationPackage({ packageDir: ORDERS_DIR });

  assert.equal(result.valid, true);
  assert.equal(result.readiness_status, "RUNTIME_CONFIRMED");
  assert.equal(result.equivalence_confirmed, true);
  assert.equal(result.expected_equivalence_status, "EQUIVALENT");
});

test("customer_status_pipeline_simple classified as DRY_RUN_VALIDATED", () => {
  const result = assessMigrationPackage({ packageDir: CUSTOMER_DIR });

  assert.equal(result.valid, true);
  assert.notEqual(result.readiness_status, "RUNTIME_CONFIRMED");
  assert.equal(result.readiness_status, "DRY_RUN_VALIDATED");
  assert.equal(result.equivalence_confirmed, false);
  assert.equal(result.expected_equivalence_status, "NOT_EXECUTED");
});

test("doctor warnings are counted but not fatal", () => {
  const ordersResult = assessMigrationPackage({ packageDir: ORDERS_DIR });
  const customerResult = assessMigrationPackage({ packageDir: CUSTOMER_DIR });

  assert.ok(ordersResult.warnings_count > 0, "orders should have warnings (MERGE+DLI, full-refresh)");
  assert.equal(ordersResult.doctor_healthy, true);
  assert.equal(ordersResult.readiness_status, "RUNTIME_CONFIRMED");

  assert.ok(customerResult.warnings_count > 0, "customer should have warnings (full-refresh)");
  assert.equal(customerResult.doctor_healthy, true);
});

test("invalid packages are classified INVALID_PACKAGE", () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "batch-invalid-"));
  fs.mkdirSync(path.join(tempDir, "source"), { recursive: true });

  const result = assessMigrationPackage({ packageDir: tempDir });

  assert.equal(result.readiness_status, "INVALID_PACKAGE");
  assert.equal(result.valid, false);
});

test("missing packagesDir returns INVALID_INPUT", () => {
  const result = batchAssessMigrationPackages({ packagesDir: undefined });

  assert.equal(result.status, "INVALID_INPUT");
  assert.equal(result.valid, false);
  assert.equal(result.package_count, 0);
});

test("empty packagesDir returns NO_PACKAGES_FOUND", () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "batch-empty-"));

  const result = batchAssessMigrationPackages({ packagesDir: tempDir });

  assert.equal(result.status, "NO_PACKAGES_FOUND");
  assert.equal(result.package_count, 0);
});

test("safety flags are present", () => {
  const result = batchAssessMigrationPackages({ packagesDir: GOLDEN_DIR });

  assert.equal(result.safety.batch_assessment_only, true);
  assert.equal(result.safety.no_cloud_api_calls, true);
  assert.equal(result.safety.no_runtime_execution, true);
  assert.equal(result.safety.no_sql_execution, true);
});

test("batch summary counts are correct", () => {
  const result = batchAssessMigrationPackages({ packagesDir: GOLDEN_DIR });

  assert.equal(result.summary.runtime_confirmed, 1);
  assert.equal(result.summary.dry_run_validated, 1);
  assert.equal(result.summary.blocked, 0);
  assert.equal(result.summary.invalid, 0);
});

test("per-package shape has all required fields", () => {
  const result = batchAssessMigrationPackages({ packagesDir: GOLDEN_DIR });

  for (const pkg of result.packages) {
    assert.ok(typeof pkg.package_name === "string");
    assert.ok(typeof pkg.package_dir === "string");
    assert.ok(typeof pkg.migration_id === "string" || pkg.migration_id === null);
    assert.ok(typeof pkg.valid === "boolean");
    assert.ok(typeof pkg.readiness_status === "string");
    assert.ok(typeof pkg.plan_status === "string");
    assert.ok(typeof pkg.doctor_status === "string");
    assert.ok(typeof pkg.doctor_healthy === "boolean");
    assert.ok(typeof pkg.findings_count === "number");
    assert.ok(typeof pkg.warnings_count === "number");
    assert.ok(typeof pkg.target_runtime === "string" || pkg.target_runtime === null);
    assert.ok(typeof pkg.target_orchestrator === "string" || pkg.target_orchestrator === null);
    assert.ok(typeof pkg.node_count === "number");
    assert.ok(typeof pkg.validation_check_count === "number");
    assert.ok(Array.isArray(pkg.warnings));
    assert.ok(Array.isArray(pkg.findings));
    assert.ok(Array.isArray(pkg.errors));
  }
});

test("package with doctor findings is BLOCKED", () => {
  const tempDir = createTempPackage({
    runtime_policy: {
      single_statement_per_node: true,
      allow_full_refresh: false,
      requires_runtime_validation: false,
    },
  });

  const result = assessMigrationPackage({ packageDir: tempDir });

  assert.equal(result.readiness_status, "BLOCKED");
  assert.ok(result.findings_count > 0);
});

test("package with MERGE+DLI warning but no equivalence evidence is NEEDS_REVIEW", () => {
  const tempDir = createTempPackage({
    sourceSql: "MERGE INTO T tgt USING S src ON tgt.id = src.id WHEN NOT MATCHED THEN INSERT VALUES (src.id);",
  });

  const result = assessMigrationPackage({ packageDir: tempDir });

  assert.equal(result.readiness_status, "NEEDS_REVIEW");
  assert.ok(result.warnings.some((w) => w.includes("MERGE") && w.includes("DLI")));
});

test("package with full-refresh warning but no equivalence evidence is NEEDS_REVIEW", () => {
  const tempDir = createTempPackage({
    sourceSql: "INSERT INTO T SELECT * FROM S;",
    runtime_policy: {
      single_statement_per_node: true,
      allow_full_refresh: true,
      requires_runtime_validation: true,
    },
  });

  const result = assessMigrationPackage({ packageDir: tempDir });

  assert.equal(result.readiness_status, "NEEDS_REVIEW");
  assert.ok(result.warnings.some((w) => w.toLowerCase().includes("full-refresh")));
});

test("healthy package with no warnings and no equivalence evidence is READY_FOR_DRY_RUN", () => {
  const tempDir = createTempPackage({
    sourceSql: "INSERT INTO T SELECT * FROM S;",
  });

  const result = assessMigrationPackage({ packageDir: tempDir });

  assert.equal(result.readiness_status, "READY_FOR_DRY_RUN");
  assert.equal(result.doctor_healthy, true);
});

test("discoverMigrationPackages requires packagesDir", () => {
  const result = discoverMigrationPackages({ packagesDir: undefined });

  assert.ok(result.errors.length > 0);
  assert.equal(result.packages.length, 0);
});

test("discoverMigrationPackages handles nonexistent directory", () => {
  const result = discoverMigrationPackages({ packagesDir: "/tmp/does-not-exist-batch-test-xyz" });

  assert.ok(result.errors.length > 0);
  assert.equal(result.packages.length, 0);
});

test("batch assessment with nonexistent packagesDir returns INVALID_INPUT", () => {
  const result = batchAssessMigrationPackages({ packagesDir: "/tmp/does-not-exist-batch-test-xyz" });

  assert.equal(result.status, "INVALID_INPUT");
});
