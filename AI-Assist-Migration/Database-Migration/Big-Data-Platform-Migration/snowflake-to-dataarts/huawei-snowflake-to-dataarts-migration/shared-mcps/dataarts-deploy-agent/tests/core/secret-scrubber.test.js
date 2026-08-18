const test = require("node:test");
const assert = require("node:assert/strict");
const { scrubSecrets } = require("../../src/core/secret-scrubber");

test("scrubSecrets redacts Huawei AK and SK values", () => {
  const input = "HUAWEI_AK=abc123 HUAWEI_SK=secret456";
  const output = scrubSecrets(input);

  assert.match(output, /HUAWEI_AK= \*\*\*REDACTED\*\*\*/);
  assert.match(output, /HUAWEI_SK= \*\*\*REDACTED\*\*\*/);
  assert.doesNotMatch(output, /abc123/);
  assert.doesNotMatch(output, /secret456/);
});

test("scrubSecrets redacts password and token values", () => {
  const input = "password=myPass token=myToken";
  const output = scrubSecrets(input);

  assert.doesNotMatch(output, /myPass/);
  assert.doesNotMatch(output, /myToken/);
});
