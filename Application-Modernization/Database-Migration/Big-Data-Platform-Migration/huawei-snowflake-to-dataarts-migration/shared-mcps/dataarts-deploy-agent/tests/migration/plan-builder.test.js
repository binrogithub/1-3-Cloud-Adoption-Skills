const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("path");
const { buildMigrationPlan } = require("../../src/migration/plan-builder");

test("buildMigrationPlan creates valid plan for golden orders pipeline", () => {
  const packageDir = path.resolve(
    __dirname,
    "../../cases/golden/orders_pipeline_simple"
  );

  const plan = buildMigrationPlan({ packageDir });

  assert.equal(plan.valid, true);
  assert.equal(plan.status, "PLAN_READY");
  assert.equal(plan.migration_id, "orders_pipeline_simple");
  assert.equal(plan.target.orchestrator, "DATAARTS_FACTORY");
  assert.equal(plan.target.runtime, "DLI");
  assert.equal(plan.target.node_count, 5);
  assert.equal(plan.validation.check_count, 7);
  assert.equal(plan.safety.plan_only, true);
  assert.equal(plan.safety.no_api_write_calls, true);
  assert.equal(plan.safety.no_runtime_execution, true);
});

test("buildMigrationPlan creates valid plan for golden customer status pipeline", () => {
  const packageDir = path.resolve(
    __dirname,
    "../../cases/golden/customer_status_pipeline_simple"
  );

  const plan = buildMigrationPlan({ packageDir });

  assert.equal(plan.valid, true);
  assert.equal(plan.status, "PLAN_READY");
  assert.equal(plan.migration_id, "customer_status_pipeline_simple");
  assert.equal(plan.target.orchestrator, "DATAARTS_FACTORY");
  assert.equal(plan.target.runtime, "DLI");
  assert.equal(plan.target.node_count, 5);
  assert.equal(plan.validation.check_count, 8);
  assert.equal(plan.safety.plan_only, true);
  assert.equal(plan.safety.no_api_write_calls, true);
  assert.equal(plan.safety.no_runtime_execution, true);
});

test("buildMigrationPlan fails when packageDir is missing", () => {
  const plan = buildMigrationPlan({});

  assert.equal(plan.valid, false);
  assert.equal(plan.status, "INVALID_INPUT");
  assert.match(plan.errors.join("\n"), /packageDir is required/);
});

test("buildMigrationPlan fails for missing package", () => {
  const plan = buildMigrationPlan({
    packageDir: "/tmp/package-that-does-not-exist",
  });

  assert.equal(plan.valid, false);
  assert.equal(plan.status, "INVALID_PACKAGE");
});
