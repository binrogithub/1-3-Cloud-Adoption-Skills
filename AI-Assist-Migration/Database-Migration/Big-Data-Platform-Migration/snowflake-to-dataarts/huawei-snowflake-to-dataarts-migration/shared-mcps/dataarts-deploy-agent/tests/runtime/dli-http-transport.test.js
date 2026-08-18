const test = require("node:test");
const assert = require("node:assert/strict");
const {
  createDliHttpTransport,
  buildDliSqlJobRequest,
  buildDliJobStatusRequest,
  buildDliJobResultRequest,
  assertDliTransportSafety,
  pollJobStatus,
  hashSql,
  truncateSqlPreview,
} = require("../../src/runtime/dli/dli-http-transport");

test("transport refuses execution without allowRealExecution", async () => {
  const transport = createDliHttpTransport({
    allowRealExecution: false,
    confirmNativeDli: true,
    understandExecutesSql: true,
  });
  const result = await transport.submitSqlJob({ sql: "SELECT 1", queueName: "default" });
  assert.equal(result.status, "TRANSPORT_GUARDRAIL_BLOCKED");
  assert.equal(result.real_execution, false);
  assert.ok(result.guard_errors.some((e) => e.includes("allowRealExecution=true")));
});

test("transport refuses without confirmNativeDli", async () => {
  const transport = createDliHttpTransport({
    allowRealExecution: true,
    confirmNativeDli: false,
    understandExecutesSql: true,
  });
  const result = await transport.submitSqlJob({ sql: "SELECT 1", queueName: "default" });
  assert.equal(result.status, "TRANSPORT_GUARDRAIL_BLOCKED");
  assert.equal(result.real_execution, false);
  assert.ok(result.guard_errors.some((e) => e.includes("--confirm-native-dli")));
});

test("transport refuses without understandExecutesSql", async () => {
  const transport = createDliHttpTransport({
    allowRealExecution: true,
    confirmNativeDli: true,
    understandExecutesSql: false,
  });
  const result = await transport.submitSqlJob({ sql: "SELECT 1", queueName: "default" });
  assert.equal(result.status, "TRANSPORT_GUARDRAIL_BLOCKED");
  assert.equal(result.real_execution, false);
  assert.ok(result.guard_errors.some((e) => e.includes("--i-understand-this-executes-sql")));
});

test("transport returns planned request in plan-only mode", async () => {
  const transport = createDliHttpTransport({
    allowRealExecution: false,
    confirmNativeDli: false,
    understandExecutesSql: false,
    config: { region: "cn-north-7", projectId: "proj-123" },
  });
  const result = await transport.submitSqlJob({ sql: "SELECT 1", queueName: "default" });
  assert.equal(result.status, "TRANSPORT_GUARDRAIL_BLOCKED");
  assert.ok(result.planned_request);
  assert.equal(result.planned_request.service, "DLI");
  assert.equal(result.planned_request.operation, "submitSqlJob");
  assert.equal(result.planned_request.method, "POST");
  assert.equal(result.planned_request.region, "cn-north-7");
  assert.equal(result.planned_request.project_id, "proj-123");
});

test("transport uses injected httpClient in real guarded mode", async () => {
  const fakeClient = {
    submitSqlJob: async ({ sql, queueName, step }) => ({
      status: "SUBMITTED",
      job_id: "fake_job_123",
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
      rows: [{ actual_value: 42 }],
      column_names: ["actual_value"],
    }),
  };

  const transport = createDliHttpTransport({
    allowRealExecution: true,
    confirmNativeDli: true,
    understandExecutesSql: true,
    httpClient: fakeClient,
    config: { region: "cn-north-7", projectId: "proj-123" },
  });

  const result = await transport.submitSqlJob({ sql: "SELECT 1", queueName: "default" });
  assert.equal(result.status, "SUBMITTED");
  assert.equal(result.job_id, "fake_job_123");
  assert.equal(result.real_execution, true);

  const statusResult = await transport.getSqlJobStatus({ jobId: "fake_job_123" });
  assert.equal(statusResult.status, "FINISHED");
  assert.equal(statusResult.real_execution, true);

  const resultData = await transport.getSqlJobResult({ jobId: "fake_job_123" });
  assert.equal(resultData.status, "FINISHED");
  assert.deepEqual(resultData.rows, [{ actual_value: 42 }]);
});

