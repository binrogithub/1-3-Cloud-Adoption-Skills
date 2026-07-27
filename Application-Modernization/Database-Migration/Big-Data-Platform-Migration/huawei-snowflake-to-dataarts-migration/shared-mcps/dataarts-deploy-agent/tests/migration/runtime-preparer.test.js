const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const os = require("os");
const path = require("path");
const yaml = require("js-yaml");
const { prepareRuntimeArtifacts, buildCanonicalDag, buildPipelineYaml, deriveMedallionLayer, deriveOperationType } = require("../../src/migration/runtime-preparer");
const { loadAll } = require("../../src/load-artifacts");

const GOLDEN_DIR = path.resolve(__dirname, "../../cases/golden/orders_pipeline_simple");
const CUSTOMER_GOLDEN_DIR = path.resolve(__dirname, "../../cases/golden/customer_status_pipeline_simple");

test("golden orders pipeline package prepares runtime artifacts successfully", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "runtime-preparer-"));
  const result = prepareRuntimeArtifacts({ packageDir: GOLDEN_DIR, outDir });

  assert.equal(result.valid, true);
  assert.equal(result.status, "RUNTIME_ARTIFACTS_READY");
  assert.equal(result.migration_id, "orders_pipeline_simple");
  assert.equal(result.copied_sql_files.length, 5);
  assert.equal(result.doctor_summary.healthy, true);
  assert.equal(result.errors.length, 0);
});

test("missing packageDir returns INVALID_INPUT", () => {
  const result = prepareRuntimeArtifacts({});

  assert.equal(result.valid, false);
  assert.equal(result.status, "INVALID_INPUT");
  assert.ok(result.errors.some((e) => e.includes("packageDir is required")));
});

test("missing package directory returns INVALID_PACKAGE", () => {
  const result = prepareRuntimeArtifacts({
    packageDir: "/tmp/package-dir-does-not-exist-xyz-runtime",
  });

  assert.equal(result.valid, false);
  assert.equal(result.status, "INVALID_PACKAGE");
});

test("prepared runtime directory contains dataarts/nodes", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "runtime-preparer-"));
  const result = prepareRuntimeArtifacts({ packageDir: GOLDEN_DIR, outDir });

  assert.equal(result.valid, true);
  assert.ok(fs.existsSync(result.runtime_nodes_dir));
  const entries = fs.readdirSync(result.runtime_nodes_dir);
  assert.ok(entries.length > 0);
});

test("prepared runtime directory contains 5 SQL files", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "runtime-preparer-"));
  const result = prepareRuntimeArtifacts({ packageDir: GOLDEN_DIR, outDir });

  assert.equal(result.valid, true);
  const entries = fs.readdirSync(result.runtime_nodes_dir).filter((f) => f.endsWith(".sql"));
  assert.equal(entries.length, 5);
});

test("runtime_artifact_manifest.json is written", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "runtime-preparer-"));
  const result = prepareRuntimeArtifacts({ packageDir: GOLDEN_DIR, outDir });

  assert.equal(result.valid, true);
  const manifestPath = path.join(result.runtime_artifacts_dir, "runtime_artifact_manifest.json");
  assert.ok(fs.existsSync(manifestPath));

  const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf-8"));
  assert.equal(manifest.migration_id, "orders_pipeline_simple");
  assert.equal(manifest.sql_files.length, 5);
  assert.ok(manifest.runtime_setup_files);
  assert.equal(manifest.runtime_setup_files.length, 3);
  assert.ok(manifest.runtime_validation_queries_path);
});

test("copied SQL files all have statement_count 1", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "runtime-preparer-"));
  const result = prepareRuntimeArtifacts({ packageDir: GOLDEN_DIR, outDir });

  assert.equal(result.valid, true);
  for (const f of result.copied_sql_files) {
    assert.equal(f.statement_count, 1, `node ${f.node_id} should have statement_count 1`);
  }
});

test("runtime_prepare_result.json is written", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "runtime-preparer-"));
  const result = prepareRuntimeArtifacts({ packageDir: GOLDEN_DIR, outDir });

  assert.equal(result.valid, true);
  const migrationOutDir = path.join(outDir, result.migration_id);
  const resultPath = path.join(migrationOutDir, "runtime_prepare_result.json");
  assert.ok(fs.existsSync(resultPath));
});

