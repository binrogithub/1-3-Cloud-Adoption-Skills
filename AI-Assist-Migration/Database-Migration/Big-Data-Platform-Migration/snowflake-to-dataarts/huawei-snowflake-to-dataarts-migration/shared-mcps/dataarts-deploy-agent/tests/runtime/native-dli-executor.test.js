const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { executeNativeDliPlan, compareValidationResults, buildNativeDliEquivalenceSummary } = require("../../src/runtime/native-dli-executor");
const { createMockDliClient } = require("../../src/runtime/dli/mock-dli-client");
const { loadRuntimePackageArtifacts } = require("../../src/runtime/runtime-package-loader");
const { loadMigrationPackage } = require("../../src/migration/package-loader");

const ORDERS_DIR = path.resolve(__dirname, "../../cases/golden/orders_pipeline_simple");
const CUSTOMER_DIR = path.resolve(__dirname, "../../cases/golden/customer_status_pipeline_simple");

function getValidationQueries(packageDir) {
  const pkg = loadMigrationPackage(packageDir);
  const artifacts = loadRuntimePackageArtifacts({
    packageDir,
    migrationId: pkg.migration_id,
  });
  return artifacts.valid ? (artifacts.validation_queries.queries || []) : [];
}

test("executeNativeDliPlan succeeds for orders package", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "native-exec-"));
  const queries = getValidationQueries(ORDERS_DIR);
  const mockClient = createMockDliClient({ validationQueries: queries });

  const result = executeNativeDliPlan({
    packageDir: ORDERS_DIR,
    dliQueue: "default",
    mode: "MOCK",
    dliClient: mockClient,
    outDir,
  });

  assert.equal(result.valid, true);
  assert.equal(result.status, "NATIVE_DLI_MOCK_EXECUTION_COMPLETE");
  assert.equal(result.mode, "MOCK");
  assert.equal(result.mock_execution, true);
  assert.ok(result.run_id);
  assert.equal(result.migration_id, "orders_pipeline_simple");
  assert.ok(result.setup_results.length > 0);
  assert.ok(result.target_results.length > 0);
  assert.ok(result.validation_results.length > 0);
  assert.ok(result.comparison_results.length > 0);
});

test("executeNativeDliPlan succeeds for customer package", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "native-exec-cust-"));
  const queries = getValidationQueries(CUSTOMER_DIR);
  const mockClient = createMockDliClient({ validationQueries: queries });

  const result = executeNativeDliPlan({
    packageDir: CUSTOMER_DIR,
    dliQueue: "default",
    mode: "MOCK",
    dliClient: mockClient,
    outDir,
  });

  assert.equal(result.valid, true);
  assert.equal(result.status, "NATIVE_DLI_MOCK_EXECUTION_COMPLETE");
  assert.equal(result.migration_id, "customer_status_pipeline_simple");
});

test("final_equivalence MOCK_EQUIVALENT on success", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "native-exec-eq-"));
  const queries = getValidationQueries(ORDERS_DIR);
  const mockClient = createMockDliClient({ validationQueries: queries });

  const result = executeNativeDliPlan({
    packageDir: ORDERS_DIR,
    dliQueue: "default",
    mode: "MOCK",
    dliClient: mockClient,
    outDir,
  });

  assert.equal(result.valid, true);
  assert.equal(result.final_equivalence, "MOCK_EQUIVALENT");
});

test("equivalence_confirmed false", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "native-exec-eqf-"));
  const queries = getValidationQueries(ORDERS_DIR);
  const mockClient = createMockDliClient({ validationQueries: queries });

  const result = executeNativeDliPlan({
    packageDir: ORDERS_DIR,
    dliQueue: "default",
    mode: "MOCK",
    dliClient: mockClient,
    outDir,
  });

  assert.equal(result.equivalence_confirmed, false);
});

test("real_runtime_confirmed false", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "native-exec-rrf-"));
  const queries = getValidationQueries(ORDERS_DIR);
  const mockClient = createMockDliClient({ validationQueries: queries });

  const result = executeNativeDliPlan({
    packageDir: ORDERS_DIR,
    dliQueue: "default",
    mode: "MOCK",
    dliClient: mockClient,
    outDir,
  });

  assert.equal(result.real_runtime_confirmed, false);
});

test("mismatch returns NOT_EQUIVALENT and valid false", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "native-exec-mismatch-"));
  const queries = getValidationQueries(ORDERS_DIR);
  const mockClient = createMockDliClient({
    validationQueries: queries,
    failQueryId: "raw_orders_count",
  });

  const result = executeNativeDliPlan({
    packageDir: ORDERS_DIR,
    dliQueue: "default",
    mode: "MOCK",
    dliClient: mockClient,
    outDir,
  });

  assert.equal(result.valid, false);
  assert.equal(result.final_equivalence, "NOT_EQUIVALENT");
  assert.equal(result.status, "NATIVE_DLI_MOCK_EXECUTION_FAILED");
});

test("evidence files written", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "native-exec-evidence-"));
  const queries = getValidationQueries(ORDERS_DIR);
  const mockClient = createMockDliClient({ validationQueries: queries });

  const result = executeNativeDliPlan({
    packageDir: ORDERS_DIR,
    dliQueue: "default",
    mode: "MOCK",
    dliClient: mockClient,
    outDir,
  });

  assert.ok(result.evidence_paths);
  assert.ok(fs.existsSync(result.evidence_paths.result_json));
  assert.ok(fs.existsSync(result.evidence_paths.report_md));
  assert.ok(fs.existsSync(result.evidence_paths.run_result_json));
  assert.ok(fs.existsSync(result.evidence_paths.run_report_md));
  assert.ok(fs.existsSync(result.evidence_paths.current_run_json));
});

