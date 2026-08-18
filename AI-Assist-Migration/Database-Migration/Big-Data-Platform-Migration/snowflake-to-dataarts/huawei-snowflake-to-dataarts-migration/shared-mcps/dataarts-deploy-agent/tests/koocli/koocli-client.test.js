const test = require("node:test");
const assert = require("node:assert/strict");
const {
  detectKooCli,
  runKooCliCommand,
  buildKooCliFutureCommandPlan,
  isCommandAllowed,
  COMMAND_ALLOWLIST,
} = require("../../src/koocli/koocli-client");

function makeMockRunner(results) {
  let index = 0;
  return (spec) => {
    if (index < results.length) {
      return results[index++];
    }
    return { exit_code: 1, success: false, outputTail: "", step: spec.step, name: spec.name, command: spec.cmd };
  };
}

test("COMMAND_ALLOWLIST contains expected entries", () => {
  assert.ok(COMMAND_ALLOWLIST.includes("which hcloud"));
  assert.ok(COMMAND_ALLOWLIST.includes("hcloud --help"));
  assert.ok(COMMAND_ALLOWLIST.includes("hcloud version"));
  assert.ok(COMMAND_ALLOWLIST.includes("hcloud --version"));
  assert.ok(COMMAND_ALLOWLIST.includes("hcloud configure list"));
  assert.ok(COMMAND_ALLOWLIST.includes("hcloud configure test"));
});

test("isCommandAllowed accepts allowlisted commands", () => {
  assert.equal(isCommandAllowed("which hcloud"), true);
  assert.equal(isCommandAllowed("hcloud configure test"), true);
  assert.equal(isCommandAllowed("hcloud configure list"), true);
});

test("isCommandAllowed rejects non-allowlisted commands", () => {
  assert.equal(isCommandAllowed("hcloud DataArtsStudio createJob"), false);
  assert.equal(isCommandAllowed("hcloud DLI runSql"), false);
  assert.equal(isCommandAllowed("rm -rf /"), false);
  assert.equal(isCommandAllowed("hcloud ECS createServer"), false);
});

test("runKooCliCommand rejects commands outside allowlist", () => {
  const result = runKooCliCommand({
    step: 1,
    name: "dangerous",
    cmd: "hcloud DataArtsStudio createJob",
  });

  assert.equal(result.rejected, true);
  assert.equal(result.success, false);
  assert.ok(result.rejection_reason.includes("not in allowlist"));
});

test("runKooCliCommand allows allowlisted commands", () => {
  const mockRunner = makeMockRunner([
    { exit_code: 0, success: true, outputTail: "3.2.7", step: 0, name: "hcloud --version", command: "hcloud --version" },
  ]);

  const result = runKooCliCommand(
    { step: 0, name: "hcloud-version", cmd: "hcloud --version" },
    { commandRunner: mockRunner }
  );

  assert.equal(result.rejected, false);
  assert.equal(result.success, true);
  assert.equal(result.exit_code, 0);
});

test("detectKooCli handles missing hcloud gracefully", () => {
  const mockRunner = makeMockRunner([
    { exit_code: 1, success: false, outputTail: "not found", step: 0, name: "detect-hcloud", command: "which hcloud" },
  ]);

  const result = detectKooCli({ commandRunner: mockRunner });

  assert.equal(result.installed, false);
  assert.equal(result.version, null);
  assert.equal(result.configure_test.attempted, false);
  assert.equal(result.configure_list.attempted, false);
  assert.ok(result.errors.some((e) => e.includes("not found")));
});

test("detectKooCli returns installed true when hcloud exists", () => {
  const mockRunner = makeMockRunner([
    { exit_code: 0, success: true, outputTail: "/usr/local/bin/hcloud", step: 0, name: "detect-hcloud", command: "which hcloud" },
    { exit_code: 0, success: true, outputTail: "3.2.7", step: 1, name: "hcloud-version", command: "hcloud --version" },
    { exit_code: 0, success: true, outputTail: "OK", step: 3, name: "hcloud-configure-test", command: "hcloud configure test" },
    { exit_code: 0, success: true, outputTail: "default", step: 4, name: "hcloud-configure-list", command: "hcloud configure list" },
  ]);

  const result = detectKooCli({ commandRunner: mockRunner });

  assert.equal(result.installed, true);
  assert.equal(result.version, "3.2.7");
  assert.equal(result.configure_test.attempted, true);
  assert.equal(result.configure_test.success, true);
  assert.equal(result.configure_list.attempted, true);
  assert.equal(result.configure_list.success, true);
});

