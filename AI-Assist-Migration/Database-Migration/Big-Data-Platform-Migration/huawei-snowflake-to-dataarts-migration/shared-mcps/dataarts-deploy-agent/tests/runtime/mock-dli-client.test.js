const test = require("node:test");
const assert = require("node:assert/strict");
const { createMockDliClient, hashSql } = require("../../src/runtime/dli/mock-dli-client");

const VALIDATION_QUERIES = [
  {
    id: "raw_orders_count",
    type: "TABLE_COUNT",
    object_name: "RAW_ORDERS",
    sql: "SELECT COUNT(*) AS actual_value FROM demo_migration.raw_orders",
    expected: 5,
  },
  {
    id: "task_audit_success_count",
    type: "TABLE_COUNT",
    object_name: "TASK_AUDIT_SUCCESS",
    sql: "SELECT COUNT(*) AS actual_value FROM demo_migration.task_audit WHERE status = 'SUCCESS'",
    expected: ">=1",
  },
  {
    id: "aggregate_2026_06_20",
    type: "AGGREGATE_CHECK",
    object_name: "2026-06-20",
    sql: "SELECT order_count, total_amount FROM demo_migration.gold_daily_sales WHERE order_date = '2026-06-20'",
    expected: { order_count: 2, total_amount: 420.50 },
  },
  {
    id: "final_equivalence",
    type: "FINAL_EQUIVALENCE",
    object_name: "SNOWFLAKE_TO_DATAARTS",
    sql: "SELECT 'EQUIVALENT' AS actual_value",
    expected: "EQUIVALENT",
  },
];

test("mock client executeSql returns mocked FINISHED result", () => {
  const client = createMockDliClient({ validationQueries: VALIDATION_QUERIES });
  const result = client.executeSql({
    sql: "CREATE TABLE test (id INT)",
    queueName: "default",
    step: { name: "setup_01" },
  });

  assert.equal(result.status, "FINISHED");
  assert.equal(result.statement_type, "EXECUTE_SQL");
  assert.equal(result.mocked, true);
  assert.equal(result.simulated, false);
  assert.ok(result.job_id);
  assert.ok(result.sql_hash);
});

test("mock client querySql returns expected scalar result for TABLE_COUNT", () => {
  const client = createMockDliClient({ validationQueries: VALIDATION_QUERIES });
  const result = client.querySql({
    sql: "SELECT COUNT(*) AS actual_value FROM demo_migration.raw_orders",
    queueName: "default",
    step: { name: "raw_orders_count" },
  });

  assert.equal(result.status, "FINISHED");
  assert.equal(result.mocked, true);
  assert.equal(result.rows[0].actual_value, 5);
});

test("mock client querySql handles >=1 expected values", () => {
  const client = createMockDliClient({ validationQueries: VALIDATION_QUERIES });
  const result = client.querySql({
    sql: "SELECT COUNT(*) AS actual_value FROM demo_migration.task_audit WHERE status = 'SUCCESS'",
    queueName: "default",
    step: { name: "task_audit_success_count" },
  });

  assert.equal(result.status, "FINISHED");
  assert.ok(result.rows[0].actual_value >= 1);
});

test("mock client querySql returns expected object result for AGGREGATE_CHECK", () => {
  const client = createMockDliClient({ validationQueries: VALIDATION_QUERIES });
  const result = client.querySql({
    sql: "SELECT order_count, total_amount FROM demo_migration.gold_daily_sales WHERE order_date = '2026-06-20'",
    queueName: "default",
    step: { name: "aggregate_2026_06_20" },
  });

  assert.equal(result.status, "FINISHED");
  assert.equal(result.mocked, true);
  assert.equal(result.rows[0].order_count, 2);
  assert.equal(result.rows[0].total_amount, 420.50);
});

test("mock client querySql returns expected result for FINAL_EQUIVALENCE", () => {
  const client = createMockDliClient({ validationQueries: VALIDATION_QUERIES });
  const result = client.querySql({
    sql: "SELECT 'EQUIVALENT' AS actual_value",
    queueName: "default",
    step: { name: "final_equivalence" },
  });

  assert.equal(result.status, "FINISHED");
  assert.equal(result.rows[0].actual_value, "EQUIVALENT");
});

test("mock client can simulate query mismatch via failQueryId", () => {
  const client = createMockDliClient({
    validationQueries: VALIDATION_QUERIES,
    failQueryId: "raw_orders_count",
  });
  const result = client.querySql({
    sql: "SELECT COUNT(*) AS actual_value FROM demo_migration.raw_orders",
    queueName: "default",
    step: { name: "raw_orders_count" },
  });

  assert.equal(result.status, "FINISHED");
  assert.equal(result.rows[0].actual_value, -999);
});

test("mock client can simulate step failure via failStepId", () => {
  const client = createMockDliClient({
    validationQueries: VALIDATION_QUERIES,
    failStepId: "setup_01",
  });
  const result = client.executeSql({
    sql: "CREATE TABLE test (id INT)",
    queueName: "default",
    step: { name: "setup_01" },
  });

  assert.equal(result.status, "FAILED");
  assert.equal(result.mocked, true);
  assert.ok(result.error);
});

test("mock client getJobStatus returns FINISHED", () => {
  const client = createMockDliClient({ validationQueries: VALIDATION_QUERIES });
  const result = client.getJobStatus({ jobId: "mock_job_1" });

  assert.equal(result.status, "FINISHED");
  assert.equal(result.mocked, true);
});

test("mock client getJobResult returns FINISHED", () => {
  const client = createMockDliClient({ validationQueries: VALIDATION_QUERIES });
  const result = client.getJobResult({ jobId: "mock_job_1" });

  assert.equal(result.status, "FINISHED");
  assert.equal(result.mocked, true);
});

test("hashSql produces consistent hash", () => {
  const h1 = hashSql("SELECT 1");
  const h2 = hashSql("SELECT 1");
  const h3 = hashSql("SELECT 2");
  assert.equal(h1, h2);
  assert.notEqual(h1, h3);
});

test("mock client with no validationQueries returns empty rows for unknown query", () => {
  const client = createMockDliClient({});
  const result = client.querySql({
    sql: "SELECT COUNT(*) AS actual_value FROM unknown",
    queueName: "default",
    step: { name: "unknown_query" },
  });

  assert.equal(result.status, "FINISHED");
  assert.deepEqual(result.rows, []);
});