test("transport does not expose secrets in errors/output", async () => {
  const transport = createDliHttpTransport({
    allowRealExecution: true,
    confirmNativeDli: true,
    understandExecutesSql: true,
    config: { region: "cn-north-7", projectId: "proj-123", ak: "SECRET_AK_12345", sk: "SECRET_SK_67890" },
  });

  const result = await transport.submitSqlJob({ sql: "SELECT 1", queueName: "default" });
  const json = JSON.stringify(result);
  assert.ok(!json.includes("SECRET_AK_12345"));
  assert.ok(!json.includes("SECRET_SK_67890"));
});

test("transport returns NOT_CONFIGURED when no httpClient and no AK/SK", async () => {
  const transport = createDliHttpTransport({
    allowRealExecution: true,
    confirmNativeDli: true,
    understandExecutesSql: true,
    config: { region: "cn-north-7", projectId: "proj-123" },
  });
  const result = await transport.submitSqlJob({ sql: "SELECT 1", queueName: "default" });
  assert.equal(result.status, "NATIVE_DLI_TRANSPORT_NOT_CONFIGURED");
  assert.equal(result.real_execution, false);
});

test("transport getSqlJobStatus returns planned when guardrails block", async () => {
  const transport = createDliHttpTransport({
    allowRealExecution: false,
    confirmNativeDli: false,
    understandExecutesSql: false,
    config: { region: "cn-north-7", projectId: "proj-123" },
  });
  const result = await transport.getSqlJobStatus({ jobId: "job123" });
  assert.equal(result.status, "TRANSPORT_GUARDRAIL_BLOCKED");
  assert.equal(result.real_execution, false);
  assert.ok(result.planned_request);
  assert.equal(result.planned_request.operation, "getSqlJobStatus");
});

test("transport getSqlJobResult returns planned when guardrails block", async () => {
  const transport = createDliHttpTransport({
    allowRealExecution: false,
    confirmNativeDli: false,
    understandExecutesSql: false,
    config: { region: "cn-north-7", projectId: "proj-123" },
  });
  const result = await transport.getSqlJobResult({ jobId: "job123" });
  assert.equal(result.status, "TRANSPORT_GUARDRAIL_BLOCKED");
  assert.equal(result.real_execution, false);
  assert.deepEqual(result.rows, []);
  assert.ok(result.planned_request);
  assert.equal(result.planned_request.operation, "getSqlJobResult");
});

test("buildDliSqlJobRequest constructs correct request", () => {
  const req = buildDliSqlJobRequest({
    sql: "SELECT COUNT(*) FROM test",
    queueName: "my_queue",
    region: "cn-north-7",
    projectId: "proj-123",
  });
  assert.equal(req.service, "DLI");
  assert.equal(req.operation, "submitSqlJob");
  assert.equal(req.method, "POST");
  assert.equal(req.region, "cn-north-7");
  assert.equal(req.project_id, "proj-123");
  assert.equal(req.queue_name, "my_queue");
  assert.ok(req.url);
  assert.ok(req.url.includes("dli.cn-north-7.myhuaweicloud.com"));
  assert.ok(req.url.includes("/v1.0/proj-123/jobs/submit-job"));
  assert.ok(req.sql_hash);
  assert.equal(req.execution_mode, "PLAN_ONLY");
  assert.ok(req.body_keys.includes("sql"));
  assert.ok(req.body_keys.includes("queue_name"));
});

test("buildDliSqlJobRequest includes database when provided", () => {
  const req = buildDliSqlJobRequest({
    sql: "SELECT 1",
    queueName: "default",
    region: "cn-north-7",
    projectId: "proj-123",
    database: "demo_migration",
  });
  assert.ok(req.body_keys.includes("currentdb"));
});

test("buildDliJobStatusRequest constructs correct request", () => {
  const req = buildDliJobStatusRequest({
    jobId: "abc-123",
    region: "cn-north-7",
    projectId: "proj-123",
  });
  assert.equal(req.service, "DLI");
  assert.equal(req.operation, "getSqlJobStatus");
  assert.equal(req.method, "GET");
  assert.equal(req.job_id, "abc-123");
  assert.ok(req.url);
  assert.ok(req.url.includes("job_id=abc-123"));
  assert.equal(req.execution_mode, "PLAN_ONLY");
});

test("buildDliJobResultRequest constructs correct request", () => {
  const req = buildDliJobResultRequest({
    jobId: "abc-123",
    region: "cn-north-7",
    projectId: "proj-123",
  });
  assert.equal(req.service, "DLI");
  assert.equal(req.operation, "getSqlJobResult");
  assert.equal(req.method, "GET");
  assert.equal(req.job_id, "abc-123");
  assert.ok(req.url);
  assert.ok(req.url.includes("/jobs/abc-123"));
  assert.equal(req.execution_mode, "PLAN_ONLY");
});

