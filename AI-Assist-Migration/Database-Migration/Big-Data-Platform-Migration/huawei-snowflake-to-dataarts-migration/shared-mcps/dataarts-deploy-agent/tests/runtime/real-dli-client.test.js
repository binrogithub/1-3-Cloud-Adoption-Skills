const test = require("node:test");
const assert = require("node:assert/strict");
const {
  createRealDliClient,
  assertRealDliExecutionAllowed,
  buildDliSqlExecutionRequest,
  buildDliQueryRequest,
  validateRealDliClientConfig,
  createRealDliSafetyPolicy,
  hashSql,
  truncateSqlPreview,
} = require("../../src/runtime/dli/real-dli-client");
const { assertDliClient } = require("../../src/runtime/dli/dli-client-interface");

const ENV_KEYS = [
  "HUAWEI_REGION",
  "HUAWEI_PROJECT_ID",
  "HUAWEI_AK",
  "HUAWEI_SK",
  "DLI_QUEUE_NAME",
  "DATAARTS_WORKSPACE_ID",
];

function saveEnv() {
  const saved = {};
  for (const key of ENV_KEYS) {
    saved[key] = process.env[key];
    delete process.env[key];
  }
  return saved;
}

function restoreEnv(saved) {
  for (const key of ENV_KEYS) {
    if (saved[key] !== undefined) {
      process.env[key] = saved[key];
    } else {
      delete process.env[key];
    }
  }
}

test("createRealDliClient satisfies assertDliClient", () => {
  const client = createRealDliClient();
  assert.equal(assertDliClient(client), true);
});

test("default allowRealExecution is false", async () => {
  const client = createRealDliClient();
  const result = await client.executeSql({
    sql: "CREATE TABLE test (id INT)",
    queueName: "default",
    step: { name: "setup_01" },
  });
  assert.equal(result.real_execution, false);
});

test("executeSql returns PLANNED_NOT_EXECUTED by default", async () => {
  const client = createRealDliClient();
  const result = await client.executeSql({
    sql: "CREATE TABLE test (id INT)",
    queueName: "default",
    step: { name: "setup_01" },
  });
  assert.equal(result.status, "PLANNED_NOT_EXECUTED");
  assert.equal(result.statement_type, "EXECUTE_SQL");
  assert.equal(result.real_execution, false);
  assert.ok(result.job_id);
  assert.ok(result.sql_hash);
  assert.ok(result.sql_preview);
  assert.ok(result.planned_request);
});

test("querySql returns PLANNED_NOT_EXECUTED by default", async () => {
  const client = createRealDliClient();
  const result = await client.querySql({
    sql: "SELECT COUNT(*) AS actual_value FROM test",
    queueName: "default",
    step: { name: "test_count" },
  });
  assert.equal(result.status, "PLANNED_NOT_EXECUTED");
  assert.equal(result.statement_type, "QUERY");
  assert.equal(result.real_execution, false);
  assert.ok(result.job_id);
  assert.ok(result.sql_hash);
  assert.ok(result.planned_request);
});

test("allowRealExecution=true throws guardrail error without full flags", async () => {
  const client = createRealDliClient({ allowRealExecution: true });
  await assert.rejects(
    () => client.executeSql({ sql: "SELECT 1", queueName: "default", step: { name: "test" } }),
    { message: "Native DLI real execution requires --confirm-native-dli" }
  );
  await assert.rejects(
    () => client.querySql({ sql: "SELECT 1", queueName: "default", step: { name: "test" } }),
    { message: "Native DLI real execution requires --confirm-native-dli" }
  );
  await assert.rejects(
    () => client.getJobStatus({ jobId: "123" }),
    { message: "Native DLI real execution requires --confirm-native-dli" }
  );
  await assert.rejects(
    () => client.getJobResult({ jobId: "123" }),
    { message: "Native DLI real execution requires --confirm-native-dli" }
  );
});

test("request builders include queue name and sql hash", () => {
  const req = buildDliSqlExecutionRequest({
    sql: "SELECT 1",
    queueName: "my_queue",
    step: { name: "step1", type: "DLI_SQL" },
  });
  assert.equal(req.queue_name, "my_queue");
  assert.ok(req.sql_hash);
  assert.equal(req.service, "DLI");
  assert.equal(req.operation, "executeSql");
  assert.equal(req.execution_mode, "PLAN_ONLY");

  const qReq = buildDliQueryRequest({
    sql: "SELECT COUNT(*) FROM t",
    queueName: "default",
    step: { name: "q1", type: "DLI_QUERY" },
  });
  assert.equal(qReq.queue_name, "default");
  assert.ok(qReq.sql_hash);
  assert.equal(qReq.operation, "querySql");
});