test("detectKooCli handles configure test failure gracefully", () => {
  const mockRunner = makeMockRunner([
    { exit_code: 0, success: true, outputTail: "/usr/local/bin/hcloud", step: 0, name: "detect-hcloud", command: "which hcloud" },
    { exit_code: 0, success: true, outputTail: "3.2.7", step: 1, name: "hcloud-version", command: "hcloud --version" },
    { exit_code: 1, success: false, outputTail: "config error", step: 3, name: "hcloud-configure-test", command: "hcloud configure test" },
    { exit_code: 0, success: true, outputTail: "default", step: 4, name: "hcloud-configure-list", command: "hcloud configure list" },
  ]);

  const result = detectKooCli({ commandRunner: mockRunner });

  assert.equal(result.installed, true);
  assert.equal(result.configure_test.success, false);
  assert.ok(result.warnings.some((w) => w.includes("configure test")));
});

test("detectKooCli tries hcloud version as fallback", () => {
  const mockRunner = makeMockRunner([
    { exit_code: 0, success: true, outputTail: "/usr/local/bin/hcloud", step: 0, name: "detect-hcloud", command: "which hcloud" },
    { exit_code: 1, success: false, outputTail: "", step: 1, name: "hcloud-version", command: "hcloud --version" },
    { exit_code: 0, success: true, outputTail: "3.2.7", step: 2, name: "hcloud-version-alt", command: "hcloud version" },
    { exit_code: 0, success: true, outputTail: "OK", step: 3, name: "hcloud-configure-test", command: "hcloud configure test" },
    { exit_code: 0, success: true, outputTail: "default", step: 4, name: "hcloud-configure-list", command: "hcloud configure list" },
  ]);

  const result = detectKooCli({ commandRunner: mockRunner });

  assert.equal(result.installed, true);
  assert.equal(result.version, "3.2.7");
});

test("detectKooCli scrubs secrets from output", () => {
  const mockRunner = makeMockRunner([
    { exit_code: 0, success: true, outputTail: "/usr/local/bin/hcloud", step: 0, name: "detect-hcloud", command: "which hcloud" },
    { exit_code: 0, success: true, outputTail: "3.2.7", step: 1, name: "hcloud-version", command: "hcloud --version" },
    { exit_code: 0, success: true, outputTail: "AK=mysecretkey", step: 3, name: "hcloud-configure-test", command: "hcloud configure test" },
    { exit_code: 0, success: true, outputTail: "default", step: 4, name: "hcloud-configure-list", command: "hcloud configure list" },
  ]);

  const result = detectKooCli({ commandRunner: mockRunner });

  assert.ok(result.configure_test.output_summary.includes("***REDACTED***"));
  assert.ok(!result.configure_test.output_summary.includes("mysecretkey"));
});

test("buildKooCliFutureCommandPlan returns PLANNED_NOT_IMPLEMENTED entries", () => {
  const plan = buildKooCliFutureCommandPlan({
    migrationId: "test_migration",
    jobName: "test_job",
    dliQueue: "default",
    runtimeArtifactsDir: "/tmp/artifacts",
  });

  assert.equal(plan.migration_id, "test_migration");
  assert.equal(plan.job_name, "test_job");
  assert.ok(plan.categories.length >= 1);

  for (const cat of plan.categories) {
    for (const cmd of cat.commands) {
      assert.equal(cmd.implementation_status, "PLANNED_NOT_IMPLEMENTED");
    }
  }
});

test("buildKooCliFutureCommandPlan includes expected categories", () => {
  const plan = buildKooCliFutureCommandPlan({
    migrationId: "test",
    jobName: "job1",
  });

  const categoryNames = plan.categories.map((c) => c.category);
  assert.ok(categoryNames.includes("inspect_workspace"));
  assert.ok(categoryNames.includes("create_job"));
  assert.ok(categoryNames.includes("verify_job"));
  assert.ok(categoryNames.includes("trigger_run"));
  assert.ok(categoryNames.includes("query_instance"));
  assert.ok(categoryNames.includes("query_logs"));
  assert.ok(categoryNames.includes("validate_output"));
});

test("buildKooCliFutureCommandPlan includes job name in commands", () => {
  const plan = buildKooCliFutureCommandPlan({
    migrationId: "test",
    jobName: "my_job",
  });

  const createJobCat = plan.categories.find((c) => c.category === "create_job");
  assert.ok(createJobCat.commands[0].cmd.includes("my_job"));
});