test("buildDliSqlJobRequest handles missing region/projectId", () => {
  const req = buildDliSqlJobRequest({ sql: "SELECT 1" });
  assert.equal(req.endpoint, null);
  assert.equal(req.path, null);
  assert.equal(req.url, null);
  assert.equal(req.region, null);
  assert.equal(req.project_id, null);
});

test("assertDliTransportSafety with all flags", () => {
  const result = assertDliTransportSafety({
    allowRealExecution: true,
    confirmNativeDli: true,
    understandExecutesSql: true,
  });
  assert.equal(result.safe, true);
  assert.deepEqual(result.errors, []);
});

test("assertDliTransportSafety without allowRealExecution", () => {
  const result = assertDliTransportSafety({
    confirmNativeDli: true,
    understandExecutesSql: true,
  });
  assert.equal(result.safe, false);
  assert.ok(result.errors.some((e) => e.includes("allowRealExecution=true")));
});

test("assertDliTransportSafety without confirmNativeDli", () => {
  const result = assertDliTransportSafety({
    allowRealExecution: true,
    understandExecutesSql: true,
  });
  assert.equal(result.safe, false);
  assert.ok(result.errors.some((e) => e.includes("--confirm-native-dli")));
});

test("assertDliTransportSafety without understandExecutesSql", () => {
  const result = assertDliTransportSafety({
    allowRealExecution: true,
    confirmNativeDli: true,
  });
  assert.equal(result.safe, false);
  assert.ok(result.errors.some((e) => e.includes("--i-understand-this-executes-sql")));
});