test("runtime_prepare_report.md is written", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "runtime-preparer-"));
  const result = prepareRuntimeArtifacts({ packageDir: GOLDEN_DIR, outDir });

  assert.equal(result.valid, true);
  const migrationOutDir = path.join(outDir, result.migration_id);
  const reportPath = path.join(migrationOutDir, "runtime_prepare_report.md");
  assert.ok(fs.existsSync(reportPath));
});

test("prepared runtime directory contains analysis/canonical_dag.json", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "runtime-preparer-"));
  const result = prepareRuntimeArtifacts({ packageDir: GOLDEN_DIR, outDir });

  assert.equal(result.valid, true);
  const dagPath = path.join(result.runtime_artifacts_dir, "analysis", "canonical_dag.json");
  assert.ok(fs.existsSync(dagPath));
  const dag = JSON.parse(fs.readFileSync(dagPath, "utf-8"));
  assert.ok(dag.dag);
  assert.equal(dag.dag.total_nodes, 5);
  assert.ok(Array.isArray(dag.dag.nodes));
  assert.ok(Array.isArray(dag.dag.edges));
});

test("prepared runtime directory contains dataarts/dataarts_pipeline.yaml", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "runtime-preparer-"));
  const result = prepareRuntimeArtifacts({ packageDir: GOLDEN_DIR, outDir });

  assert.equal(result.valid, true);
  const yamlPath = path.join(result.runtime_artifacts_dir, "dataarts", "dataarts_pipeline.yaml");
  assert.ok(fs.existsSync(yamlPath));
  const content = fs.readFileSync(yamlPath, "utf-8");
  const parsed = yaml.load(content);
  assert.ok(parsed.nodes);
  assert.ok(parsed.schedule);
  assert.ok(parsed.dependencies);
  assert.ok(parsed.execution_order);
});

test("prepared runtime directory contains analysis/compatibility_report.md", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "runtime-preparer-"));
  const result = prepareRuntimeArtifacts({ packageDir: GOLDEN_DIR, outDir });

  assert.equal(result.valid, true);
  const reportPath = path.join(result.runtime_artifacts_dir, "analysis", "compatibility_report.md");
  assert.ok(fs.existsSync(reportPath));
  const content = fs.readFileSync(reportPath, "utf-8");
  assert.ok(content.includes("COMPATIBLE"));
});

test("generated artifacts can be loaded by legacy loadAll", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "runtime-preparer-"));
  const result = prepareRuntimeArtifacts({ packageDir: GOLDEN_DIR, outDir });

  assert.equal(result.valid, true);
  const artifacts = loadAll(result.runtime_artifacts_dir);
  assert.ok(artifacts.canonicalDag);
  assert.ok(artifacts.pipelineYaml);
  assert.ok(artifacts.sqlNodes);
  assert.equal(artifacts.canonicalDag.dag.total_nodes, 5);
  assert.equal(artifacts.pipelineYaml.nodes.length, 5);
  assert.equal(Object.keys(artifacts.sqlNodes).length, 5);
});

test("canonical_dag nodes have required legacy fields", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "runtime-preparer-"));
  const result = prepareRuntimeArtifacts({ packageDir: GOLDEN_DIR, outDir });

  assert.equal(result.valid, true);
  const dagPath = path.join(result.runtime_artifacts_dir, "analysis", "canonical_dag.json");
  const dag = JSON.parse(fs.readFileSync(dagPath, "utf-8"));

  for (const node of dag.dag.nodes) {
    assert.ok(node.id, "node has id");
    assert.ok(node.name, "node has name");
    assert.ok(node.source_task_name, "node has source_task_name");
    assert.ok(node.target_node_type, "node has target_node_type");
    assert.ok(node.medallion_layer, "node has medallion_layer");
    assert.ok(node.operation_type, "node has operation_type");
    assert.ok(node.sql_file, "node has sql_file");
    assert.ok(Array.isArray(node.dependencies), "node dependencies is array");
    assert.ok(typeof node.execution_order === "number", "node has execution_order");
    assert.ok(node.description, "node has description");
  }
});

