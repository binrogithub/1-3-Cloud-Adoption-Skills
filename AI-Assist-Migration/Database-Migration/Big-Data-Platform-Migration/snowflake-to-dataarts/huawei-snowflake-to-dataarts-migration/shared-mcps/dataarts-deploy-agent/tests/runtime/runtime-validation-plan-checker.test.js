const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("path");
const { compareValidationPlanToRuntimeQueries } = require("../../src/runtime/runtime-validation-plan-checker");

const ORDERS_DIR = path.resolve(__dirname, "../../cases/golden/orders_pipeline_simple");
const CUSTOMER_DIR = path.resolve(__dirname, "../../cases/golden/customer_status_pipeline_simple");

test("validation plan checker passes for orders package", () => {
  const result = compareValidationPlanToRuntimeQueries({ packageDir: ORDERS_DIR });

  assert.equal(result.valid, true);
  assert.equal(result.findings.length, 0);
  assert.equal(result.unmatched.length, 0);
  assert.ok(result.matched.length > 0);
});

test("validation plan checker passes for customer package", () => {
  const result = compareValidationPlanToRuntimeQueries({ packageDir: CUSTOMER_DIR });

  assert.equal(result.valid, true);
  assert.equal(result.findings.length, 0);
  assert.equal(result.unmatched.length, 0);
  assert.ok(result.matched.length > 0);
});

test("PIPELINE_READY checks are skipped", () => {
  const result = compareValidationPlanToRuntimeQueries({ packageDir: ORDERS_DIR });

  const pipelineReadyMatch = result.matched.find(
    (m) => m.plan_check.type === "PIPELINE_READY"
  );
  assert.equal(pipelineReadyMatch, undefined);
});

test("FINAL_EQUIVALENCE checks are skipped", () => {
  const result = compareValidationPlanToRuntimeQueries({ packageDir: CUSTOMER_DIR });

  const finalEquivMatch = result.matched.find(
    (m) => m.plan_check.type === "FINAL_EQUIVALENCE"
  );
  assert.equal(finalEquivMatch, undefined);
});

test("TABLE_COUNT checks are matched for orders", () => {
  const result = compareValidationPlanToRuntimeQueries({ packageDir: ORDERS_DIR });

  const tableCountMatches = result.matched.filter(
    (m) => m.plan_check.type === "TABLE_COUNT"
  );
  assert.ok(tableCountMatches.length >= 3, "should match RAW_ORDERS, SILVER_ORDERS, GOLD_DAILY_SALES");
});

test("AGGREGATE_CHECK checks are matched for orders", () => {
  const result = compareValidationPlanToRuntimeQueries({ packageDir: ORDERS_DIR });

  const aggregateMatches = result.matched.filter(
    (m) => m.plan_check.type === "AGGREGATE_CHECK"
  );
  assert.equal(aggregateMatches.length, 2);
});

test("AGGREGATE_CHECK checks are matched for customer", () => {
  const result = compareValidationPlanToRuntimeQueries({ packageDir: CUSTOMER_DIR });

  const aggregateMatches = result.matched.filter(
    (m) => m.plan_check.type === "AGGREGATE_CHECK"
  );
  assert.equal(aggregateMatches.length, 2);
});

test("missing runtime query for plan check produces finding", () => {
  const validationPlan = {
    checks: [
      { type: "TABLE_COUNT", object_name: "MISSING_TABLE", expected: 1 },
    ],
  };
  const runtimeQueries = {
    queries: [
      { id: "q1", type: "TABLE_COUNT", object_name: "OTHER_TABLE", sql: "SELECT 1", expected: 1 },
    ],
  };

  const result = compareValidationPlanToRuntimeQueries({
    validationPlan,
    runtimeQueries,
  });

  assert.equal(result.valid, false);
  assert.equal(result.findings.length, 1);
  assert.equal(result.unmatched.length, 1);
  assert.ok(result.findings[0].includes("MISSING_TABLE"));
});

test("missing packageDir fails", () => {
  const result = compareValidationPlanToRuntimeQueries({});

  assert.equal(result.valid, false);
  assert.ok(result.errors.some((e) => e.includes("packageDir")));
});

test("missing runtime queries produces warning not error", () => {
  const validationPlan = {
    checks: [{ type: "TABLE_COUNT", object_name: "T", expected: 1 }],
  };

  const result = compareValidationPlanToRuntimeQueries({
    validationPlan,
    runtimeQueries: null,
  });

  assert.equal(result.valid, true);
  assert.ok(result.warnings.length > 0);
});