test("assertDliTransportSafety with no flags", () => {
  const result = assertDliTransportSafety({});
  assert.equal(result.safe, false);
  assert.equal(result.errors.length, 3);
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

test("truncateSqlPreview truncates long SQL", () => {
  const longSql = "SELECT " + "a".repeat(500) + " FROM t";
  const preview = truncateSqlPreview(longSql);
  assert.ok(preview.length <= 123);
  assert.ok(preview.endsWith("..."));
});

test("transport _isRealExecutionAllowed reflects flags", () => {
  const t1 = createDliHttpTransport({ allowRealExecution: true, confirmNativeDli: true, understandExecutesSql: true });
  assert.equal(t1._isRealExecutionAllowed, true);

  const t2 = createDliHttpTransport({ allowRealExecution: false, confirmNativeDli: true, understandExecutesSql: true });
  assert.equal(t2._isRealExecutionAllowed, false);
});

test("transport _effectiveHttpClient with injected client", () => {
  const fakeClient = { submitSqlJob: async () => {} };
  const transport = createDliHttpTransport({
    allowRealExecution: true,
    confirmNativeDli: true,
    understandExecutesSql: true,
    httpClient: fakeClient,
  });
  assert.equal(transport._effectiveHttpClient, fakeClient);
});

test("transport _effectiveHttpClient with AK/SK", () => {
  const transport = createDliHttpTransport({
    allowRealExecution: true,
    confirmNativeDli: true,
    understandExecutesSql: true,
    config: { ak: "test_ak", sk: "test_sk" },
  });
  assert.equal(transport._effectiveHttpClient, "REAL_HUAWEI_SIGNER");
});

test("transport _effectiveHttpClient with nothing", () => {
  const transport = createDliHttpTransport({
    allowRealExecution: true,
    confirmNativeDli: true,
    understandExecutesSql: true,
  });
  assert.equal(transport._effectiveHttpClient, null);
});

test("transport getSqlJobStatus with injected httpClient", async () => {
  const fakeClient = {
    getSqlJobStatus: async ({ jobId }) => ({
      status: "FINISHED",
      job_id: jobId,
      real_execution: true,
    }),
  };
  const transport = createDliHttpTransport({
    allowRealExecution: true,
    confirmNativeDli: true,
    understandExecutesSql: true,
    httpClient: fakeClient,
    config: { region: "cn-north-7", projectId: "proj-123" },
  });
  const result = await transport.getSqlJobStatus({ jobId: "job456" });
  assert.equal(result.status, "FINISHED");
  assert.equal(result.real_execution, true);
});

test("transport getSqlJobResult with injected httpClient", async () => {
  const fakeClient = {
    getSqlJobResult: async ({ jobId }) => ({
      status: "FINISHED",
      job_id: jobId,
      real_execution: true,
      rows: [{ col1: "val1" }],
      column_names: ["col1"],
    }),
  };
  const transport = createDliHttpTransport({
    allowRealExecution: true,
    confirmNativeDli: true,
    understandExecutesSql: true,
    httpClient: fakeClient,
    config: { region: "cn-north-7", projectId: "proj-123" },
  });
  const result = await transport.getSqlJobResult({ jobId: "job789" });
  assert.equal(result.status, "FINISHED");
  assert.deepEqual(result.rows, [{ col1: "val1" }]);
  assert.deepEqual(result.column_names, ["col1"]);
});

test("transport submitSqlJob with httpClient missing required method returns NOT_IMPLEMENTED", async () => {
  const fakeClient = { someOtherMethod: async () => {} };
  const transport = createDliHttpTransport({
    allowRealExecution: true,
    confirmNativeDli: true,
    understandExecutesSql: true,
    httpClient: fakeClient,
    config: { region: "cn-north-7", projectId: "proj-123" },
  });
  const result = await transport.submitSqlJob({ sql: "SELECT 1", queueName: "default" });
  assert.equal(result.status, "NATIVE_DLI_TRANSPORT_NOT_IMPLEMENTED");
  assert.equal(result.real_execution, false);
});

test("pollJobStatus returns terminal status immediately", async () => {
  const fakeTransport = {
    getSqlJobStatus: async ({ jobId }) => ({
      status: "FINISHED",
      job_id: jobId,
      real_execution: true,
    }),
  };
  const result = await pollJobStatus(fakeTransport, "job1", 3, 10);
  assert.equal(result.status, "FINISHED");
  assert.equal(result.job_id, "job1");
});

test("pollJobStatus polls until terminal status", async () => {
  let callCount = 0;
  const fakeTransport = {
    getSqlJobStatus: async ({ jobId }) => {
      callCount++;
      if (callCount < 3) {
        return { status: "RUNNING", job_id: jobId, real_execution: true };
      }
      return { status: "FINISHED", job_id: jobId, real_execution: true };
    },
  };
  const result = await pollJobStatus(fakeTransport, "job1", 10, 10);
  assert.equal(result.status, "FINISHED");
  assert.equal(callCount, 3);
});

test("pollJobStatus times out after max attempts", async () => {
  const fakeTransport = {
    getSqlJobStatus: async ({ jobId }) => ({
      status: "RUNNING",
      job_id: jobId,
      real_execution: true,
    }),
  };
  const result = await pollJobStatus(fakeTransport, "job1", 3, 10);
  assert.equal(result.status, "TIMEOUT");
});

test("parseJobStatus normalizes lowercase DLI API status to uppercase", () => {
  const { parseJobStatus } = require("../../src/runtime/dli/dli-http-transport");
  const res1 = parseJobStatus(JSON.stringify({ jobs: [{ status: "finished", job_id: "j1" }] }));
  assert.equal(res1.status, "FINISHED");
  assert.equal(res1.job_id, "j1");

  const res2 = parseJobStatus(JSON.stringify({ jobs: [{ status: "running", job_id: "j2" }] }));
  assert.equal(res2.status, "RUNNING");

  const res3 = parseJobStatus(JSON.stringify({ jobs: [{ status: "failed", job_id: "j3" }] }));
  assert.equal(res3.status, "FAILED");

  const res4 = parseJobStatus(JSON.stringify({ status: "cancelled", job_id: "j4" }));
  assert.equal(res4.status, "CANCELLED");
});

test("parseJobResult extracts column names from DLI schema key-value format", () => {
  const { parseJobResult } = require("../../src/runtime/dli/dli-http-transport");
  const resBody = JSON.stringify({
    rows: [["6"]],
    schema: [{ actual_value: "BIGINT" }],
  });
  const result = parseJobResult(resBody);
  assert.deepEqual(result.column_names, ["actual_value"]);
  assert.equal(result.rows.length, 1);
  assert.equal(result.rows[0].actual_value, "6");
});

test("parseJobResult handles multiple DLI schema columns", () => {
  const { parseJobResult } = require("../../src/runtime/dli/dli-http-transport");
  const resBody = JSON.stringify({
    rows: [["4", "active"]],
    schema: [{ customer_count: "BIGINT" }, { status: "STRING" }],
  });
  const result = parseJobResult(resBody);
  assert.deepEqual(result.column_names, ["customer_count", "status"]);
  assert.equal(result.rows[0].customer_count, "4");
  assert.equal(result.rows[0].status, "active");
});

test("parseJobResult falls back to named column_name property", () => {
  const { parseJobResult } = require("../../src/runtime/dli/dli-http-transport");
  const resBody = JSON.stringify({
    rows: [["42"]],
    schema: [{ column_name: "cnt", column_type: "BIGINT" }],
  });
  const result = parseJobResult(resBody);
  assert.deepEqual(result.column_names, ["cnt"]);
  assert.equal(result.rows[0].cnt, "42");
});
