const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const os = require("os");
const path = require("path");
const {
  buildMvpReport,
  resolveMvpStatus,
  renderMarkdown,
  writeMvpReport,
  MVP_VERSION,
} = require("../../src/migration/mvp-report");
const { normalizeRunIds, normalizeInstanceId } = require("../../src/migration/executor");

function createTempOutDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "mvp-test-"));
}

function writeFixtureJson(dir, filename, data) {
  const filePath = path.join(dir, filename);
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2), "utf-8");
  return filePath;
}

function makeFullDemoResult(overrides = {}) {
  return {
    run_id: "run_20260626173934_669f05b1",
    status: "FUNCTIONAL_EQUIVALENCE_CONFIRMED",
    job_name: "orders_pipeline_framework_v02_20260626123934",
    instance_id: "1332281",
    runtime_validate_status: "PASS",
    final_equivalence: "EQUIVALENT",
    stale_result_detected: false,
    ...overrides,
  };
}

function makeFullDoctorResult(overrides = {}) {
  return {
    is_healthy: true,
    findings: [],
    warnings: [],
    info: ["All checks passed"],
    ...overrides,
  };
}

function makeFullMigrationResult(overrides = {}) {
  return {
    status: "MIGRATION_EXECUTION_COMPLETE",
    valid: true,
    mode: "CONFIRM",
    adapter: "legacy-demo",
    run_id: "run_20260626173934_95b6bf9b",
    migration_run_id: "run_20260626173934_95b6bf9b",
    runtime_run_id: "run_20260626173934_669f05b1",
    job_name: "orders_pipeline_framework_v02_20260626123934",
    instance_id: "1332281",
    dataarts_instance_id: "1332281",
    ...overrides,
  };
}

test("resolveMvpStatus returns CONFIRMED when all conditions met", () => {
  const evidence = {
    demo_one_shot_result: makeFullDemoResult(),
    demo_one_shot_doctor_result: makeFullDoctorResult(),
  };

  const status = resolveMvpStatus(evidence);
  assert.equal(status.status, "CONFIRMED");
  assert.equal(status.conditions.runtime_validation_pass, true);
  assert.equal(status.conditions.equivalence_equivalent, true);
  assert.equal(status.conditions.doctor_healthy_yes, true);
  assert.equal(status.conditions.stale_result_false, true);
  assert.equal(status.conditions.instance_id_exists, true);
});

test("resolveMvpStatus returns NOT_CONFIRMED when equivalence is not EQUIVALENT", () => {
  const evidence = {
    demo_one_shot_result: makeFullDemoResult({ final_equivalence: "NOT_EQUIVALENT" }),
    demo_one_shot_doctor_result: makeFullDoctorResult(),
  };

  const status = resolveMvpStatus(evidence);
  assert.equal(status.status, "NOT_CONFIRMED");
  assert.equal(status.conditions.equivalence_equivalent, false);
});

test("resolveMvpStatus returns NOT_CONFIRMED when runtime validation is not PASS", () => {
  const evidence = {
    demo_one_shot_result: makeFullDemoResult({ runtime_validate_status: "FAIL" }),
    demo_one_shot_doctor_result: makeFullDoctorResult(),
  };

  const status = resolveMvpStatus(evidence);
  assert.equal(status.status, "NOT_CONFIRMED");
  assert.equal(status.conditions.runtime_validation_pass, false);
});

test("resolveMvpStatus returns NOT_CONFIRMED when doctor is not healthy", () => {
  const evidence = {
    demo_one_shot_result: makeFullDemoResult(),
    demo_one_shot_doctor_result: makeFullDoctorResult({ is_healthy: false, findings: ["CRITICAL: something"] }),
  };

  const status = resolveMvpStatus(evidence);
  assert.equal(status.status, "NOT_CONFIRMED");
  assert.equal(status.conditions.doctor_healthy_yes, false);
});

test("resolveMvpStatus handles doctor healthy field alias (not is_healthy)", () => {
  const evidence = {
    demo_one_shot_result: makeFullDemoResult(),
    demo_one_shot_doctor_result: { healthy: true, findings: [], warnings: [], info: [] },
  };

  const status = resolveMvpStatus(evidence);
  assert.equal(status.status, "CONFIRMED");
  assert.equal(status.conditions.doctor_healthy_yes, true);
});

test("resolveMvpStatus returns NOT_CONFIRMED when stale result detected", () => {
  const evidence = {
    demo_one_shot_result: makeFullDemoResult({ stale_result_detected: true }),
    demo_one_shot_doctor_result: makeFullDoctorResult(),
  };

  const status = resolveMvpStatus(evidence);
  assert.equal(status.status, "NOT_CONFIRMED");
  assert.equal(status.conditions.stale_result_false, false);
});

test("resolveMvpStatus returns NOT_CONFIRMED when instance_id is null", () => {
  const evidence = {
    demo_one_shot_result: makeFullDemoResult({ instance_id: null }),
    demo_one_shot_doctor_result: makeFullDoctorResult(),
  };

  const status = resolveMvpStatus(evidence);
  assert.equal(status.status, "NOT_CONFIRMED");
  assert.equal(status.conditions.instance_id_exists, false);
});