test("pipeline yaml nodes have required legacy fields", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "runtime-preparer-"));
  const result = prepareRuntimeArtifacts({ packageDir: GOLDEN_DIR, outDir });

  assert.equal(result.valid, true);
  const yamlPath = path.join(result.runtime_artifacts_dir, "dataarts", "dataarts_pipeline.yaml");
  const content = fs.readFileSync(yamlPath, "utf-8");
  const parsed = yaml.load(content);

  for (const node of parsed.nodes) {
    assert.ok(node.id, "node has id");
    assert.ok(node.name, "node has name");
    assert.ok(node.type, "node has type");
    assert.ok(node.sql_file, "node has sql_file");
    assert.ok(node.source_task, "node has source_task");
    assert.ok(typeof node.execution_order === "number", "node has execution_order");
    assert.ok(node.description, "node has description");
  }
});

test("deriveMedallionLayer works for known patterns", () => {
  assert.equal(deriveMedallionLayer("drop_silver_orders"), "silver");
  assert.equal(deriveMedallionLayer("create_silver_orders"), "silver");
  assert.equal(deriveMedallionLayer("drop_gold_daily_sales"), "gold");
  assert.equal(deriveMedallionLayer("create_gold_daily_sales"), "gold");
  assert.equal(deriveMedallionLayer("audit_pipeline"), "audit");
});

test("deriveOperationType works for known patterns", () => {
  assert.equal(deriveOperationType("drop_silver_orders"), "DROP");
  assert.equal(deriveOperationType("create_silver_orders"), "CTAS");
  assert.equal(deriveOperationType("audit_pipeline"), "INSERT");
});

test("buildCanonicalDag produces valid structure from manifest", () => {
  const { loadArtifactManifest } = require("../../src/artifacts/manifest-loader");
  const manifestPath = path.join(GOLDEN_DIR, "target", "artifact_manifest.json");
  const manifestResult = loadArtifactManifest(manifestPath);
  assert.equal(manifestResult.valid, true);

  const dag = buildCanonicalDag(manifestResult.manifest, manifestResult.nodes);
  assert.ok(dag.dag);
  assert.equal(dag.dag.total_nodes, 5);
  assert.equal(dag.dag.nodes.length, 5);
  assert.ok(dag.dag.edges.length > 0);
  assert.ok(dag.dag.root_task);
  assert.equal(dag.dag.source_platform, "snowflake");
  assert.equal(dag.dag.target_platform, "huawei_cloud_dataarts_factory");
});

test("buildPipelineYaml produces valid structure from manifest", () => {
  const { loadArtifactManifest } = require("../../src/artifacts/manifest-loader");
  const manifestPath = path.join(GOLDEN_DIR, "target", "artifact_manifest.json");
  const manifestResult = loadArtifactManifest(manifestPath);
  assert.equal(manifestResult.valid, true);

  const pipeline = buildPipelineYaml(manifestResult.manifest, manifestResult.nodes);
  assert.ok(pipeline.pipeline);
  assert.ok(pipeline.schedule);
  assert.equal(pipeline.nodes.length, 5);
  assert.ok(pipeline.dependencies.length > 0);
  assert.equal(pipeline.execution_order.length, 5);
});

test("golden customer status pipeline package prepares runtime artifacts successfully", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "runtime-preparer-"));
  const result = prepareRuntimeArtifacts({ packageDir: CUSTOMER_GOLDEN_DIR, outDir });

  assert.equal(result.valid, true);
  assert.equal(result.status, "RUNTIME_ARTIFACTS_READY");
  assert.equal(result.migration_id, "customer_status_pipeline_simple");
  assert.equal(result.copied_sql_files.length, 5);
  assert.equal(result.doctor_summary.healthy, true);
  assert.equal(result.errors.length, 0);
});

