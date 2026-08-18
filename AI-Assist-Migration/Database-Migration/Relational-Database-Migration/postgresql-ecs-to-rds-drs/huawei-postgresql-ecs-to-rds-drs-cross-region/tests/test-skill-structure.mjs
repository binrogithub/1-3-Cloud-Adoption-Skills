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
  assert(fm.includes('name: huawei-postgresql-ecs-to-rds-drs-cross-region'), 'name field missing or incorrect');
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
  assert(fm.includes('status: READY_WITH_WARNINGS'), 'status must be READY_WITH_WARNINGS');
  assert(fm.includes('risk_level: high'), 'risk_level must be high');
});

test('Rules section exists', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('# Rules'), 'Rules section missing');
});

test('VPN is OUT_OF_SCOPE', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('OUT_OF_SCOPE_FOR_THIS_SCENARIO'), 'VPN OUT_OF_SCOPE not documented');
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

test('DRS MCP required', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('huaweicloud-drs'), 'DRS MCP not declared as required');
});

test('explicit_approval documented', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('explicit_approval'), 'explicit_approval not documented');
});

test('CIDR /32 guard documented', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('/32'), '/32 CIDR guard not documented');
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
  assert(content.includes('GAP-PG-'), 'PG capability gaps not documented');
});

test('status is READY_WITH_WARNINGS in body', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('READY_WITH_WARNINGS'), 'READY_WITH_WARNINGS status not documented in body');
});

test('EIP architecture documented', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('EIP'), 'EIP architecture not documented');
});

test('pre-check and connection test required before start', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('pre-check') || content.includes('precheck') || content.includes('Pre-check'), 'Pre-check requirement not documented');
  assert(content.includes('connection test') || content.includes('Connection test'), 'Connection test requirement not documented');
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

console.log('\n=== PostgreSQL DRS Skill Structure Tests ===\n');
for (const r of results) {
  const icon = r.status === 'PASS' ? '✓' : '✗';
  console.log(`${icon} ${r.name}${r.error ? ` — ${r.error}` : ''}`);
}
console.log(`\nResults: ${passed} passed, ${failed} failed, ${passed + failed} total\n`);
process.exit(failed > 0 ? 1 : 0);