test("SQL preview is truncated and does not expose excessive content", async () => {
  const longSql = "SELECT " + "a".repeat(500) + " FROM very_long_table_name";
  const client = createRealDliClient();
  const result = await client.executeSql({
    sql: longSql,
    queueName: "default",
    step: { name: "long_sql" },
  });
  assert.ok(result.sql_preview.length <= 123);
  assert.ok(result.sql_preview.endsWith("..."));
  assert.ok(!result.sql_preview.includes("\n"));
});

test("validateRealDliClientConfig does not expose secrets", () => {
  const saved = saveEnv();
  try {
    const config = {
      HUAWEI_REGION: "cn-north-7",
      HUAWEI_PROJECT_ID: "proj-123",
      HUAWEI_AK: "MY_ACCESS_KEY",
      HUAWEI_SK: "MY_SECRET_KEY",
      DLI_QUEUE_NAME: "default",
      DATAARTS_WORKSPACE_ID: "ws-123",
    };
    const result = validateRealDliClientConfig({ config, envFilePath: "/nonexistent/.env.dataarts" });
    assert.equal(result.valid, true);
    assert.equal(result.has_ak, true);
    assert.equal(result.has_sk, true);
    assert.equal(result.region, "cn-north-7");
    assert.equal(result.dli_queue, "default");
    assert.ok(!JSON.stringify(result).includes("MY_ACCESS_KEY"));
    assert.ok(!JSON.stringify(result).includes("MY_SECRET_KEY"));
    assert.ok(result.source_map);
    assert.ok(result.masked_config);
  } finally {
    restoreEnv(saved);
  }
});

test("validateRealDliClientConfig reports missing required fields", () => {
  const saved = saveEnv();

  try {
    const result = validateRealDliClientConfig({ config: {}, envFilePath: "/nonexistent/.env.dataarts" });
    assert.equal(result.valid, false);
    assert.ok(result.errors.length > 0);
    assert.ok(result.errors.some((e) => e.includes("HUAWEI_REGION")));
    assert.ok(result.errors.some((e) => e.includes("HUAWEI_PROJECT_ID")));
    assert.ok(result.errors.some((e) => e.includes("HUAWEI_AK")));
    assert.ok(result.errors.some((e) => e.includes("HUAWEI_SK")));
  } finally {
    restoreEnv(saved);
  }
});

test("validateRealDliClientConfig warns about missing workspace id", () => {
  const saved = saveEnv();
  try {
    const config = {
      HUAWEI_REGION: "cn-north-7",
      HUAWEI_PROJECT_ID: "proj-123",
      HUAWEI_AK: "ak",
      HUAWEI_SK: "sk",
    };
    const result = validateRealDliClientConfig({ config, envFilePath: "/nonexistent/.env.dataarts" });
    assert.equal(result.valid, true);
    assert.ok(result.warnings.some((w) => w.includes("DATAARTS_WORKSPACE_ID")));
  } finally {
    restoreEnv(saved);
  }
});

