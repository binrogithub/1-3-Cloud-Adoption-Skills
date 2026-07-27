const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { countSqlStatements, loadArtifactManifest } = require("../../src/artifacts/manifest-loader");

test("countSqlStatements counts empty SQL as zero", () => {
  assert.equal(countSqlStatements(""), 0);
});

test("countSqlStatements counts single SQL statement", () => {
  assert.equal(countSqlStatements("SELECT 1;"), 1);
});

test("countSqlStatements counts multiple SQL statements", () => {
  assert.equal(countSqlStatements("SELECT 1; SELECT 2;"), 2);
});

test("loadArtifactManifest validates golden orders pipeline manifest", () => {
  const manifestPath = path.resolve(
    __dirname,
    "../../cases/golden/orders_pipeline_simple/target/artifact_manifest.json"
  );

  const result = loadArtifactManifest(manifestPath);

  assert.equal(result.valid, true);
  assert.equal(result.manifest.migration_id, "orders_pipeline_simple");
  assert.equal(result.manifest.target.runtime, "DLI");
  assert.equal(result.nodes.length, 5);

  for (const node of result.nodes) {
    assert.equal(node.sql_exists, true);
    assert.equal(node.statement_count, 1);
  }
});

test("loadArtifactManifest validates golden customer status pipeline manifest", () => {
  const manifestPath = path.resolve(
    __dirname,
    "../../cases/golden/customer_status_pipeline_simple/target/artifact_manifest.json"
  );

  const result = loadArtifactManifest(manifestPath);

  assert.equal(result.valid, true);
  assert.equal(result.manifest.migration_id, "customer_status_pipeline_simple");
  assert.equal(result.manifest.target.runtime, "DLI");
  assert.equal(result.nodes.length, 5);

  for (const node of result.nodes) {
    assert.equal(node.sql_exists, true);
    assert.equal(node.statement_count, 1);
  }
});

test("loadArtifactManifest fails when SQL file is missing", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "manifest-loader-"));
  fs.mkdirSync(path.join(dir, "sql"), { recursive: true });

  const manifestPath = path.join(dir, "artifact_manifest.json");

  fs.writeFileSync(manifestPath, JSON.stringify({
    manifest_version: "0.1",
    migration_id: "bad_case",
    target: {
      orchestrator: "DATAARTS_FACTORY",
      runtime: "DLI"
    },
    nodes: [
      {
        id: "node_a",
        name: "node_a",
        type: "DLISQL",
        sql_file: "sql/missing.sql",
        depends_on: []
      }
    ]
  }, null, 2));

  const result = loadArtifactManifest(manifestPath);

  assert.equal(result.valid, false);
  assert.match(result.errors.join("\n"), /SQL file not found/);
});

test("loadArtifactManifest fails when dependency points to unknown node", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "manifest-loader-"));
  fs.mkdirSync(path.join(dir, "sql"), { recursive: true });

  fs.writeFileSync(path.join(dir, "sql", "node_a.sql"), "SELECT 1;", "utf-8");

  const manifestPath = path.join(dir, "artifact_manifest.json");

  fs.writeFileSync(manifestPath, JSON.stringify({
    manifest_version: "0.1",
    migration_id: "bad_dependency_case",
    target: {
      orchestrator: "DATAARTS_FACTORY",
      runtime: "DLI"
    },
    nodes: [
      {
        id: "node_a",
        name: "node_a",
        type: "DLISQL",
        sql_file: "sql/node_a.sql",
        depends_on: ["missing_node"]
      }
    ]
  }, null, 2));

  const result = loadArtifactManifest(manifestPath);

  assert.equal(result.valid, false);
  assert.match(result.errors.join("\n"), /unknown node/);
});
