const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const os = require("os");
const path = require("path");
const {
  loadRuntimeSetup,
  loadRuntimeValidationQueries,
  loadRuntimePackageArtifacts,
} = require("../../src/runtime/runtime-package-loader");

const ORDERS_DIR = path.resolve(__dirname, "../../cases/golden/orders_pipeline_simple");
const CUSTOMER_DIR = path.resolve(__dirname, "../../cases/golden/customer_status_pipeline_simple");

test("loads orders runtime setup files", () => {
  const result = loadRuntimeSetup({ packageDir: ORDERS_DIR });

  assert.equal(result.valid, true);
  assert.equal(result.setup_sql_files.length, 3);
  assert.equal(result.setup_sql_files[0].file_name, "01_create_schema.sql");
  assert.equal(result.setup_sql_files[1].file_name, "02_create_raw_tables.sql");
  assert.equal(result.setup_sql_files[2].file_name, "03_insert_seed_data.sql");
});

test("loads customer runtime setup files", () => {
  const result = loadRuntimeSetup({ packageDir: CUSTOMER_DIR });

  assert.equal(result.valid, true);
  assert.equal(result.setup_sql_files.length, 3);
  assert.equal(result.setup_sql_files[0].file_name, "01_create_schema.sql");
  assert.equal(result.setup_sql_files[1].file_name, "02_create_raw_tables.sql");
  assert.equal(result.setup_sql_files[2].file_name, "03_insert_seed_data.sql");
});

test("all setup SQL files are single-statement for orders", () => {
  const result = loadRuntimeSetup({ packageDir: ORDERS_DIR });

  assert.equal(result.valid, true);
  for (const f of result.setup_sql_files) {
    assert.equal(f.statement_count, 1, `${f.file_name} should have exactly 1 statement`);
  }
});

test("all setup SQL files are single-statement for customer", () => {
  const result = loadRuntimeSetup({ packageDir: CUSTOMER_DIR });

  assert.equal(result.valid, true);
  for (const f of result.setup_sql_files) {
    assert.equal(f.statement_count, 1, `${f.file_name} should have exactly 1 statement`);
  }
});

test("validation_queries.json loads and validates for orders", () => {
  const result = loadRuntimeValidationQueries({
    packageDir: ORDERS_DIR,
    migrationId: "orders_pipeline_simple",
  });

  assert.equal(result.valid, true);
  assert.ok(result.validation_queries);
  assert.equal(result.validation_queries.migration_id, "orders_pipeline_simple");
  assert.ok(result.validation_queries.queries.length > 0);
});

test("validation_queries.json loads and validates for customer", () => {
  const result = loadRuntimeValidationQueries({
    packageDir: CUSTOMER_DIR,
    migrationId: "customer_status_pipeline_simple",
  });

  assert.equal(result.valid, true);
  assert.ok(result.validation_queries);
  assert.equal(result.validation_queries.migration_id, "customer_status_pipeline_simple");
  assert.ok(result.validation_queries.queries.length > 0);
});

test("migration_id mismatch fails", () => {
  const result = loadRuntimeValidationQueries({
    packageDir: ORDERS_DIR,
    migrationId: "wrong_migration_id",
  });

  assert.equal(result.valid, false);
  assert.ok(result.errors.some((e) => e.includes("mismatch")));
});

test("missing query id fails", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "rt-loader-"));
  fs.mkdirSync(path.join(dir, "runtime", "validation"), { recursive: true });
  const queries = {
    validation_queries_version: "0.1",
    migration_id: "test_pkg",
    runtime: "DLI",
    queries: [
      { type: "TABLE_COUNT", object_name: "T", sql: "SELECT 1", expected: 1 },
    ],
  };
  fs.writeFileSync(
    path.join(dir, "runtime", "validation", "validation_queries.json"),
    JSON.stringify(queries)
  );

  const result = loadRuntimeValidationQueries({ packageDir: dir });
  assert.equal(result.valid, false);
  assert.ok(result.errors.some((e) => e.includes("id")));
});

test("missing query type fails", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "rt-loader-"));
  fs.mkdirSync(path.join(dir, "runtime", "validation"), { recursive: true });
  const queries = {
    validation_queries_version: "0.1",
    migration_id: "test_pkg",
    runtime: "DLI",
    queries: [
      { id: "q1", object_name: "T", sql: "SELECT 1", expected: 1 },
    ],
  };
  fs.writeFileSync(
    path.join(dir, "runtime", "validation", "validation_queries.json"),
    JSON.stringify(queries)
  );

  const result = loadRuntimeValidationQueries({ packageDir: dir });
  assert.equal(result.valid, false);
  assert.ok(result.errors.some((e) => e.includes("type")));
});

