const test = require("node:test");
const assert = require("node:assert/strict");
const { runKooCliDoctor } = require("../../src/koocli/koocli-doctor");

function makeMockRunner(results) {
  let index = 0;
  return (spec) => {
    if (index < results.length) {
      return results[index++];
    }
    return { exit_code: 1, success: false, outputTail: "", step: spec.step, name: spec.name, command: spec.cmd };
  };
}

test("doctor returns KOOCLI_UNAVAILABLE when hcloud missing", () => {
  const mockRunner = makeMockRunner([
    { exit_code: 1, success: false, outputTail: "not found", step: 0, name: "detect-hcloud", command: "which hcloud" },
  ]);

  const result = runKooCliDoctor({ commandRunner: mockRunner });

  assert.equal(result.status, "KOOCLI_UNAVAILABLE");
  assert.equal(result.healthy, false);
  assert.equal(result.installed, false);
});

test("doctor returns KOOCLI_HEALTHY when hcloud installed and configured", () => {
  const mockRunner = makeMockRunner([
    { exit_code: 0, success: true, outputTail: "/usr/local/bin/hcloud", step: 0, name: "detect-hcloud", command: "which hcloud" },
    { exit_code: 0, success: true, outputTail: "3.2.7", step: 1, name: "hcloud-version", command: "hcloud --version" },
    { exit_code: 0, success: true, outputTail: "OK", step: 3, name: "hcloud-configure-test", command: "hcloud configure test" },
    { exit_code: 0, success: true, outputTail: "default", step: 4, name: "hcloud-configure-list", command: "hcloud configure list" },
  ]);

  const result = runKooCliDoctor({ commandRunner: mockRunner });

  assert.equal(result.status, "KOOCLI_HEALTHY");
  assert.equal(result.healthy, true);
  assert.equal(result.installed, true);
});

test("doctor returns KOOCLI_CONFIG_WARNING when configure has issues", () => {
  const mockRunner = makeMockRunner([
    { exit_code: 0, success: true, outputTail: "/usr/local/bin/hcloud", step: 0, name: "detect-hcloud", command: "which hcloud" },
    { exit_code: 0, success: true, outputTail: "3.2.7", step: 1, name: "hcloud-version", command: "hcloud --version" },
    { exit_code: 1, success: false, outputTail: "config error", step: 3, name: "hcloud-configure-test", command: "hcloud configure test" },
    { exit_code: 0, success: true, outputTail: "default", step: 4, name: "hcloud-configure-list", command: "hcloud configure list" },
  ]);

  const result = runKooCliDoctor({ commandRunner: mockRunner });

  assert.equal(result.status, "KOOCLI_CONFIG_WARNING");
  assert.equal(result.healthy, true);
  assert.equal(result.installed, true);
  assert.ok(result.warnings.length > 0);
});

test("doctor safety flags are present", () => {
  const mockRunner = makeMockRunner([
    { exit_code: 1, success: false, outputTail: "not found", step: 0, name: "detect-hcloud", command: "which hcloud" },
  ]);

  const result = runKooCliDoctor({ commandRunner: mockRunner });

  assert.equal(result.safety.koocli_diagnostic_only, true);
  assert.equal(result.safety.no_service_api_calls, true);
  assert.equal(result.safety.no_api_write_calls, true);
  assert.equal(result.safety.no_runtime_execution, true);
  assert.equal(result.safety.no_sql_execution, true);
  assert.equal(result.safety.no_commands_outside_allowlist, true);
});

test("doctor includes diagnostics detail", () => {
  const mockRunner = makeMockRunner([
    { exit_code: 0, success: true, outputTail: "/usr/local/bin/hcloud", step: 0, name: "detect-hcloud", command: "which hcloud" },
    { exit_code: 0, success: true, outputTail: "3.2.7", step: 1, name: "hcloud-version", command: "hcloud --version" },
    { exit_code: 0, success: true, outputTail: "OK", step: 3, name: "hcloud-configure-test", command: "hcloud configure test" },
    { exit_code: 0, success: true, outputTail: "default", step: 4, name: "hcloud-configure-list", command: "hcloud configure list" },
  ]);

  const result = runKooCliDoctor({ commandRunner: mockRunner });

  assert.ok(result.diagnostics);
  assert.equal(result.diagnostics.installed, true);
  assert.equal(result.diagnostics.version, "3.2.7");
});

test("doctor output is scrubbed", () => {
  const mockRunner = makeMockRunner([
    { exit_code: 0, success: true, outputTail: "/usr/local/bin/hcloud", step: 0, name: "detect-hcloud", command: "which hcloud" },
    { exit_code: 0, success: true, outputTail: "3.2.7", step: 1, name: "hcloud-version", command: "hcloud --version" },
    { exit_code: 0, success: true, outputTail: "SK=supersecret", step: 3, name: "hcloud-configure-test", command: "hcloud configure test" },
    { exit_code: 0, success: true, outputTail: "default", step: 4, name: "hcloud-configure-list", command: "hcloud configure list" },
  ]);

  const result = runKooCliDoctor({ commandRunner: mockRunner });

  assert.ok(result.diagnostics.configure_test.output_summary.includes("***REDACTED***"));
  assert.ok(!result.diagnostics.configure_test.output_summary.includes("supersecret"));
});