test("customer status prepared runtime directory contains dataarts/nodes", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "runtime-preparer-"));
  const result = prepareRuntimeArtifacts({ packageDir: CUSTOMER_GOLDEN_DIR, outDir });

  assert.equal(result.valid, true);
  assert.ok(fs.existsSync(result.runtime_nodes_dir));
  const entries = fs.readdirSync(result.runtime_nodes_dir);
  assert.ok(entries.length > 0);
});

test("customer status prepared runtime directory contains 5 SQL files", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "runtime-preparer-"));
  const result = prepareRuntimeArtifacts({ packageDir: CUSTOMER_GOLDEN_DIR, outDir });

  assert.equal(result.valid, true);
  const entries = fs.readdirSync(result.runtime_nodes_dir).filter((f) => f.endsWith(".sql"));
  assert.equal(entries.length, 5);
});

test("customer status runtime_artifact_manifest.json is written", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "runtime-preparer-"));
  const result = prepareRuntimeArtifacts({ packageDir: CUSTOMER_GOLDEN_DIR, outDir });

  assert.equal(result.valid, true);
  const manifestPath = path.join(result.runtime_artifacts_dir, "runtime_artifact_manifest.json");
  assert.ok(fs.existsSync(manifestPath));

  const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf-8"));
  assert.equal(manifest.migration_id, "customer_status_pipeline_simple");
  assert.equal(manifest.sql_files.length, 5);
});

test("customer status copied SQL files all have statement_count 1", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "runtime-preparer-"));
  const result = prepareRuntimeArtifacts({ packageDir: CUSTOMER_GOLDEN_DIR, outDir });

  assert.equal(result.valid, true);
  for (const f of result.copied_sql_files) {
    assert.equal(f.statement_count, 1, `node ${f.node_id} should have statement_count 1`);
  }
});

test("customer status prepared runtime directory contains analysis/canonical_dag.json", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "runtime-preparer-"));
  const result = prepareRuntimeArtifacts({ packageDir: CUSTOMER_GOLDEN_DIR, outDir });

  assert.equal(result.valid, true);
  const dagPath = path.join(result.runtime_artifacts_dir, "analysis", "canonical_dag.json");
  assert.ok(fs.existsSync(dagPath));
  const dag = JSON.parse(fs.readFileSync(dagPath, "utf-8"));
  assert.ok(dag.dag);
  assert.equal(dag.dag.total_nodes, 5);
});

test("customer status prepared runtime directory contains dataarts/dataarts_pipeline.yaml", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "runtime-preparer-"));
  const result = prepareRuntimeArtifacts({ packageDir: CUSTOMER_GOLDEN_DIR, outDir });

  assert.equal(result.valid, true);
  const yamlPath = path.join(result.runtime_artifacts_dir, "dataarts", "dataarts_pipeline.yaml");
  assert.ok(fs.existsSync(yamlPath));
  const content = fs.readFileSync(yamlPath, "utf-8");
  const parsed = yaml.load(content);
  assert.ok(parsed.nodes);
  assert.ok(parsed.schedule);
  assert.ok(parsed.dependencies);
  assert.ok(parsed.execution_order);
});

test("customer status prepared runtime directory contains analysis/compatibility_report.md", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "runtime-preparer-"));
  const result = prepareRuntimeArtifacts({ packageDir: CUSTOMER_GOLDEN_DIR, outDir });

  assert.equal(result.valid, true);
  const reportPath = path.join(result.runtime_artifacts_dir, "analysis", "compatibility_report.md");
  assert.ok(fs.existsSync(reportPath));
  const content = fs.readFileSync(reportPath, "utf-8");
  assert.ok(content.includes("COMPATIBLE"));
});

test("customer status generated artifacts can be loaded by legacy loadAll", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "runtime-preparer-"));
  const result = prepareRuntimeArtifacts({ packageDir: CUSTOMER_GOLDEN_DIR, outDir });

  assert.equal(result.valid, true);
  const artifacts = loadAll(result.runtime_artifacts_dir);
  assert.ok(artifacts.canonicalDag);
  assert.ok(artifacts.pipelineYaml);
  assert.ok(artifacts.sqlNodes);
  assert.equal(artifacts.canonicalDag.dag.total_nodes, 5);
  assert.equal(artifacts.pipelineYaml.nodes.length, 5);
  assert.equal(Object.keys(artifacts.sqlNodes).length, 5);
});

