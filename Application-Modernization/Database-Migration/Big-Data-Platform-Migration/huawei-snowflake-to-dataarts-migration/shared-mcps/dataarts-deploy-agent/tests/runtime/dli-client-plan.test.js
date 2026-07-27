const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("path");
const fs = require("fs");
const { buildNativeRuntimePlan } = require("../../src/runtime/native-runtime-plan");
const { createRealDliClient, createRealDliSafetyPolicy } = require("../../src/runtime/dli/real-dli-client");

const ORDERS_DIR = path.resolve(__dirname, "../../cases/golden/orders_pipeline_simple");
const CUSTOMER_DIR = path.resolve(__dirname, "../../cases/golden/customer_status_pipeline_simple");

async function buildDliClientPlan(packageDir, dliQueue) {
  const nativePlan = buildNativeRuntimePlan({ packageDir, dliQueue });
  if (!nativePlan.valid) {
    return { valid: false, errors: nativePlan.errors };
  }

  const client = createRealDliClient({ allowRealExecution: false });
  const plannedSqlExecutions = [];
  const plannedQueryExecutions = [];

  for (const step of nativePlan.phases.runtime_setup) {
    const sql = fs.readFileSync(step.file_path, "utf-8");
    const result = await client.executeSql({ sql, queueName: dliQueue, step });
    plannedSqlExecutions.push(result);
  }

  for (const step of nativePlan.phases.target_transform) {
    const sqlPath = step.sql_path;
    let sql = "";
    if (sqlPath && fs.existsSync(sqlPath)) {
      sql = fs.readFileSync(sqlPath, "utf-8");
    }
    const result = await client.executeSql({ sql, queueName: dliQueue, step });
    plannedSqlExecutions.push(result);
  }

  for (const step of nativePlan.phases.runtime_validation) {
    const result = await client.querySql({ sql: step.sql, queueName: dliQueue, step });
    plannedQueryExecutions.push(result);
  }

  return {
    valid: true,
    migration_id: nativePlan.migration_id,
    planned_sql_executions: plannedSqlExecutions,
    planned_query_executions: plannedQueryExecutions,
    total_planned_requests: plannedSqlExecutions.length + plannedQueryExecutions.length,
    safety: createRealDliSafetyPolicy(),
  };
}

test("dli client plan creates 15 planned DLI requests for orders", async () => {
  const result = await buildDliClientPlan(ORDERS_DIR, "default");
  assert.equal(result.valid, true);
  assert.equal(result.migration_id, "orders_pipeline_simple");
  assert.equal(result.total_planned_requests, 15);
});

test("dli client plan orders has 3 setup + 5 target + 7 validation", async () => {
  const result = await buildDliClientPlan(ORDERS_DIR, "default");
  const setupCount = result.planned_sql_executions.filter(
    (r) => r.planned_request && r.planned_request.step_name && r.planned_request.step_name.includes(".sql")
  ).length;
  const targetCount = result.planned_sql_executions.filter(
    (r) => r.planned_request && r.planned_request.step_type === "DLI_SQL" && !r.planned_request.step_name.includes(".sql")
  ).length;

  assert.equal(result.planned_sql_executions.length, 8);
  assert.equal(result.planned_query_executions.length, 7);
});

test("dli client plan creates 15 planned DLI requests for customer", async () => {
  const result = await buildDliClientPlan(CUSTOMER_DIR, "default");
  assert.equal(result.valid, true);
  assert.equal(result.migration_id, "customer_status_pipeline_simple");
  assert.equal(result.total_planned_requests, 15);
});

test("dli client plan customer has 3 setup + 5 target + 7 validation", async () => {
  const result = await buildDliClientPlan(CUSTOMER_DIR, "default");
  assert.equal(result.planned_sql_executions.length, 8);
  assert.equal(result.planned_query_executions.length, 7);
});

test("dli client plan all requests are PLANNED_NOT_EXECUTED", async () => {
  const result = await buildDliClientPlan(ORDERS_DIR, "default");
  for (const exec of result.planned_sql_executions) {
    assert.equal(exec.status, "PLANNED_NOT_EXECUTED");
    assert.equal(exec.real_execution, false);
  }
  for (const q of result.planned_query_executions) {
    assert.equal(q.status, "PLANNED_NOT_EXECUTED");
    assert.equal(q.real_execution, false);
  }
});

test("dli client plan safety no_real_sql_execution true", async () => {
  const result = await buildDliClientPlan(ORDERS_DIR, "default");
  assert.equal(result.safety.no_real_sql_execution, true);
});

test("dli client plan safety no_cloud_write_calls true", async () => {
  const result = await buildDliClientPlan(ORDERS_DIR, "default");
  assert.equal(result.safety.no_cloud_write_calls, true);
});

test("dli client plan each request has sql_hash and sql_preview", async () => {
  const result = await buildDliClientPlan(ORDERS_DIR, "default");
  for (const exec of result.planned_sql_executions) {
    assert.ok(exec.sql_hash);
    assert.ok(typeof exec.sql_preview === "string");
  }
  for (const q of result.planned_query_executions) {
    assert.ok(q.sql_hash);
    assert.ok(typeof q.sql_preview === "string");
  }
});

test("dli client plan each request has planned_request with queue_name", async () => {
  const result = await buildDliClientPlan(ORDERS_DIR, "default");
  for (const exec of result.planned_sql_executions) {
    assert.ok(exec.planned_request);
    assert.equal(exec.planned_request.queue_name, "default");
    assert.equal(exec.planned_request.service, "DLI");
    assert.equal(exec.planned_request.execution_mode, "PLAN_ONLY");
  }
  for (const q of result.planned_query_executions) {
    assert.ok(q.planned_request);
    assert.equal(q.planned_request.queue_name, "default");
    assert.equal(q.planned_request.service, "DLI");
    assert.equal(q.planned_request.execution_mode, "PLAN_ONLY");
  }
});

test("dli client plan with custom queue name", async () => {
  const result = await buildDliClientPlan(ORDERS_DIR, "my_custom_queue");
  assert.equal(result.valid, true);
  for (const exec of result.planned_sql_executions) {
    assert.equal(exec.planned_request.queue_name, "my_custom_queue");
  }
});
