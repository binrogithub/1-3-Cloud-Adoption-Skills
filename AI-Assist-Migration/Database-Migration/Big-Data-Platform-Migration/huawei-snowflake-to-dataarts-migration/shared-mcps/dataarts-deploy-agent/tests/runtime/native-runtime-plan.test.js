const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("path");
const { buildNativeRuntimePlan, flattenNativePlanSteps } = require("../../src/runtime/native-runtime-plan");

const ORDERS_DIR = path.resolve(__dirname, "../../cases/golden/orders_pipeline_simple");
const CUSTOMER_DIR = path.resolve(__dirname, "../../cases/golden/customer_status_pipeline_simple");

test("orders_pipeline_simple native plan ready", () => {
  const plan = buildNativeRuntimePlan({
    packageDir: ORDERS_DIR,
    dliQueue: "default",
  });

  assert.equal(plan.valid, true);
  assert.equal(plan.status, "NATIVE_RUNTIME_PLAN_READY");
  assert.equal(plan.migration_id, "orders_pipeline_simple");
  assert.equal(plan.dli_queue, "default");
});

test("customer_status_pipeline_simple native plan ready", () => {
  const plan = buildNativeRuntimePlan({
    packageDir: CUSTOMER_DIR,
    dliQueue: "default",
  });

  assert.equal(plan.valid, true);
  assert.equal(plan.status, "NATIVE_RUNTIME_PLAN_READY");
  assert.equal(plan.migration_id, "customer_status_pipeline_simple");
});

test("orders setup_sql_count = 3", () => {
  const plan = buildNativeRuntimePlan({ packageDir: ORDERS_DIR });
  assert.equal(plan.summary.setup_sql_count, 3);
});

test("orders target_sql_count = 5", () => {
  const plan = buildNativeRuntimePlan({ packageDir: ORDERS_DIR });
  assert.equal(plan.summary.target_sql_count, 5);
});

test("orders validation_query_count = 7", () => {
  const plan = buildNativeRuntimePlan({ packageDir: ORDERS_DIR });
  assert.equal(plan.summary.validation_query_count, 7);
});

test("orders total_steps = 16", () => {
  const plan = buildNativeRuntimePlan({ packageDir: ORDERS_DIR });
  assert.equal(plan.summary.total_steps, 16);
});

test("orders all planned steps executed = false", () => {
  const plan = buildNativeRuntimePlan({ packageDir: ORDERS_DIR });
  const allSteps = flattenNativePlanSteps(plan);
  for (const step of allSteps) {
    assert.equal(step.executed, false, `Step ${step.name} should have executed=false`);
  }
});

test("orders safety.no_sql_execution true", () => {
  const plan = buildNativeRuntimePlan({ packageDir: ORDERS_DIR });
  assert.equal(plan.safety.no_sql_execution, true);
});

test("orders safety.native_runtime_plan_only true", () => {
  const plan = buildNativeRuntimePlan({ packageDir: ORDERS_DIR });
  assert.equal(plan.safety.native_runtime_plan_only, true);
});

test("orders safety.no_cloud_api_calls true", () => {
  const plan = buildNativeRuntimePlan({ packageDir: ORDERS_DIR });
  assert.equal(plan.safety.no_cloud_api_calls, true);
});

test("orders safety.no_runtime_execution true", () => {
  const plan = buildNativeRuntimePlan({ packageDir: ORDERS_DIR });
  assert.equal(plan.safety.no_runtime_execution, true);
});

test("orders runtime_setup phase has DLI_SQL type steps", () => {
  const plan = buildNativeRuntimePlan({ packageDir: ORDERS_DIR });
  for (const step of plan.phases.runtime_setup) {
    assert.equal(step.type, "DLI_SQL");
    assert.equal(step.phase, "runtime_setup");
    assert.equal(step.execution_required, true);
  }
});

test("orders target_transform phase has DLI_SQL type steps", () => {
  const plan = buildNativeRuntimePlan({ packageDir: ORDERS_DIR });
  for (const step of plan.phases.target_transform) {
    assert.equal(step.type, "DLI_SQL");
    assert.equal(step.phase, "target_transform");
  }
});

test("orders runtime_validation phase has DLI_QUERY type steps", () => {
  const plan = buildNativeRuntimePlan({ packageDir: ORDERS_DIR });
  for (const step of plan.phases.runtime_validation) {
    assert.equal(step.type, "DLI_QUERY");
    assert.equal(step.phase, "runtime_validation");
  }
});

test("orders equivalence_summary phase has LOCAL_COMPARISON type step", () => {
  const plan = buildNativeRuntimePlan({ packageDir: ORDERS_DIR });
  assert.equal(plan.phases.equivalence_summary.length, 1);
  assert.equal(plan.phases.equivalence_summary[0].type, "LOCAL_COMPARISON");
  assert.equal(plan.phases.equivalence_summary[0].phase, "equivalence_summary");
});

test("orders execution_order starts at 1 and is sequential", () => {
  const plan = buildNativeRuntimePlan({ packageDir: ORDERS_DIR });
  const allSteps = flattenNativePlanSteps(plan);
  for (let i = 0; i < allSteps.length; i++) {
    assert.equal(allSteps[i].execution_order, i + 1);
  }
});

test("customer_status setup_sql_count = 3", () => {
  const plan = buildNativeRuntimePlan({ packageDir: CUSTOMER_DIR });
  assert.equal(plan.summary.setup_sql_count, 3);
});

test("customer_status target_sql_count = 5", () => {
  const plan = buildNativeRuntimePlan({ packageDir: CUSTOMER_DIR });
  assert.equal(plan.summary.target_sql_count, 5);
});