test("resolveMvpStatus uses runtime_demo_one_shot_result over demo_one_shot_result", () => {
  const evidence = {
    demo_one_shot_result: makeFullDemoResult({ final_equivalence: "NOT_EQUIVALENT" }),
    runtime_demo_one_shot_result: makeFullDemoResult({ final_equivalence: "EQUIVALENT" }),
    demo_one_shot_doctor_result: makeFullDoctorResult(),
  };

  const status = resolveMvpStatus(evidence);
  assert.equal(status.status, "CONFIRMED");
  assert.equal(status.final_equivalence, "EQUIVALENT");
});

test("buildMvpReport handles migration_run_id and runtime_run_id separately", () => {
  const outDir = createTempOutDir();
  writeFixtureJson(outDir, "demo_one_shot_result.json", makeFullDemoResult());
  writeFixtureJson(outDir, "demo_one_shot_doctor_result.json", makeFullDoctorResult());
  writeFixtureJson(outDir, "migration_execute_result.json", makeFullMigrationResult());

  const { report } = buildMvpReport({
    migrationRunId: "run_migration_123",
    runtimeRunId: "run_runtime_456",
    jobName: "test_job",
    outDir,
  });

  assert.equal(report.run_ids.migration_run_id, "run_migration_123");
  assert.equal(report.run_ids.runtime_run_id, "run_runtime_456");
  assert.notEqual(report.run_ids.migration_run_id, report.run_ids.runtime_run_id);
});

test("buildMvpReport marks MVP status CONFIRMED when all conditions met", () => {
  const outDir = createTempOutDir();
  writeFixtureJson(outDir, "demo_one_shot_result.json", makeFullDemoResult());
  writeFixtureJson(outDir, "demo_one_shot_doctor_result.json", makeFullDoctorResult());
  writeFixtureJson(outDir, "migration_execute_result.json", makeFullMigrationResult());

  const { report, mvpStatus } = buildMvpReport({
    migrationRunId: "run_migration_123",
    runtimeRunId: "run_runtime_456",
    jobName: "test_job",
    outDir,
  });

  assert.equal(report.mvp_status, "CONFIRMED");
  assert.equal(mvpStatus.status, "CONFIRMED");
});

test("buildMvpReport marks NOT_CONFIRMED when equivalence is not EQUIVALENT", () => {
  const outDir = createTempOutDir();
  writeFixtureJson(outDir, "demo_one_shot_result.json", makeFullDemoResult({ final_equivalence: "PARTIAL" }));
  writeFixtureJson(outDir, "demo_one_shot_doctor_result.json", makeFullDoctorResult());
  writeFixtureJson(outDir, "migration_execute_result.json", makeFullMigrationResult());

  const { report } = buildMvpReport({
    migrationRunId: "run_migration_123",
    runtimeRunId: "run_runtime_456",
    jobName: "test_job",
    outDir,
  });

  assert.equal(report.mvp_status, "NOT_CONFIRMED");
});

test("buildMvpReport includes dataarts_instance_id in run_ids", () => {
  const outDir = createTempOutDir();
  writeFixtureJson(outDir, "demo_one_shot_result.json", makeFullDemoResult({ instance_id: "1332281" }));
  writeFixtureJson(outDir, "demo_one_shot_doctor_result.json", makeFullDoctorResult());
  writeFixtureJson(outDir, "migration_execute_result.json", makeFullMigrationResult());

  const { report } = buildMvpReport({
    migrationRunId: "run_migration_123",
    runtimeRunId: "run_runtime_456",
    jobName: "test_job",
    outDir,
  });

  assert.equal(report.run_ids.dataarts_instance_id, "1332281");
});

test("buildMvpReport includes remaining limitations and next roadmap", () => {
  const outDir = createTempOutDir();
  writeFixtureJson(outDir, "demo_one_shot_result.json", makeFullDemoResult());
  writeFixtureJson(outDir, "demo_one_shot_doctor_result.json", makeFullDoctorResult());

  const { report } = buildMvpReport({
    migrationRunId: "run_migration_123",
    runtimeRunId: "run_runtime_456",
    jobName: "test_job",
    outDir,
  });

  assert.ok(Array.isArray(report.remaining_limitations));
  assert.ok(report.remaining_limitations.length > 0);
  assert.ok(Array.isArray(report.next_roadmap));
  assert.ok(report.next_roadmap.length > 0);
});

test("buildMvpReport includes safety controls", () => {
  const outDir = createTempOutDir();
  writeFixtureJson(outDir, "demo_one_shot_result.json", makeFullDemoResult());
  writeFixtureJson(outDir, "demo_one_shot_doctor_result.json", makeFullDoctorResult());

  const { report } = buildMvpReport({
    migrationRunId: "run_migration_123",
    runtimeRunId: "run_runtime_456",
    jobName: "test_job",
    outDir,
  });

  assert.equal(report.safety_controls.no_publish, true);
  assert.equal(report.safety_controls.no_delete, true);
  assert.equal(report.safety_controls.run_immediate_only, true);
});

