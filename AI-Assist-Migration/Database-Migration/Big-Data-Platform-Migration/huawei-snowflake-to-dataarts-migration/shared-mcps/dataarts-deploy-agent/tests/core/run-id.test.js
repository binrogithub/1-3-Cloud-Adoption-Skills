const test = require("node:test");
const assert = require("node:assert/strict");
const { generateRunId, isValidRunId } = require("../../src/core/run-id");

test("generateRunId returns current demo-compatible run id format", () => {
  const runId = generateRunId(new Date("2026-06-23T13:43:24.000Z"));

  assert.match(runId, /^run_20260623134324\._[a-f0-9]{8}$/);
  assert.equal(isValidRunId(runId), true);
});

test("isValidRunId rejects invalid run ids", () => {
  assert.equal(isValidRunId("abc"), false);
  assert.equal(isValidRunId("run_20260623134324"), false);
  assert.equal(isValidRunId("run_20260623134324_abcdef12"), false);
});
