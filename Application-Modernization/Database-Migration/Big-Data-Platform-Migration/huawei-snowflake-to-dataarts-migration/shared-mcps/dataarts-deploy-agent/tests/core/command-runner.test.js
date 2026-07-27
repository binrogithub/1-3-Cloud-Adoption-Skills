const test = require("node:test");
const assert = require("node:assert/strict");
const { runShellCommand, tailNonEmptyLines } = require("../../src/core/command-runner");

test("tailNonEmptyLines returns last non-empty lines", () => {
  const result = tailNonEmptyLines("a\n\nb\nc\nd\n", 2);

  assert.deepEqual(result, ["c", "d"]);
});

test("runShellCommand returns success result for passing command", () => {
  const result = runShellCommand({
    step: 1,
    name: "hello",
    cmd: "node -e \"console.log('hello')\"",
  });

  assert.equal(result.step, 1);
  assert.equal(result.name, "hello");
  assert.equal(result.exit_code, 0);
  assert.equal(result.success, true);
  assert.match(result.outputTail, /hello/);
});

test("runShellCommand returns failed result for failing command", () => {
  const result = runShellCommand({
    step: 2,
    name: "fail",
    cmd: "node -e \"console.error('boom'); process.exit(7)\"",
  });

  assert.equal(result.step, 2);
  assert.equal(result.name, "fail");
  assert.equal(result.exit_code, 7);
  assert.equal(result.success, false);
  assert.match(result.outputTail, /boom/);
});

test("runShellCommand scrubs secrets from output", () => {
  const result = runShellCommand({
    step: 3,
    name: "secret-output",
    cmd: "node -e \"console.log('HUAWEI_SK=super-secret-value')\"",
  });

  assert.equal(result.success, true);
  assert.match(result.outputTail, /HUAWEI_SK= \*\*\*REDACTED\*\*\*/);
  assert.doesNotMatch(result.outputTail, /super-secret-value/);
});
