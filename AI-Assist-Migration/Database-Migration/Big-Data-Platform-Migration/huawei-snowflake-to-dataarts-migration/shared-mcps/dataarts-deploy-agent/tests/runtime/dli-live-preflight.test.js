const test = require("node:test");
const assert = require("node:assert/strict");
const {
  runDliLiveReadOnlyPreflight,
} = require("../../src/runtime/dli/dli-live-preflight");
const {
  createRealDliClient,
  buildDliListQueuesRequest,
  buildDliQueueDescribeRequest,
  createDliLivePreflightSafetyPolicy,
  runReadOnlyDliPreflight,
} = require("../../src/runtime/dli/real-dli-client");

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

test("readOnly flag is required — without it returns READ_ONLY_FLAG_REQUIRED", async () => {
  const result = await runDliLiveReadOnlyPreflight({ dliQueue: "default", readOnly: false });
  assert.equal(result.status, "READ_ONLY_FLAG_REQUIRED");
  assert.equal(result.healthy, false);
  assert.ok(result.findings.some((f) => f.includes("--read-only")));
});

test("readOnly flag omitted returns READ_ONLY_FLAG_REQUIRED", async () => {
  const result = await runDliLiveReadOnlyPreflight({ dliQueue: "default" });
  assert.equal(result.status, "READ_ONLY_FLAG_REQUIRED");
  assert.equal(result.healthy, false);
});

test("missing config returns DLI_LIVE_PREFLIGHT_NOT_CONFIGURED", async () => {
  const saved = saveEnv();

  try {
    const result = await runDliLiveReadOnlyPreflight({ dliQueue: "default", readOnly: true, config: {}, envFilePath: "/nonexistent/.env.dataarts" });
    assert.equal(result.status, "DLI_LIVE_PREFLIGHT_NOT_CONFIGURED");
    assert.equal(result.healthy, false);
    assert.equal(result.credentials_present, false);
    assert.equal(result.queue_accessible, false);
    assert.ok(result.source_map);
    assert.ok(result.env_file_status);
  } finally {
    restoreEnv(saved);
  }
});

test("no cloud calls attempted when config missing", async () => {
  let cloudCalled = false;
  const mockClient = {
    listQueues: async () => {
      cloudCalled = true;
      return { status: "OK", queues: [] };
    },
    describeQueue: async () => {
      cloudCalled = true;
      return { status: "OK", queue: null };
    },
  };

  const saved = saveEnv();

  try {
    const result = await runDliLiveReadOnlyPreflight({ dliQueue: "default", readOnly: true, config: {}, client: mockClient, envFilePath: "/nonexistent/.env.dataarts" });
    assert.equal(result.status, "DLI_LIVE_PREFLIGHT_NOT_CONFIGURED");
    assert.equal(cloudCalled, false);
  } finally {
    restoreEnv(saved);
  }
});

test("config present with mocked live client returns healthy", async () => {
  const saved = saveEnv();
  try {
    const config = {
      HUAWEI_REGION: "cn-north-7",
      HUAWEI_PROJECT_ID: "proj-123",
      HUAWEI_AK: "MY_ACCESS_KEY",
      HUAWEI_SK: "MY_SECRET_KEY",
    };

    const mockClient = {
      listQueues: async () => ({
        status: "OK",
        http_status: 200,
        read_only: true,
        real_execution: false,
        queues: [
          { queue_name: "default", queue_type: "sql", owner: "test" },
        ],
        queues_found: 1,
      }),
      describeQueue: async () => ({
        status: "OK",
        http_status: 200,
        read_only: true,
        real_execution: false,
        queue_name: "default",
        queue: { queue_name: "default", queue_type: "sql" },
        queue_exists: true,
      }),
    };

    const result = await runDliLiveReadOnlyPreflight({ dliQueue: "default", readOnly: true, config, client: mockClient, envFilePath: "/nonexistent/.env.dataarts" });
    assert.equal(result.status, "DLI_LIVE_PREFLIGHT_HEALTHY");
    assert.equal(result.healthy, true);
    assert.equal(result.credentials_present, true);
    assert.equal(result.queue_accessible, true);
  } finally {
    restoreEnv(saved);
  }
});

