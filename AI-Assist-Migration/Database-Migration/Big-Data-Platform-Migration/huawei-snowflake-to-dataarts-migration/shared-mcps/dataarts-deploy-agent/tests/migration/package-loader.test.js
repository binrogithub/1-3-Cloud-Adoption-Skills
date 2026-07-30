const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { loadMigrationPackage } = require("../../src/migration/package-loader");

test("loadMigrationPackage validates golden orders pipeline package", () => {
  const packageDir = path.resolve(
    __dirname,
    "../../cases/golden/orders_pipeline_simple"
  );

  const result = loadMigrationPackage(packageDir);

  assert.equal(result.valid, true);
  assert.equal(result.migration_id, "orders_pipeline_simple");
  assert.ok(result.source.task_graph_sql.includes("T_LOAD_SILVER_ORDERS"));
  assert.equal(result.artifact_manifest_result.valid, true);
  assert.equal(result.validation_plan.migration_id, "orders_pipeline_simple");
});

test("loadMigrationPackage validates golden customer status pipeline package", () => {
  const packageDir = path.resolve(
    __dirname,
    "../../cases/golden/customer_status_pipeline_simple"
  );

  const result = loadMigrationPackage(packageDir);

  assert.equal(result.valid, true);
  assert.equal(result.migration_id, "customer_status_pipeline_simple");
  assert.ok(result.source.task_graph_sql.includes("T_LOAD_SILVER_CUSTOMERS"));
  assert.equal(result.artifact_manifest_result.valid, true);
  assert.equal(result.validation_plan.migration_id, "customer_status_pipeline_simple");
});

test("loadMigrationPackage fails when package directory does not exist", () => {
  const result = loadMigrationPackage("/tmp/migration-package-does-not-exist");

  assert.equal(result.valid, false);
  assert.match(result.errors.join("\n"), /does not exist/);
});

test("loadMigrationPackage fails when source task graph is missing", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "migration-package-"));
  fs.mkdirSync(path.join(dir, "target"), { recursive: true });
  fs.mkdirSync(path.join(dir, "validation"), { recursive: true });
  fs.mkdirSync(path.join(dir, "expected"), { recursive: true });
  fs.mkdirSync(path.join(dir, "target", "sql"), { recursive: true });

  fs.writeFileSync(path.join(dir, "target", "sql", "node.sql"), "SELECT 1;", "utf-8");

  fs.writeFileSync(path.join(dir, "target", "artifact_manifest.json"), JSON.stringify({
    manifest_version: "0.1",
    migration_id: "missing_source_case",
    target: {
      orchestrator: "DATAARTS_FACTORY",
      runtime: "DLI"
    },
    nodes: [
      {
        id: "node",
        name: "node",
        type: "DLISQL",
        sql_file: "sql/node.sql",
        depends_on: []
      }
    ]
  }, null, 2));

  fs.writeFileSync(path.join(dir, "validation", "validation_plan.json"), JSON.stringify({
    validation_plan_version: "0.1",
    migration_id: "missing_source_case",
    checks: []
  }, null, 2));

  const result = loadMigrationPackage(dir);

  assert.equal(result.valid, false);
  assert.match(result.errors.join("\n"), /Missing source task graph/);
});

test("loadMigrationPackage fails on migration_id mismatch", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "migration-package-"));
  fs.mkdirSync(path.join(dir, "source"), { recursive: true });
  fs.mkdirSync(path.join(dir, "target", "sql"), { recursive: true });
  fs.mkdirSync(path.join(dir, "validation"), { recursive: true });

  fs.writeFileSync(path.join(dir, "source", "snowflake_task_graph.sql"), "CREATE TASK A AS SELECT 1;", "utf-8");
  fs.writeFileSync(path.join(dir, "target", "sql", "node.sql"), "SELECT 1;", "utf-8");

  fs.writeFileSync(path.join(dir, "target", "artifact_manifest.json"), JSON.stringify({
    manifest_version: "0.1",
    migration_id: "manifest_id",
    target: {
      orchestrator: "DATAARTS_FACTORY",
      runtime: "DLI"
    },
    nodes: [
      {
        id: "node",
        name: "node",
        type: "DLISQL",
        sql_file: "sql/node.sql",
        depends_on: []
      }
    ]
  }, null, 2));

  fs.writeFileSync(path.join(dir, "validation", "validation_plan.json"), JSON.stringify({
    validation_plan_version: "0.1",
    migration_id: "validation_id",
    checks: []
  }, null, 2));

  const result = loadMigrationPackage(dir);

  assert.equal(result.valid, false);
  assert.match(result.errors.join("\n"), /migration_id mismatch/);
});
