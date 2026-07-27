const test = require("node:test");
const assert = require("node:assert/strict");
const {
  checkDliQueueHealth,
  buildDliQueueHealthSafetyPolicy,
  buildDliListJobsRequest,
  countJobsByState,
} = require("../../src/runtime/dli/dli-queue-health");

test("queue health requires --read-only", async () => {
  const result = await checkDliQueueHealth({
    queueName: "default",
    readOnly: false,
  });

  assert.equal(result.status, "READ_ONLY_FLAG_REQUIRED");
  assert.equal(result.healthy, false);
  assert.equal(result.read_only, true);
  assert.ok(result.findings.some((f) => f.includes("--read-only")));
});

test("queue health safety flags present", () => {
  const safety = buildDliQueueHealthSafetyPolicy();
  assert.equal(safety.dli_queue_health, true);
  assert.equal(safety.read_only, true);
  assert.equal(safety.no_sql_execution, true);
  assert.equal(safety.no_job_cancel, true);
  assert.equal(safety.no_cloud_write_calls, true);
  assert.equal(safety.no_runtime_execution, true);
  assert.equal(safety.no_confirm, true);
  assert.equal(safety.secrets_redacted, true);
});

test("queue health never cancels jobs - safety policy has no_job_cancel", () => {
  const safety = buildDliQueueHealthSafetyPolicy();
  assert.equal(safety.no_job_cancel, true);
});

test("countJobsByState counts correctly", () => {
  const jobs = [
    { status: "LAUNCHING" },
    { status: "LAUNCHING" },
    { status: "LAUNCHING" },
    { status: "RUNNING" },
    { status: "FINISHED" },
    { status: "FINISHED" },
    { status: "FAILED" },
    { status: "CANCELLED" },
  ];

  const counts = countJobsByState(jobs);
  assert.equal(counts.LAUNCHING, 3);
  assert.equal(counts.RUNNING, 1);
  assert.equal(counts.FINISHED, 2);
  assert.equal(counts.FAILED, 1);
  assert.equal(counts.CANCELLED, 1);
  assert.equal(counts.UNKNOWN, 0);
});

test("countJobsByState handles empty jobs", () => {
  const counts = countJobsByState([]);
  assert.equal(counts.LAUNCHING, 0);
  assert.equal(counts.RUNNING, 0);
  assert.equal(counts.FINISHED, 0);
  assert.equal(counts.FAILED, 0);
  assert.equal(counts.CANCELLED, 0);
  assert.equal(counts.UNKNOWN, 0);
});

test("countJobsByState handles unknown status", () => {
  const jobs = [{ status: "WEIRD_STATUS" }];
  const counts = countJobsByState(jobs);
  assert.equal(counts.UNKNOWN, 1);
});

test("buildDliListJobsRequest constructs correct request", () => {
  const req = buildDliListJobsRequest({
    region: "la-north-2",
    projectId: "abc123",
  });

  assert.equal(req.service, "DLI");
  assert.equal(req.operation, "listSqlJobs");
  assert.equal(req.method, "GET");
  assert.equal(req.read_only, true);
  assert.ok(req.path.includes("/jobs"));
  assert.ok(req.endpoint.includes("dli.la-north-2.myhuaweicloud.com"));
});

test("buildDliListJobsRequest handles missing region/projectId", () => {
  const req = buildDliListJobsRequest({});
  assert.equal(req.endpoint, null);
  assert.equal(req.path, null);
});

test("queue health with missing credentials returns NOT_CONFIGURED when no env", async () => {
  const originalEnv = {
    HUAWEI_REGION: process.env.HUAWEI_REGION,
    HUAWEI_PROJECT_ID: process.env.HUAWEI_PROJECT_ID,
    HUAWEI_AK: process.env.HUAWEI_AK,
    HUAWEI_SK: process.env.HUAWEI_SK,
  };
  delete process.env.HUAWEI_REGION;
  delete process.env.HUAWEI_PROJECT_ID;
  delete process.env.HUAWEI_AK;
  delete process.env.HUAWEI_SK;

  try {
    const result = await checkDliQueueHealth({
      queueName: "default",
      readOnly: true,
      envFilePath: "/nonexistent/.env.dataarts",
    });

    assert.equal(result.status, "DLI_QUEUE_HEALTH_NOT_CONFIGURED");
    assert.equal(result.healthy, false);
    assert.equal(result.credentials_present, false);
  } finally {
    if (originalEnv.HUAWEI_REGION !== undefined) process.env.HUAWEI_REGION = originalEnv.HUAWEI_REGION;
    if (originalEnv.HUAWEI_PROJECT_ID !== undefined) process.env.HUAWEI_PROJECT_ID = originalEnv.HUAWEI_PROJECT_ID;
    if (originalEnv.HUAWEI_AK !== undefined) process.env.HUAWEI_AK = originalEnv.HUAWEI_AK;
    if (originalEnv.HUAWEI_SK !== undefined) process.env.HUAWEI_SK = originalEnv.HUAWEI_SK;
  }
});

test("queue health safety flags in result", async () => {
  const result = await checkDliQueueHealth({
    queueName: "default",
    readOnly: true,
  });

  assert.ok(result.safety);
  assert.equal(result.safety.read_only, true);
  assert.equal(result.safety.no_sql_execution, true);
  assert.equal(result.safety.no_job_cancel, true);
  assert.equal(result.safety.no_cloud_write_calls, true);
  assert.equal(result.safety.no_runtime_execution, true);
});