test("safety.no_cloud_api_calls true", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "native-exec-safety1-"));
  const queries = getValidationQueries(ORDERS_DIR);
  const mockClient = createMockDliClient({ validationQueries: queries });

  const result = executeNativeDliPlan({
    packageDir: ORDERS_DIR,
    dliQueue: "default",
    mode: "MOCK",
    dliClient: mockClient,
    outDir,
  });

  assert.equal(result.safety.no_cloud_api_calls, true);
});

test("safety.no_real_sql_execution true", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "native-exec-safety2-"));
  const queries = getValidationQueries(ORDERS_DIR);
  const mockClient = createMockDliClient({ validationQueries: queries });

  const result = executeNativeDliPlan({
    packageDir: ORDERS_DIR,
    dliQueue: "default",
    mode: "MOCK",
    dliClient: mockClient,
    outDir,
  });

  assert.equal(result.safety.no_real_sql_execution, true);
});

test("safety.mock_client_required true", () => {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "native-exec-safety3-"));
  const queries = getValidationQueries(ORDERS_DIR);
  const mockClient = createMockDliClient({ validationQueries: queries });

  const result = executeNativeDliPlan({
    packageDir: ORDERS_DIR,
    dliQueue: "default",
    mode: "MOCK",
    dliClient: mockClient,
    outDir,
  });

  assert.equal(result.safety.mock_client_required, true);
});

test("missing packageDir returns error", () => {
  const mockClient = createMockDliClient({});

  const result = executeNativeDliPlan({
    packageDir: null,
    dliQueue: "default",
    mode: "MOCK",
    dliClient: mockClient,
  });

  assert.equal(result.valid, false);
  assert.equal(result.status, "NATIVE_DLI_MOCK_EXECUTION_FAILED");
  assert.ok(result.errors.some((e) => e.includes("packageDir")));
});

test("missing dliClient returns error", () => {
  const result = executeNativeDliPlan({
    packageDir: ORDERS_DIR,
    dliQueue: "default",
    mode: "MOCK",
    dliClient: null,
  });

  assert.equal(result.valid, false);
  assert.equal(result.status, "NATIVE_DLI_MOCK_EXECUTION_FAILED");
  assert.ok(result.errors.some((e) => e.includes("DLI client")));
});

test("unsupported mode returns error", () => {
  const mockClient = createMockDliClient({});

  const result = executeNativeDliPlan({
    packageDir: ORDERS_DIR,
    dliQueue: "default",
    mode: "CONFIRM",
    dliClient: mockClient,
  });

  assert.equal(result.valid, false);
  assert.equal(result.status, "NATIVE_DLI_MOCK_EXECUTION_FAILED");
  assert.ok(result.errors.some((e) => e.includes("Unsupported mode")));
});

test("compareValidationResults matches TABLE_COUNT", () => {
  const comparisons = compareValidationResults({
    validationResults: [
      { query_id: "raw_count", rows: [{ actual_value: 5 }] },
    ],
    validationQueries: [
      { id: "raw_count", type: "TABLE_COUNT", object_name: "RAW", expected: 5 },
    ],
  });

  assert.equal(comparisons.length, 1);
  assert.equal(comparisons[0].match, true);
});

test("compareValidationResults detects mismatch", () => {
  const comparisons = compareValidationResults({
    validationResults: [
      { query_id: "raw_count", rows: [{ actual_value: 3 }] },
    ],
    validationQueries: [
      { id: "raw_count", type: "TABLE_COUNT", object_name: "RAW", expected: 5 },
    ],
  });

  assert.equal(comparisons.length, 1);
  assert.equal(comparisons[0].match, false);
});

test("compareValidationResults handles >=1 TASK_AUDIT_SUCCESS", () => {
  const comparisons = compareValidationResults({
    validationResults: [
      { query_id: "audit", rows: [{ actual_value: 3 }] },
    ],
    validationQueries: [
      { id: "audit", type: "TASK_AUDIT_SUCCESS", object_name: "TASK_AUDIT", expected: ">=1" },
    ],
  });

  assert.equal(comparisons.length, 1);
  assert.equal(comparisons[0].match, true);
});

test("compareValidationResults handles AGGREGATE_CHECK", () => {
  const comparisons = compareValidationResults({
    validationResults: [
      { query_id: "agg", rows: [{ order_count: 2, total_amount: 420.50 }] },
    ],
    validationQueries: [
      { id: "agg", type: "AGGREGATE_CHECK", object_name: "2026-06-20", expected: { order_count: 2, total_amount: 420.50 } },
    ],
  });

  assert.equal(comparisons.length, 1);
  assert.equal(comparisons[0].match, true);
});

test("buildNativeDliEquivalenceSummary returns MOCK_EQUIVALENT when all match", () => {
  const summary = buildNativeDliEquivalenceSummary({
    comparisonResults: [
      { query_id: "a", object_name: "A", query_type: "TABLE_COUNT", expected: 5, actual: 5, match: true },
    ],
    migrationId: "test",
  });

  assert.equal(summary.final_equivalence, "MOCK_EQUIVALENT");
  assert.equal(summary.equivalence_confirmed, false);
  assert.equal(summary.real_runtime_confirmed, false);
  assert.equal(summary.mock_execution, true);
});

test("buildNativeDliEquivalenceSummary returns NOT_EQUIVALENT when any mismatch", () => {
  const summary = buildNativeDliEquivalenceSummary({
    comparisonResults: [
      { query_id: "a", object_name: "A", query_type: "TABLE_COUNT", expected: 5, actual: 3, match: false },
    ],
    migrationId: "test",
  });

  assert.equal(summary.final_equivalence, "NOT_EQUIVALENT");
});