test("queue inaccessible returns unhealthy", async () => {
  const saved = saveEnv();
  try {
    const config = {
      HUAWEI_REGION: "cn-north-7",
      HUAWEI_PROJECT_ID: "proj-123",
      HUAWEI_AK: "MY_ACCESS_KEY",
      HUAWEI_SK: "MY_SECRET_KEY",
    };

    const mockClient = {
      listQueues: async () => ({
        status: "OK",
        http_status: 200,
        read_only: true,
        real_execution: false,
        queues: [
          { queue_name: "other_queue", queue_type: "sql" },
        ],
        queues_found: 1,
      }),
      describeQueue: async () => ({
        status: "ERROR",
        http_status: 404,
        queue_exists: false,
      }),
    };

    const result = await runDliLiveReadOnlyPreflight({ dliQueue: "default", readOnly: true, config, client: mockClient, envFilePath: "/nonexistent/.env.dataarts" });
    assert.equal(result.status, "DLI_LIVE_PREFLIGHT_UNHEALTHY");
    assert.equal(result.healthy, false);
    assert.equal(result.queue_accessible, false);
    assert.ok(result.findings.some((f) => f.includes("not found")));
  } finally {
    restoreEnv(saved);
  }
});

test("auth failure returns unhealthy", async () => {
  const saved = saveEnv();
  try {
    const config = {
      HUAWEI_REGION: "cn-north-7",
      HUAWEI_PROJECT_ID: "proj-123",
      HUAWEI_AK: "MY_ACCESS_KEY",
      HUAWEI_SK: "MY_SECRET_KEY",
    };

    const mockClient = {
      listQueues: async () => ({
        status: "ERROR",
        http_status: 401,
        read_only: true,
        real_execution: false,
        queues: [],
        queues_found: 0,
      }),
      describeQueue: async () => ({ status: "ERROR", http_status: 401 }),
    };

    const result = await runDliLiveReadOnlyPreflight({ dliQueue: "default", readOnly: true, config, client: mockClient, envFilePath: "/nonexistent/.env.dataarts" });
    assert.equal(result.status, "DLI_LIVE_PREFLIGHT_UNHEALTHY");
    assert.equal(result.healthy, false);
    assert.ok(result.findings.some((f) => f.includes("authentication") || f.includes("connectivity")));
  } finally {
    restoreEnv(saved);
  }
});

test("safety flags are present in preflight result", async () => {
  const saved = saveEnv();
  try {
    const config = {
      HUAWEI_REGION: "cn-north-7",
      HUAWEI_PROJECT_ID: "proj-123",
      HUAWEI_AK: "ak",
      HUAWEI_SK: "sk",
    };

    const mockClient = {
      listQueues: async () => ({ status: "OK", http_status: 200, queues: [{ queue_name: "default" }], queues_found: 1 }),
      describeQueue: async () => ({ status: "OK", queue: { queue_name: "default" } }),
    };

    const result = await runDliLiveReadOnlyPreflight({ dliQueue: "default", readOnly: true, config, client: mockClient, envFilePath: "/nonexistent/.env.dataarts" });
    assert.ok(result.safety);
    assert.equal(result.safety.dli_live_preflight, true);
    assert.equal(result.safety.read_only, true);
    assert.equal(result.safety.no_sql_execution, true);
    assert.equal(result.safety.no_runtime_execution, true);
    assert.equal(result.safety.no_cloud_write_calls, true);
    assert.equal(result.safety.no_confirm, true);
    assert.equal(result.safety.no_mutation_methods_allowed, true);
    assert.equal(result.safety.secrets_redacted, true);
  } finally {
    restoreEnv(saved);
  }
});

test("secrets are not exposed in preflight result", async () => {
  const saved = saveEnv();
  try {
    const config = {
      HUAWEI_REGION: "cn-north-7",
      HUAWEI_PROJECT_ID: "proj-123",
      HUAWEI_AK: "MY_SECRET_ACCESS_KEY_VALUE",
      HUAWEI_SK: "MY_SECRET_SECRET_KEY_VALUE",
    };

    const mockClient = {
      listQueues: async () => ({ status: "OK", http_status: 200, queues: [{ queue_name: "default" }], queues_found: 1 }),
      describeQueue: async () => ({ status: "OK", queue: { queue_name: "default" } }),
    };

    const result = await runDliLiveReadOnlyPreflight({ dliQueue: "default", readOnly: true, config, client: mockClient, envFilePath: "/nonexistent/.env.dataarts" });
    const json = JSON.stringify(result);
    assert.ok(!json.includes("MY_SECRET_ACCESS_KEY_VALUE"));
    assert.ok(!json.includes("MY_SECRET_SECRET_KEY_VALUE"));
    assert.equal(result.project_id, "present");
  } finally {
    restoreEnv(saved);
  }
});

