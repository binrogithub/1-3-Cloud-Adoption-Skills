const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { ensureDir, readJsonSafe, writeJson } = require("../../src/core/json-file");

test("writeJson creates parent folders and writes JSON", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "migration-core-"));
  const filePath = path.join(dir, "nested", "result.json");

  writeJson(filePath, { status: "PASS" });

  const result = JSON.parse(fs.readFileSync(filePath, "utf-8"));
  assert.equal(result.status, "PASS");
});

test("readJsonSafe returns null for missing file", () => {
  const result = readJsonSafe("/tmp/file-that-does-not-exist.json");
  assert.equal(result, null);
});

test("readJsonSafe returns parse error object for invalid JSON", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "migration-core-"));
  const filePath = path.join(dir, "bad.json");

  ensureDir(dir);
  fs.writeFileSync(filePath, "{bad-json", "utf-8");

  const result = readJsonSafe(filePath);

  assert.ok(result._parse_error);
  assert.equal(result._file_path, filePath);
});