test("customer_status validation_query_count = 7", () => {
  const plan = buildNativeRuntimePlan({ packageDir: CUSTOMER_DIR });
  assert.equal(plan.summary.validation_query_count, 7);
});

test("customer_status total_steps = 16", () => {
  const plan = buildNativeRuntimePlan({ packageDir: CUSTOMER_DIR });
  assert.equal(plan.summary.total_steps, 16);
});

test("missing packageDir returns INVALID_INPUT", () => {
  const plan = buildNativeRuntimePlan({});
  assert.equal(plan.valid, false);
  assert.equal(plan.status, "INVALID_INPUT");
  assert.ok(plan.errors.some((e) => e.includes("packageDir")));
});

test("nonexistent package dir returns INVALID_PACKAGE", () => {
  const plan = buildNativeRuntimePlan({
    packageDir: "/nonexistent/path/that/does/not/exist",
  });
  assert.equal(plan.valid, false);
  assert.equal(plan.status, "INVALID_PACKAGE");
});

test("missing runtime artifacts returns INVALID_RUNTIME_ARTIFACTS", () => {
  const fs = require("fs");
  const os = require("os");
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "native-plan-no-runtime-"));
  fs.mkdirSync(path.join(tmpDir, "source"), { recursive: true });
  fs.mkdirSync(path.join(tmpDir, "target", "sql"), { recursive: true });
  fs.mkdirSync(path.join(tmpDir, "validation"), { recursive: true });
  fs.writeFileSync(path.join(tmpDir, "source", "snowflake_task_graph.sql"), "-- dummy");
  fs.writeFileSync(
    path.join(tmpDir, "target", "artifact_manifest.json"),
    JSON.stringify({
      manifest_version: "0.1",
      migration_id: "test_no_runtime",
      source_type: "snowflake_task_graph",
      target: { orchestrator: "DATAARTS_FACTORY", runtime: "DLI", node_type: "DLISQL" },
      nodes: [
        {
          id: "node1",
          name: "node1",
          type: "DLISQL",
          sql_file: "sql/01_test.sql",
          depends_on: [],
        },
      ],
    })
  );
  fs.writeFileSync(path.join(tmpDir, "target", "sql", "01_test.sql"), "SELECT 1;");
  fs.writeFileSync(
    path.join(tmpDir, "validation", "validation_plan.json"),
    JSON.stringify({
      validation_plan_version: "0.1",
      migration_id: "test_no_runtime",
      checks: [],
    })
  );

  const plan = buildNativeRuntimePlan({ packageDir: tmpDir });
  assert.equal(plan.valid, false);
  assert.equal(plan.status, "INVALID_RUNTIME_ARTIFACTS");
});

test("validation plan mismatch returns VALIDATION_PLAN_MISMATCH", () => {
  const fs = require("fs");
  const os = require("os");
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "native-plan-mismatch-"));
  fs.mkdirSync(path.join(tmpDir, "source"), { recursive: true });
  fs.mkdirSync(path.join(tmpDir, "target", "sql"), { recursive: true });
  fs.mkdirSync(path.join(tmpDir, "validation"), { recursive: true });
  fs.mkdirSync(path.join(tmpDir, "runtime", "setup"), { recursive: true });
  fs.mkdirSync(path.join(tmpDir, "runtime", "validation"), { recursive: true });

  fs.writeFileSync(path.join(tmpDir, "source", "snowflake_task_graph.sql"), "-- test_mismatch");
  fs.writeFileSync(
    path.join(tmpDir, "target", "artifact_manifest.json"),
    JSON.stringify({
      manifest_version: "0.1",
      migration_id: "test_mismatch",
      source_type: "snowflake_task_graph",
      target: { orchestrator: "DATAARTS_FACTORY", runtime: "DLI", node_type: "DLISQL" },
      nodes: [
        {
          id: "node1",
          name: "node1",
          type: "DLISQL",
          sql_file: "sql/01_test.sql",
          depends_on: [],
        },
      ],
    })
  );
  fs.writeFileSync(path.join(tmpDir, "target", "sql", "01_test.sql"), "SELECT 1;");
  fs.writeFileSync(
    path.join(tmpDir, "validation", "validation_plan.json"),
    JSON.stringify({
      validation_plan_version: "0.1",
      migration_id: "test_mismatch",
      checks: [
        {
          type: "TABLE_COUNT",
          object_name: "MISSING_TABLE",
          expected: 1,
        },
      ],
    })
  );
  fs.writeFileSync(path.join(tmpDir, "runtime", "setup", "01_setup.sql"), "CREATE SCHEMA test;");
  fs.writeFileSync(
    path.join(tmpDir, "runtime", "validation", "validation_queries.json"),
    JSON.stringify({
      validation_queries_version: "0.1",
      migration_id: "test_mismatch",
      runtime: "DLI",
      queries: [
        {
          id: "some_query",
          type: "TABLE_COUNT",
          object_name: "EXISTING_TABLE",
          sql: "SELECT COUNT(*) AS actual_value FROM test.existing",
          expected: 1,
        },
      ],
    })
  );

  const plan = buildNativeRuntimePlan({ packageDir: tmpDir });
  assert.equal(plan.valid, false);
  assert.equal(plan.status, "VALIDATION_PLAN_MISMATCH");
});

test("flattenNativePlanSteps returns all steps in order", () => {
  const plan = buildNativeRuntimePlan({ packageDir: ORDERS_DIR });
  const steps = flattenNativePlanSteps(plan);
  assert.equal(steps.length, plan.summary.total_steps);
});