test("missing query object_name fails", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "rt-loader-"));
  fs.mkdirSync(path.join(dir, "runtime", "validation"), { recursive: true });
  const queries = {
    validation_queries_version: "0.1",
    migration_id: "test_pkg",
    runtime: "DLI",
    queries: [
      { id: "q1", type: "TABLE_COUNT", sql: "SELECT 1", expected: 1 },
    ],
  };
  fs.writeFileSync(
    path.join(dir, "runtime", "validation", "validation_queries.json"),
    JSON.stringify(queries)
  );

  const result = loadRuntimeValidationQueries({ packageDir: dir });
  assert.equal(result.valid, false);
  assert.ok(result.errors.some((e) => e.includes("object_name")));
});

test("missing query sql fails", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "rt-loader-"));
  fs.mkdirSync(path.join(dir, "runtime", "validation"), { recursive: true });
  const queries = {
    validation_queries_version: "0.1",
    migration_id: "test_pkg",
    runtime: "DLI",
    queries: [
      { id: "q1", type: "TABLE_COUNT", object_name: "T", expected: 1 },
    ],
  };
  fs.writeFileSync(
    path.join(dir, "runtime", "validation", "validation_queries.json"),
    JSON.stringify(queries)
  );

  const result = loadRuntimeValidationQueries({ packageDir: dir });
  assert.equal(result.valid, false);
  assert.ok(result.errors.some((e) => e.includes("sql")));
});

test("missing query expected fails", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "rt-loader-"));
  fs.mkdirSync(path.join(dir, "runtime", "validation"), { recursive: true });
  const queries = {
    validation_queries_version: "0.1",
    migration_id: "test_pkg",
    runtime: "DLI",
    queries: [
      { id: "q1", type: "TABLE_COUNT", object_name: "T", sql: "SELECT 1" },
    ],
  };
  fs.writeFileSync(
    path.join(dir, "runtime", "validation", "validation_queries.json"),
    JSON.stringify(queries)
  );

  const result = loadRuntimeValidationQueries({ packageDir: dir });
  assert.equal(result.valid, false);
  assert.ok(result.errors.some((e) => e.includes("expected")));
});

test("loadRuntimePackageArtifacts loads orders successfully", () => {
  const result = loadRuntimePackageArtifacts({
    packageDir: ORDERS_DIR,
    migrationId: "orders_pipeline_simple",
  });

  assert.equal(result.valid, true);
  assert.equal(result.migration_id, "orders_pipeline_simple");
  assert.equal(result.setup_sql_files.length, 3);
  assert.ok(result.validation_queries);
  assert.ok(result.validation_queries.queries.length > 0);
});

test("loadRuntimePackageArtifacts loads customer successfully", () => {
  const result = loadRuntimePackageArtifacts({
    packageDir: CUSTOMER_DIR,
    migrationId: "customer_status_pipeline_simple",
  });

  assert.equal(result.valid, true);
  assert.equal(result.migration_id, "customer_status_pipeline_simple");
  assert.equal(result.setup_sql_files.length, 3);
  assert.ok(result.validation_queries);
  assert.ok(result.validation_queries.queries.length > 0);
});

test("loadRuntimePackageArtifacts missing packageDir fails", () => {
  const result = loadRuntimePackageArtifacts({});

  assert.equal(result.valid, false);
  assert.ok(result.errors.some((e) => e.includes("packageDir")));
});

test("loadRuntimeSetup missing setup dir fails", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "rt-loader-"));

  const result = loadRuntimeSetup({ packageDir: dir });

  assert.equal(result.valid, false);
  assert.ok(result.errors.some((e) => e.includes("does not exist")));
});

test("loadRuntimeValidationQueries missing file fails", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "rt-loader-"));

  const result = loadRuntimeValidationQueries({ packageDir: dir });

  assert.equal(result.valid, false);
  assert.ok(result.errors.some((e) => e.includes("does not exist")));
});

test("setup SQL files are sorted by filename", () => {
  const result = loadRuntimeSetup({ packageDir: ORDERS_DIR });

  const names = result.setup_sql_files.map((f) => f.file_name);
  const sorted = [...names].sort();
  assert.deepEqual(names, sorted);
});
