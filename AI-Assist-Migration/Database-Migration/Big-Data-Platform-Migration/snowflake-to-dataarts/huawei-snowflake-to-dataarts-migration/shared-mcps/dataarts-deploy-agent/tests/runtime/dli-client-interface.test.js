const test = require("node:test");
const assert = require("node:assert/strict");
const {
  REQUIRED_DLI_CLIENT_METHODS,
  assertDliClient,
  createUnsupportedDliClient,
} = require("../../src/runtime/dli/dli-client-interface");

test("REQUIRED_DLI_CLIENT_METHODS contains executeSql, querySql, getJobStatus, getJobResult", () => {
  assert.ok(REQUIRED_DLI_CLIENT_METHODS.includes("executeSql"));
  assert.ok(REQUIRED_DLI_CLIENT_METHODS.includes("querySql"));
  assert.ok(REQUIRED_DLI_CLIENT_METHODS.includes("getJobStatus"));
  assert.ok(REQUIRED_DLI_CLIENT_METHODS.includes("getJobResult"));
  assert.equal(REQUIRED_DLI_CLIENT_METHODS.length, 4);
});

test("assertDliClient accepts valid mock client", () => {
  const client = {
    executeSql() {},
    querySql() {},
    getJobStatus() {},
    getJobResult() {},
  };
  assert.equal(assertDliClient(client), true);
});

test("assertDliClient rejects null", () => {
  assert.throws(() => assertDliClient(null), /non-null object/);
});

test("assertDliClient rejects undefined", () => {
  assert.throws(() => assertDliClient(undefined), /non-null object/);
});

test("assertDliClient rejects missing methods", () => {
  const client = {
    executeSql() {},
    querySql() {},
  };
  assert.throws(() => assertDliClient(client), /missing required methods/);
});

test("assertDliClient rejects object with no methods", () => {
  assert.throws(() => assertDliClient({}), /missing required methods/);
});

test("unsupported client executeSql throws clear error", () => {
  const client = createUnsupportedDliClient();
  assert.throws(() => client.executeSql({ sql: "SELECT 1" }), /Real DLI client is not configured/);
});

test("unsupported client querySql throws clear error", () => {
  const client = createUnsupportedDliClient();
  assert.throws(() => client.querySql({ sql: "SELECT 1" }), /Real DLI client is not configured/);
});

test("unsupported client getJobStatus throws clear error", () => {
  const client = createUnsupportedDliClient();
  assert.throws(() => client.getJobStatus({ jobId: "123" }), /Real DLI client is not configured/);
});

test("unsupported client getJobResult throws clear error", () => {
  const client = createUnsupportedDliClient();
  assert.throws(() => client.getJobResult({ jobId: "123" }), /Real DLI client is not configured/);
});

test("unsupported client passes assertDliClient", () => {
  const client = createUnsupportedDliClient();
  assert.equal(assertDliClient(client), true);
});