test("runtime-preparer copies runtime/setup into prepared artifacts for orders", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "runtime-preparer-"));
  const result = prepareRuntimeArtifacts({ packageDir: GOLDEN_DIR, outDir });

  assert.equal(result.valid, true);
  const setupDir = path.join(result.runtime_artifacts_dir, "runtime", "setup");
  assert.ok(fs.existsSync(setupDir));
  const setupFiles = fs.readdirSync(setupDir).filter((f) => f.endsWith(".sql"));
  assert.equal(setupFiles.length, 3);
  assert.ok(setupFiles.includes("01_create_schema.sql"));
  assert.ok(setupFiles.includes("02_create_raw_tables.sql"));
  assert.ok(setupFiles.includes("03_insert_seed_data.sql"));
});

test("runtime-preparer copies runtime/validation into prepared artifacts for orders", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "runtime-preparer-"));
  const result = prepareRuntimeArtifacts({ packageDir: GOLDEN_DIR, outDir });

  assert.equal(result.valid, true);
  const validationDir = path.join(result.runtime_artifacts_dir, "runtime", "validation");
  assert.ok(fs.existsSync(validationDir));
  const validationQueriesPath = path.join(validationDir, "validation_queries.json");
  assert.ok(fs.existsSync(validationQueriesPath));
  const queries = JSON.parse(fs.readFileSync(validationQueriesPath, "utf-8"));
  assert.equal(queries.migration_id, "orders_pipeline_simple");
});

test("runtime-preparer copies runtime/setup into prepared artifacts for customer", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "runtime-preparer-"));
  const result = prepareRuntimeArtifacts({ packageDir: CUSTOMER_GOLDEN_DIR, outDir });

  assert.equal(result.valid, true);
  const setupDir = path.join(result.runtime_artifacts_dir, "runtime", "setup");
  assert.ok(fs.existsSync(setupDir));
  const setupFiles = fs.readdirSync(setupDir).filter((f) => f.endsWith(".sql"));
  assert.equal(setupFiles.length, 3);
});

test("runtime-preparer copies runtime/validation into prepared artifacts for customer", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "runtime-preparer-"));
  const result = prepareRuntimeArtifacts({ packageDir: CUSTOMER_GOLDEN_DIR, outDir });

  assert.equal(result.valid, true);
  const validationDir = path.join(result.runtime_artifacts_dir, "runtime", "validation");
  assert.ok(fs.existsSync(validationDir));
  const validationQueriesPath = path.join(validationDir, "validation_queries.json");
  assert.ok(fs.existsSync(validationQueriesPath));
  const queries = JSON.parse(fs.readFileSync(validationQueriesPath, "utf-8"));
  assert.equal(queries.migration_id, "customer_status_pipeline_simple");
});

test("runtime_artifact_manifest includes runtime setup and validation metadata for orders", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "runtime-preparer-"));
  const result = prepareRuntimeArtifacts({ packageDir: GOLDEN_DIR, outDir });

  assert.equal(result.valid, true);
  const manifestPath = path.join(result.runtime_artifacts_dir, "runtime_artifact_manifest.json");
  const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf-8"));
  assert.ok(manifest.runtime_setup_files);
  assert.equal(manifest.runtime_setup_files.length, 3);
  assert.ok(manifest.runtime_validation_queries_path);
  assert.ok(manifest.runtime_validation_queries_path.includes("validation_queries.json"));
});

test("runtime_artifact_manifest includes runtime setup and validation metadata for customer", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "runtime-preparer-"));
  const result = prepareRuntimeArtifacts({ packageDir: CUSTOMER_GOLDEN_DIR, outDir });

  assert.equal(result.valid, true);
  const manifestPath = path.join(result.runtime_artifacts_dir, "runtime_artifact_manifest.json");
  const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf-8"));
  assert.ok(manifest.runtime_setup_files);
  assert.equal(manifest.runtime_setup_files.length, 3);
  assert.ok(manifest.runtime_validation_queries_path);
  assert.ok(manifest.runtime_validation_queries_path.includes("validation_queries.json"));
});