test("renderMarkdown produces non-empty markdown", () => {
  const outDir = createTempOutDir();
  writeFixtureJson(outDir, "demo_one_shot_result.json", makeFullDemoResult());
  writeFixtureJson(outDir, "demo_one_shot_doctor_result.json", makeFullDoctorResult());

  const { report } = buildMvpReport({
    migrationRunId: "run_migration_123",
    runtimeRunId: "run_runtime_456",
    jobName: "test_job",
    outDir,
  });

  const md = renderMarkdown(report);
  assert.ok(md.includes("Migration Framework MVP"));
  assert.ok(md.includes("CONFIRMED"));
  assert.ok(md.includes("migration_run_id"));
  assert.ok(md.includes("runtime_run_id"));
  assert.ok(md.includes("dataarts_instance_id"));
});

test("writeMvpReport writes result JSON and report MD", () => {
  const outDir = createTempOutDir();
  writeFixtureJson(outDir, "demo_one_shot_result.json", makeFullDemoResult());
  writeFixtureJson(outDir, "demo_one_shot_doctor_result.json", makeFullDoctorResult());

  const { report } = buildMvpReport({
    migrationRunId: "run_migration_123",
    runtimeRunId: "run_runtime_456",
    jobName: "test_job",
    outDir,
  });

  const { resultPath, reportPath } = writeMvpReport(report, outDir);

  assert.ok(fs.existsSync(resultPath));
  assert.ok(fs.existsSync(reportPath));

  const writtenResult = JSON.parse(fs.readFileSync(resultPath, "utf-8"));
  assert.equal(writtenResult.mvp_status, "CONFIRMED");
  assert.equal(writtenResult.run_ids.migration_run_id, "run_migration_123");
  assert.equal(writtenResult.run_ids.runtime_run_id, "run_runtime_456");

  const writtenMd = fs.readFileSync(reportPath, "utf-8");
  assert.ok(writtenMd.includes("CONFIRMED"));
});

test("normalizeRunIds preserves backward compatible run_id", () => {
  const adapterResult = { run_id: "run_runtime_456" };
  const migrationRunId = "run_migration_123";

  const normalized = normalizeRunIds(adapterResult, migrationRunId);

  assert.equal(normalized.run_id, "run_migration_123");
  assert.equal(normalized.migration_run_id, "run_migration_123");
  assert.equal(normalized.runtime_run_id, "run_runtime_456");
});

test("normalizeRunIds falls back to runtime_run_id for run_id when no migration_run_id", () => {
  const adapterResult = { run_id: "run_runtime_456" };
  const migrationRunId = null;

  const normalized = normalizeRunIds(adapterResult, migrationRunId);

  assert.equal(normalized.run_id, "run_runtime_456");
  assert.equal(normalized.migration_run_id, null);
  assert.equal(normalized.runtime_run_id, "run_runtime_456");
});

test("normalizeInstanceId returns null for null/undefined/empty", () => {
  assert.equal(normalizeInstanceId(null), null);
  assert.equal(normalizeInstanceId(undefined), null);
  assert.equal(normalizeInstanceId(""), null);
});

test("normalizeInstanceId returns the id for valid values", () => {
  assert.equal(normalizeInstanceId("1332281"), "1332281");
  assert.equal(normalizeInstanceId(1332281), 1332281);
});

test("MVP_VERSION is 0.1", () => {
  assert.equal(MVP_VERSION, "0.1");
});

test("buildMvpReport reads runtime run dir evidence when runtimeRunId provided", () => {
  const outDir = createTempOutDir();
  const runtimeRunId = "run_20260626173934_669f05b1";
  const runDir = path.join(outDir, "runs", runtimeRunId);
  fs.mkdirSync(runDir, { recursive: true });

  writeFixtureJson(runDir, "demo_one_shot_result.json", makeFullDemoResult());
  writeFixtureJson(outDir, "demo_one_shot_doctor_result.json", makeFullDoctorResult());

  const { report } = buildMvpReport({
    migrationRunId: "run_migration_123",
    runtimeRunId,
    jobName: "test_job",
    outDir,
  });

  assert.equal(report.mvp_status, "CONFIRMED");
  assert.ok(report.evidence_paths.runtime_run_dir);
});

test("buildMvpReport handles missing evidence gracefully", () => {
  const outDir = createTempOutDir();

  const { report } = buildMvpReport({
    migrationRunId: "run_migration_123",
    runtimeRunId: "run_runtime_456",
    jobName: "test_job",
    outDir,
  });

  assert.equal(report.mvp_status, "NOT_CONFIRMED");
  assert.equal(report.run_ids.migration_run_id, "run_migration_123");
  assert.equal(report.run_ids.runtime_run_id, "run_runtime_456");
});
