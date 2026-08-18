import { readFileSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SKILL_DIR = join(__dirname, '..');

let passed = 0;
let failed = 0;
const results = [];

function test(name, fn) {
  try {
    fn();
    passed++;
    results.push({ name, status: 'PASS' });
  } catch (e) {
    failed++;
    results.push({ name, status: 'FAIL', error: e.message });
  }
}

function assert(condition, message) {
  if (!condition) throw new Error(message || 'Assertion failed');
}

function readFile(relativePath) {
  const fullPath = join(SKILL_DIR, relativePath);
  if (!existsSync(fullPath)) throw new Error(`File not found: ${relativePath}`);
  return readFileSync(fullPath, 'utf-8');
}

function fileExists(relativePath) {
  return existsSync(join(SKILL_DIR, relativePath));
}

test('SKILL.md exists', () => {
  assert(fileExists('SKILL.md'), 'SKILL.md not found');
});

test('YAML frontmatter valid in SKILL.md', () => {
  const content = readFile('SKILL.md');
  assert(content.startsWith('---'), 'SKILL.md must start with YAML frontmatter');
  const end = content.indexOf('---', 3);
  assert(end > 0, 'SKILL.md frontmatter must be closed');
  const fm = content.slice(3, end);
  assert(fm.includes('name: huawei-snowflake-to-dataarts-migration'), 'name field missing or incorrect');
  assert(fm.includes('version:'), 'version field missing');
  assert(fm.includes('category:'), 'category field missing');
  assert(fm.includes('risk_level:'), 'risk_level field missing');
  assert(fm.includes('status:'), 'status field missing');
  assert(fm.includes('requires_explicit_approval:'), 'requires_explicit_approval field missing');
  assert(fm.includes('license:'), 'license field missing');
  assert(fm.includes('compatibility:'), 'compatibility field missing');
  assert(fm.includes('metadata:'), 'metadata field missing');
});

test('frontmatter has correct status and risk', () => {
  const content = readFile('SKILL.md');
  const end = content.indexOf('---', 3);
  const fm = content.slice(3, end);
  assert(fm.includes('status: PARTIAL'), 'status must be PARTIAL');
  assert(fm.includes('risk_level: medium'), 'risk_level must be medium');
});

test('Rules section exists', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('# Rules'), 'Rules section missing');
});

test('demo/POC limitation documented', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('demo') || content.includes('POC'), 'Demo/POC limitation not documented');
});

test('Prerequisites section exists with table', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('# Prerequisites'), 'Prerequisites section missing');
  assert(content.includes('Tool or resource'), 'Prerequisites table header missing');
  assert(content.includes('Required'), 'Prerequisites Required column missing');
  assert(content.includes('Purpose'), 'Prerequisites Purpose column missing');
  assert(content.includes('Verification'), 'Prerequisites Verification column missing');
});

test('Workflow starts with PARSE INTENT', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('STEP 1') && content.includes('PARSE INTENT'), 'STEP 1 PARSE INTENT not found');
});

test('Troubleshooting section exists', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('# Troubleshooting'), 'Troubleshooting section missing');
  assert(content.includes('Symptom'), 'Troubleshooting table missing Symptom column');
  assert(content.includes('Likely cause'), 'Troubleshooting table missing Likely cause column');
  assert(content.includes('Resolution'), 'Troubleshooting table missing Resolution column');
});

test('dataarts-deploy-agent MCP required', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('dataarts-deploy-agent'), 'dataarts-deploy-agent MCP not declared');
});

test('confirm=true required for writes', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('confirm=true'), 'confirm=true requirement not documented');
});

test('no hardcoded IDs', () => {
  const content = readFile('SKILL.md');
  const uuidPattern = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;
  assert(!uuidPattern.test(content), 'Found hardcoded UUID in SKILL.md');
});

test('no secrets', () => {
  const content = readFile('SKILL.md');
  const secretPatterns = [
    /AK[=:]\s*[A-Z0-9]{10,}/,
    /SK[=:]\s*[A-Z0-9]{10,}/,
    /password[=:]\s*['"][^'"]+['"]/i,
    /private_key[=:]\s*['"]/i
  ];
  for (const pattern of secretPatterns) {
    assert(!pattern.test(content), `Found secret pattern in SKILL.md`);
  }
});

test('capability gaps documented', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('GAP-DA-'), 'DataArts capability gaps not documented');
});

test('status is PARTIAL in body', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('PARTIAL'), 'PARTIAL status not documented in body');
});

test('secret scrubbing documented', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('scrub') || content.includes('Scrubbing'), 'Secret scrubbing not documented');
});

test('equivalence validation documented', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('equivalence'), 'Equivalence validation not documented');
});

test('relative links valid in README', () => {
  if (!fileExists('README.md')) return;
  const readme = readFile('README.md');
  const linkPattern = /\[([^\]]+)\]\(([^)]+)\)/g;
  let match;
  while ((match = linkPattern.exec(readme)) !== null) {
    const link = match[2];
    if (link.startsWith('http') || link.startsWith('#')) continue;
    assert(fileExists(link), `Broken relative link in README.md: ${link}`);
  }
});

console.log('\n=== Snowflake DataArts Skill Structure Tests ===\n');
for (const r of results) {
  const icon = r.status === 'PASS' ? '✓' : '✗';
  console.log(`${icon} ${r.name}${r.error ? ` — ${r.error}` : ''}`);
}
console.log(`\nResults: ${passed} passed, ${failed} failed, ${passed + failed} total\n`);
process.exit(failed > 0 ? 1 : 0);
