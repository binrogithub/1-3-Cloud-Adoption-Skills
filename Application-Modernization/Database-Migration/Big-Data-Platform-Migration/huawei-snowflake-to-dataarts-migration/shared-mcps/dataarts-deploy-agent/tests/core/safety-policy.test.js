const test = require("node:test");
const assert = require("node:assert/strict");
const { DEFAULT_SAFETY_POLICY, buildSafetyPolicy } = require("../../src/core/safety-policy");

test("default safety policy blocks dangerous operations", () => {
  assert.equal(DEFAULT_SAFETY_POLICY.no_publish, true);
  assert.equal(DEFAULT_SAFETY_POLICY.no_scheduled_start, true);
  assert.equal(DEFAULT_SAFETY_POLICY.no_delete, true);
  assert.equal(DEFAULT_SAFETY_POLICY.no_update, true);
  assert.equal(DEFAULT_SAFETY_POLICY.no_overwrite, true);
  assert.equal(DEFAULT_SAFETY_POLICY.only_run_immediate_for_execution, true);
  assert.equal(DEFAULT_SAFETY_POLICY.abort_if_job_exists, true);
});

test("buildSafetyPolicy allows explicit safe metadata overrides", () => {
  const policy = buildSafetyPolicy({ evidence_mode: "run_id" });

  assert.equal(policy.no_publish, true);
  assert.equal(policy.evidence_mode, "run_id");
});