test("mutation/write methods are not allowed — executeSql/querySql remain blocked", async () => {
  const client = createRealDliClient({ liveReadOnly: true });
  const execResult = await client.executeSql({ sql: "SELECT 1", queueName: "default" });
  assert.equal(execResult.real_execution, false);
  assert.equal(execResult.status, "PLANNED_NOT_EXECUTED");
  const queryResult = await client.querySql({ sql: "SELECT 1", queueName: "default" });
  assert.equal(queryResult.real_execution, false);
  assert.equal(queryResult.status, "PLANNED_NOT_EXECUTED");
});

test("executeSql/querySql remain blocked for real execution even with liveReadOnly", async () => {
  const client = createRealDliClient({ liveReadOnly: true, allowRealExecution: true });
  await assert.rejects(
    () => client.executeSql({ sql: "SELECT 1", queueName: "default" }),
    { message: "Native DLI real execution requires --confirm-native-dli" }
  );
  await assert.rejects(
    () => client.querySql({ sql: "SELECT 1", queueName: "default" }),
    { message: "Native DLI real execution requires --confirm-native-dli" }
  );
});

test("live preflight output is structured and redacted", async () => {
  const saved = saveEnv();
  try {
    const config = {
      HUAWEI_REGION: "cn-north-7",
      HUAWEI_PROJECT_ID: "proj-123",
      HUAWEI_AK: "ak",
      HUAWEI_SK: "sk",
    };

    const mockClient = {
      listQueues: async () => ({ status: "OK", http_status: 200, queues: [{ queue_name: "default" }], queues_found: 1 }),
      describeQueue: async () => ({ status: "OK", queue: { queue_name: "default" } }),
    };

    const result = await runDliLiveReadOnlyPreflight({ dliQueue: "default", readOnly: true, config, client: mockClient, envFilePath: "/nonexistent/.env.dataarts" });

    assert.ok(result.status);
    assert.equal(typeof result.healthy, "boolean");
    assert.equal(result.read_only, true);
    assert.ok(result.region);
    assert.ok(result.queue_name);
    assert.ok(Array.isArray(result.live_checks));
    assert.ok(Array.isArray(result.findings));
    assert.ok(Array.isArray(result.warnings));
    assert.ok(result.safety);
    assert.equal(result.project_id, "present");
  } finally {
    restoreEnv(saved);
  }
});

test("buildDliListQueuesRequest produces correct read-only request", () => {
  const req = buildDliListQueuesRequest({ region: "cn-north-7", projectId: "proj-123" });
  assert.equal(req.service, "DLI");
  assert.equal(req.operation, "listQueues");
  assert.equal(req.method, "GET");
  assert.equal(req.read_only, true);
  assert.equal(req.execution_mode, "READ_ONLY_LIVE");
  assert.ok(req.endpoint.includes("dli.cn-north-7.myhuaweicloud.com"));
  assert.ok(req.path.includes("/v1.0/proj-123/queues"));
});

test("buildDliQueueDescribeRequest produces correct read-only request", () => {
  const req = buildDliQueueDescribeRequest({ queueName: "default", region: "cn-north-7", projectId: "proj-123" });
  assert.equal(req.service, "DLI");
  assert.equal(req.operation, "describeQueue");
  assert.equal(req.method, "GET");
  assert.equal(req.read_only, true);
  assert.equal(req.queue_name, "default");
  assert.ok(req.path.includes("/queues/default"));
});

test("createDliLivePreflightSafetyPolicy has all required flags", () => {
  const safety = createDliLivePreflightSafetyPolicy();
  assert.equal(safety.dli_live_preflight, true);
  assert.equal(safety.read_only, true);
  assert.equal(safety.no_sql_execution, true);
  assert.equal(safety.no_runtime_execution, true);
  assert.equal(safety.no_cloud_write_calls, true);
  assert.equal(safety.no_confirm, true);
  assert.equal(safety.no_mutation_methods_allowed, true);
  assert.equal(safety.secrets_redacted, true);
});

