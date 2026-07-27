const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { runMigrationPackageDoctor } = require("../../src/migration/package-doctor");

const GOLDEN_DIR = path.resolve(__dirname, "../../cases/golden/orders_pipeline_simple");
const CUSTOMER_GOLDEN_DIR = path.resolve(__dirname, "../../cases/golden/customer_status_pipeline_simple");

function createTempPackage(overrides = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "doctor-pkg-"));
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

test("golden orders pipeline package is healthy", () => {
  const result = runMigrationPackageDoctor({ packageDir: GOLDEN_DIR });

  assert.equal(result.healthy, true);
  assert.equal(result.status, "HEALTHY");
  assert.equal(result.migration_id, "orders_pipeline_simple");
  assert.equal(result.findings.length, 0);
  assert.equal(result.summary.node_count, 5);
  assert.equal(result.summary.validation_check_count, 7);
  assert.equal(result.summary.target_runtime, "DLI");
  assert.equal(result.summary.target_orchestrator, "DATAARTS_FACTORY");
  assert.equal(result.summary.all_single_statement, true);
  assert.equal(result.summary.requires_runtime_validation, true);
  assert.equal(result.summary.has_runtime_setup, true);
  assert.equal(result.summary.has_runtime_validation, true);
});

test("missing packageDir is unhealthy", () => {
  const result = runMigrationPackageDoctor({});

  assert.equal(result.healthy, false);
  assert.equal(result.status, "UNHEALTHY");
  assert.ok(result.findings.some((f) => f.includes("packageDir is required")));
});

test("missing package directory is unhealthy", () => {
  const result = runMigrationPackageDoctor({
    packageDir: "/tmp/package-dir-does-not-exist-xyz",
  });

  assert.equal(result.healthy, false);
  assert.equal(result.status, "UNHEALTHY");
  assert.ok(result.findings.some((f) => f.includes("does not exist")));
});

test("package with validation_plan checks empty is unhealthy", () => {
  const dir = createTempPackage({ checks: [] });

  const result = runMigrationPackageDoctor({ packageDir: dir });

  assert.equal(result.healthy, false);
  assert.ok(result.findings.some((f) => f.includes("no checks")));
});

test("package with runtime_policy.requires_runtime_validation false is unhealthy", () => {
  const dir = createTempPackage({
    runtime_policy: {
      single_statement_per_node: true,
      allow_full_refresh: false,
      requires_runtime_validation: false,
    },
  });

  const result = runMigrationPackageDoctor({ packageDir: dir });

  assert.equal(result.healthy, false);
  assert.ok(result.findings.some((f) => f.includes("requires_runtime_validation")));
});

test("package with target.runtime not DLI is unhealthy for current MVP", () => {
  const dir = createTempPackage({ runtime: "DWS" });

  const result = runMigrationPackageDoctor({ packageDir: dir });

  assert.equal(result.healthy, false);
  assert.ok(result.findings.some((f) => f.includes("target.runtime") && f.includes("DLI")));
});

test("source MERGE with DLI emits warning but remains healthy when package otherwise valid", () => {
  const dir = createTempPackage({
    sourceSql: "MERGE INTO T tgt USING S src ON tgt.id = src.id WHEN NOT MATCHED THEN INSERT VALUES (src.id);",
    runtime_policy: {
      single_statement_per_node: true,
      allow_full_refresh: false,
      requires_runtime_validation: true,
    },
  });

  const result = runMigrationPackageDoctor({ packageDir: dir });

  assert.equal(result.healthy, true);
  assert.equal(result.status, "HEALTHY");
  assert.ok(result.warnings.some((w) => w.includes("MERGE") && w.includes("DLI")));
});

test("golden customer status pipeline package is healthy", () => {
  const result = runMigrationPackageDoctor({ packageDir: CUSTOMER_GOLDEN_DIR });

  assert.equal(result.healthy, true);
  assert.equal(result.status, "HEALTHY");
  assert.equal(result.migration_id, "customer_status_pipeline_simple");
  assert.equal(result.findings.length, 0);
  assert.equal(result.summary.node_count, 5);
  assert.equal(result.summary.validation_check_count, 8);
  assert.equal(result.summary.target_runtime, "DLI");
  assert.equal(result.summary.target_orchestrator, "DATAARTS_FACTORY");
  assert.equal(result.summary.all_single_statement, true);
  assert.equal(result.summary.requires_runtime_validation, true);
  assert.equal(result.summary.has_runtime_setup, true);
  assert.equal(result.summary.has_runtime_validation, true);
});

test("customer status package has fewer warnings than orders pipeline (no MERGE warning)", () => {
  const ordersResult = runMigrationPackageDoctor({ packageDir: GOLDEN_DIR });
  const customerResult = runMigrationPackageDoctor({ packageDir: CUSTOMER_GOLDEN_DIR });

  assert.equal(ordersResult.healthy, true);
  assert.equal(customerResult.healthy, true);
  assert.ok(customerResult.warnings.length < ordersResult.warnings.length,
    `customer warnings (${customerResult.warnings.length}) should be < orders warnings (${ordersResult.warnings.length})`);
  assert.ok(ordersResult.warnings.some((w) => w.includes("MERGE")));
  assert.ok(!customerResult.warnings.some((w) => w.includes("MERGE")));
});

test("package without runtime artifacts gets warning but remains healthy", () => {
  const dir = createTempPackage();

  const result = runMigrationPackageDoctor({ packageDir: dir });

  assert.equal(result.healthy, true);
  assert.equal(result.status, "HEALTHY");
  assert.equal(result.summary.has_runtime_setup, false);
  assert.equal(result.summary.has_runtime_validation, false);
  assert.ok(result.warnings.some((w) => w.includes("Runtime setup/validation artifacts are missing")));
});