test("validateRealDliClientConfig detects .env.dataarts credentials", () => {
  const fs = require("fs");
  const path = require("path");
  const os = require("os");
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "dli-dotenv-test-"));
  const envPath = path.join(tmpDir, ".env.dataarts");
  fs.writeFileSync(envPath, "HUAWEI_REGION=cn-north-7\nHUAWEI_PROJECT_ID=proj-dotenv\nHUAWEI_AK=dotenv-ak\nHUAWEI_SK=dotenv-sk\nDATAARTS_WORKSPACE_ID=ws-dotenv\nDLI_QUEUE_NAME=dotenv-queue\n", "utf-8");

  const saved = saveEnv();

  try {
    const result = validateRealDliClientConfig({ config: {}, envFilePath: envPath });
    assert.equal(result.valid, true);
    assert.equal(result.region, "cn-north-7");
    assert.equal(result.has_ak, true);
    assert.equal(result.has_sk, true);
    assert.equal(result.source_map.HUAWEI_REGION, ".env.dataarts");
    assert.equal(result.source_map.HUAWEI_AK, ".env.dataarts");
    assert.equal(result.env_file_status, ".env.dataarts");
  } finally {
    restoreEnv(saved);
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

test("validateRealDliClientConfig includes source_map and masked_config", () => {
  const saved = saveEnv();
  try {
    const config = {
      HUAWEI_REGION: "cn-north-7",
      HUAWEI_PROJECT_ID: "proj-123",
      HUAWEI_AK: "test_ak",
      HUAWEI_SK: "test_sk",
      DATAARTS_WORKSPACE_ID: "ws-123",
    };
    const result = validateRealDliClientConfig({ config, envFilePath: "/nonexistent/.env.dataarts" });
    assert.ok(result.source_map);
    assert.ok(result.masked_config);
    assert.equal(result.masked_config.ak_present, "PRESENT");
    assert.equal(result.masked_config.sk_present, "PRESENT");
    const json = JSON.stringify(result);
    assert.ok(!json.includes("test_ak"));
    assert.ok(!json.includes("test_sk"));
  } finally {
    restoreEnv(saved);
  }
});

test("safety policy has no_real_sql_execution and no_cloud_write_calls", () => {
  const safety = createRealDliSafetyPolicy();
  assert.equal(safety.no_real_sql_execution, true);
  assert.equal(safety.no_cloud_write_calls, true);
  assert.equal(safety.no_runtime_execution, true);
  assert.equal(safety.no_confirm, true);
  assert.equal(safety.real_dli_client_scaffold, true);
  assert.equal(safety.plan_only, true);
  assert.equal(safety.secrets_redacted, true);
});

test("hashSql produces consistent 16-char hash", () => {
  const h1 = hashSql("SELECT 1");
  const h2 = hashSql("SELECT 1");
  const h3 = hashSql("SELECT 2");
  assert.equal(h1, h2);
  assert.notEqual(h1, h3);
  assert.equal(h1.length, 16);
});

test("truncateSqlPreview handles null and empty", () => {
  assert.equal(truncateSqlPreview(null), "");
  assert.equal(truncateSqlPreview(""), "");
  assert.equal(truncateSqlPreview(undefined), "");
});

test("getJobStatus returns PLANNED_NOT_EXECUTED", async () => {
  const client = createRealDliClient();
  const result = await client.getJobStatus({ jobId: "test_job" });
  assert.equal(result.status, "PLANNED_NOT_EXECUTED");
  assert.equal(result.real_execution, false);
});

test("getJobResult returns PLANNED_NOT_EXECUTED", async () => {
  const client = createRealDliClient();
  const result = await client.getJobResult({ jobId: "test_job" });
  assert.equal(result.status, "PLANNED_NOT_EXECUTED");
  assert.equal(result.real_execution, false);
  assert.deepEqual(result.rows, []);
  assert.deepEqual(result.column_names, []);
});

test("executeSql includes step info in result", async () => {
  const client = createRealDliClient();
  const result = await client.executeSql({
    sql: "DROP TABLE IF EXISTS t",
    queueName: "my_queue",
    step: { name: "drop_t", type: "DLI_SQL" },
  });
  assert.equal(result.step_name, "drop_t");
  assert.equal(result.step_type, "DLI_SQL");
  assert.equal(result.queue_name, "my_queue");
});

test("querySql includes step info in result", async () => {
  const client = createRealDliClient();
  const result = await client.querySql({
    sql: "SELECT COUNT(*) FROM t",
    queueName: "default",
    step: { name: "count_t", type: "DLI_QUERY" },
  });
  assert.equal(result.step_name, "count_t");
  assert.equal(result.step_type, "DLI_QUERY");
});

test("executeSql refuses without confirmNativeDli", async () => {
  const client = createRealDliClient({ allowRealExecution: true, confirmNativeDli: false, understandExecutesSql: true });
  await assert.rejects(
    () => client.executeSql({ sql: "SELECT 1", queueName: "default", step: { name: "test" } }),
    { message: "Native DLI real execution requires --confirm-native-dli" }
  );
});

test("executeSql refuses without understandExecutesSql", async () => {
  const client = createRealDliClient({ allowRealExecution: true, confirmNativeDli: true, understandExecutesSql: false });
  await assert.rejects(
    () => client.executeSql({ sql: "SELECT 1", queueName: "default", step: { name: "test" } }),
    { message: "Native DLI real execution requires --i-understand-this-executes-sql" }
  );
});

test("querySql refuses without confirmNativeDli", async () => {
  const client = createRealDliClient({ allowRealExecution: true, confirmNativeDli: false, understandExecutesSql: true });
  await assert.rejects(
    () => client.querySql({ sql: "SELECT 1", queueName: "default", step: { name: "test" } }),
    { message: "Native DLI real execution requires --confirm-native-dli" }
  );
});

test("with all guarded flags executeSql returns NATIVE_DLI_TRANSPORT_NOT_CONFIGURED", async () => {
  const saved = saveEnv();
  try {
    const client = createRealDliClient({ allowRealExecution: true, confirmNativeDli: true, understandExecutesSql: true, envFilePath: "/nonexistent/.env.dataarts" });
    const result = await client.executeSql({ sql: "SELECT 1", queueName: "default", step: { name: "test" } });
    assert.equal(result.status, "NATIVE_DLI_TRANSPORT_NOT_CONFIGURED");
    assert.equal(result.valid, false);
    assert.equal(result.real_execution, false);
  } finally {
    restoreEnv(saved);
  }
});

test("with all guarded flags querySql returns NATIVE_DLI_TRANSPORT_NOT_CONFIGURED", async () => {
  const saved = saveEnv();
  try {
    const client = createRealDliClient({ allowRealExecution: true, confirmNativeDli: true, understandExecutesSql: true, envFilePath: "/nonexistent/.env.dataarts" });
    const result = await client.querySql({ sql: "SELECT 1", queueName: "default", step: { name: "test" } });
    assert.equal(result.status, "NATIVE_DLI_TRANSPORT_NOT_CONFIGURED");
    assert.equal(result.valid, false);
    assert.equal(result.real_execution, false);
  } finally {
    restoreEnv(saved);
  }
});

test("with all guarded flags getJobStatus returns NATIVE_DLI_TRANSPORT_NOT_CONFIGURED", async () => {
  const saved = saveEnv();
  try {
    const client = createRealDliClient({ allowRealExecution: true, confirmNativeDli: true, understandExecutesSql: true, envFilePath: "/nonexistent/.env.dataarts" });
    const result = await client.getJobStatus({ jobId: "123" });
    assert.equal(result.status, "NATIVE_DLI_TRANSPORT_NOT_CONFIGURED");
    assert.equal(result.valid, false);
    assert.equal(result.real_execution, false);
  } finally {
    restoreEnv(saved);
  }
});

test("with all guarded flags getJobResult returns NATIVE_DLI_TRANSPORT_NOT_CONFIGURED", async () => {
  const saved = saveEnv();
  try {
    const client = createRealDliClient({ allowRealExecution: true, confirmNativeDli: true, understandExecutesSql: true, envFilePath: "/nonexistent/.env.dataarts" });
    const result = await client.getJobResult({ jobId: "123" });
    assert.equal(result.status, "NATIVE_DLI_TRANSPORT_NOT_CONFIGURED");
    assert.equal(result.valid, false);
    assert.equal(result.real_execution, false);
  } finally {
    restoreEnv(saved);
  }
});

test("assertRealDliExecutionAllowed with all flags returns allowed", () => {
  const result = assertRealDliExecutionAllowed({
    allowRealExecution: true,
    confirmNativeDli: true,
    understandExecutesSql: true,
  });
  assert.equal(result.allowed, true);
  assert.deepEqual(result.errors, []);
});

test("assertRealDliExecutionAllowed without allowRealExecution", () => {
  const result = assertRealDliExecutionAllowed({
    confirmNativeDli: true,
    understandExecutesSql: true,
  });
  assert.equal(result.allowed, false);
  assert.ok(result.errors.some((e) => e.includes("allowRealExecution=true")));
});

test("assertRealDliExecutionAllowed without confirmNativeDli", () => {
  const result = assertRealDliExecutionAllowed({
    allowRealExecution: true,
    understandExecutesSql: true,
  });
  assert.equal(result.allowed, false);
  assert.ok(result.errors.some((e) => e.includes("--confirm-native-dli")));
});

test("assertRealDliExecutionAllowed without understandExecutesSql", () => {
  const result = assertRealDliExecutionAllowed({
    allowRealExecution: true,
    confirmNativeDli: true,
  });
  assert.equal(result.allowed, false);
  assert.ok(result.errors.some((e) => e.includes("--i-understand-this-executes-sql")));
});

test("executeSql refuses without allowRealExecution when confirmNativeDli is true", async () => {
  const client = createRealDliClient({ allowRealExecution: false, confirmNativeDli: true, understandExecutesSql: true });
  const result = await client.executeSql({ sql: "SELECT 1", queueName: "default", step: { name: "test" } });
  assert.equal(result.status, "PLANNED_NOT_EXECUTED");
  assert.equal(result.real_execution, false);
});

test("real-dli-client calls transport.submitSqlJob only when all flags present", async () => {
  const fakeHttpClient = {
    submitSqlJob: async ({ sql, queueName, step }) => ({
      status: "SUBMITTED",
      job_id: "transport_job_1",
      real_execution: true,
    }),
    getSqlJobStatus: async ({ jobId }) => ({
      status: "FINISHED",
      job_id: jobId,
      real_execution: true,
    }),
    getSqlJobResult: async ({ jobId }) => ({
      status: "FINISHED",
      job_id: jobId,
      real_execution: true,
      rows: [],
      column_names: [],
    }),
  };

  const client = createRealDliClient({
    allowRealExecution: true,
    confirmNativeDli: true,
    understandExecutesSql: true,
    httpClient: fakeHttpClient,
  });

  const result = await client.executeSql({ sql: "SELECT 1", queueName: "default", step: { name: "test" } });
  assert.equal(result.status, "FINISHED");
  assert.equal(result.real_execution, true);
  assert.equal(result.job_id, "transport_job_1");
});

test("real-dli-client propagates NOT_CONFIGURED cleanly", async () => {
  const saved = saveEnv();
  try {
    const client = createRealDliClient({
      allowRealExecution: true,
      confirmNativeDli: true,
      understandExecutesSql: true,
      envFilePath: "/nonexistent/.env.dataarts",
    });

    const result = await client.executeSql({ sql: "SELECT 1", queueName: "default", step: { name: "test" } });
    assert.equal(result.status, "NATIVE_DLI_TRANSPORT_NOT_CONFIGURED");
    assert.equal(result.real_execution, false);
    assert.equal(result.valid, false);
  } finally {
    restoreEnv(saved);
  }
});

test("real-dli-client propagates NOT_IMPLEMENTED cleanly", async () => {
  const fakeHttpClient = { someOtherMethod: async () => {} };
  const client = createRealDliClient({
    allowRealExecution: true,
    confirmNativeDli: true,
    understandExecutesSql: true,
    httpClient: fakeHttpClient,
  });

  const result = await client.executeSql({ sql: "SELECT 1", queueName: "default", step: { name: "test" } });
  assert.equal(result.status, "NATIVE_DLI_TRANSPORT_NOT_IMPLEMENTED");
  assert.equal(result.real_execution, false);
  assert.equal(result.valid, false);
});

test("real-dli-client querySql with transport returns FINISHED with rows", async () => {
  const fakeHttpClient = {
    submitSqlJob: async ({ sql, queueName, step }) => ({
      status: "SUBMITTED",
      job_id: "query_job_1",
      real_execution: true,
    }),
    getSqlJobStatus: async ({ jobId }) => ({
      status: "FINISHED",
      job_id: jobId,
      real_execution: true,
    }),
    getSqlJobResult: async ({ jobId }) => ({
      status: "FINISHED",
      job_id: jobId,
      real_execution: true,
      rows: [{ actual_value: 100 }],
      column_names: ["actual_value"],
    }),
  };

  const client = createRealDliClient({
    allowRealExecution: true,
    confirmNativeDli: true,
    understandExecutesSql: true,
    httpClient: fakeHttpClient,
  });

  const result = await client.querySql({ sql: "SELECT COUNT(*) AS actual_value FROM t", queueName: "default", step: { name: "count_t" } });
  assert.equal(result.status, "FINISHED");
  assert.equal(result.real_execution, true);
  assert.deepEqual(result.rows, [{ actual_value: 100 }]);
});

test("real-dli-client getJobStatus with transport returns FINISHED", async () => {
  const fakeHttpClient = {
    getSqlJobStatus: async ({ jobId }) => ({
      status: "FINISHED",
      job_id: jobId,
      real_execution: true,
    }),
  };

  const client = createRealDliClient({
    allowRealExecution: true,
    confirmNativeDli: true,
    understandExecutesSql: true,
    httpClient: fakeHttpClient,
  });

  const result = await client.getJobStatus({ jobId: "job123" });
  assert.equal(result.status, "FINISHED");
  assert.equal(result.real_execution, true);
});

test("real-dli-client getJobResult with transport returns rows", async () => {
  const fakeHttpClient = {
    getSqlJobResult: async ({ jobId }) => ({
      status: "FINISHED",
      job_id: jobId,
      real_execution: true,
      rows: [{ col1: "val1" }],
      column_names: ["col1"],
    }),
  };

  const client = createRealDliClient({
    allowRealExecution: true,
    confirmNativeDli: true,
    understandExecutesSql: true,
    httpClient: fakeHttpClient,
  });

  const result = await client.getJobResult({ jobId: "job123" });
  assert.equal(result.status, "FINISHED");
  assert.equal(result.real_execution, true);
  assert.deepEqual(result.rows, [{ col1: "val1" }]);
});

test("real-dli-client exposes _transport", () => {
  const client = createRealDliClient();
  assert.ok(client._transport);
  assert.equal(typeof client._transport.submitSqlJob, "function");
  assert.equal(typeof client._transport.getSqlJobStatus, "function");
  assert.equal(typeof client._transport.getSqlJobResult, "function");
});