test("runReadOnlyDliPreflight with not-configured returns NOT_CONFIGURED", async () => {
  const saved = saveEnv();

  try {
    const result = await runReadOnlyDliPreflight({ queueName: "default", config: {}, envFilePath: "/nonexistent/.env.dataarts" });
    assert.equal(result.status, "DLI_LIVE_PREFLIGHT_NOT_CONFIGURED");
    assert.equal(result.healthy, false);
    assert.ok(result.source_map);
    assert.ok(result.env_file_status);
  } finally {
    restoreEnv(saved);
  }
});

test("listQueues in plan-only mode returns PLANNED_NOT_EXECUTED", async () => {
  const client = createRealDliClient({ liveReadOnly: false });
  const result = await client.listQueues();
  assert.equal(result.status, "PLANNED_NOT_EXECUTED");
  assert.equal(result.real_execution, false);
  assert.equal(result.read_only, true);
  assert.ok(result.planned_request);
});

test("describeQueue in plan-only mode returns PLANNED_NOT_EXECUTED", async () => {
  const client = createRealDliClient({ liveReadOnly: false });
  const result = await client.describeQueue({ queueName: "default" });
  assert.equal(result.status, "PLANNED_NOT_EXECUTED");
  assert.equal(result.real_execution, false);
  assert.equal(result.read_only, true);
  assert.ok(result.planned_request);
});

test("client exposes _liveReadOnly flag", () => {
  const clientReadOnly = createRealDliClient({ liveReadOnly: true });
  assert.equal(clientReadOnly._liveReadOnly, true);
  const clientPlan = createRealDliClient({ liveReadOnly: false });
  assert.equal(clientPlan._liveReadOnly, false);
});

test("live preflight uses unified config with .env.dataarts", async () => {
  const fs = require("fs");
  const path = require("path");
  const os = require("os");
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "preflight-dotenv-test-"));
  const envPath = path.join(tmpDir, ".env.dataarts");
  fs.writeFileSync(envPath, "HUAWEI_REGION=cn-north-7\nHUAWEI_PROJECT_ID=proj-dotenv\nHUAWEI_AK=dotenv-ak\nHUAWEI_SK=dotenv-sk\nDLI_QUEUE_NAME=dotenv-queue\nDATAARTS_WORKSPACE_ID=ws-dotenv\n", "utf-8");

  const saved = saveEnv();

  const mockClient = {
    listQueues: async () => ({ status: "OK", http_status: 200, queues: [{ queue_name: "dotenv-queue" }], queues_found: 1 }),
    describeQueue: async () => ({ status: "OK", queue: { queue_name: "dotenv-queue" } }),
  };

  try {
    const result = await runDliLiveReadOnlyPreflight({ dliQueue: "dotenv-queue", readOnly: true, config: {}, client: mockClient, envFilePath: envPath });
    assert.equal(result.healthy, true);
    assert.equal(result.source_map.HUAWEI_REGION, ".env.dataarts");
    assert.equal(result.source_map.HUAWEI_AK, ".env.dataarts");
    assert.equal(result.env_file_status, ".env.dataarts");
  } finally {
    restoreEnv(saved);
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

test("no full secret appears in preflight JSON output with unified config", async () => {
  const fs = require("fs");
  const path = require("path");
  const os = require("os");
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "preflight-secret-test-"));
  const envPath = path.join(tmpDir, ".env.dataarts");
  fs.writeFileSync(envPath, "HUAWEI_REGION=cn-north-7\nHUAWEI_PROJECT_ID=proj-123\nHUAWEI_AK=SECRET_ACCESS_KEY_12345\nHUAWEI_SK=SECRET_SECRET_KEY_67890\n", "utf-8");

  const saved = saveEnv();

  const mockClient = {
    listQueues: async () => ({ status: "OK", http_status: 200, queues: [{ queue_name: "default" }], queues_found: 1 }),
    describeQueue: async () => ({ status: "OK", queue: { queue_name: "default" } }),
  };

  try {
    const result = await runDliLiveReadOnlyPreflight({ dliQueue: "default", readOnly: true, config: {}, client: mockClient, envFilePath: envPath });
    const json = JSON.stringify(result);
    assert.ok(!json.includes("SECRET_ACCESS_KEY_12345"));
    assert.ok(!json.includes("SECRET_SECRET_KEY_67890"));
  } finally {
    restoreEnv(saved);
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});
