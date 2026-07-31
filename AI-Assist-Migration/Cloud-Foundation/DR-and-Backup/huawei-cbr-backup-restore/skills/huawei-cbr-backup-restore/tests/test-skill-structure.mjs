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

test('README.md exists', () => {
  assert(fileExists('README.md'), 'README.md not found');
});

test('skill.yaml exists', () => {
  assert(fileExists('skill.yaml'), 'skill.yaml not found');
});

test('mcp-dependencies.yaml exists', () => {
  assert(fileExists('mcp-dependencies.yaml'), 'mcp-dependencies.yaml not found');
});

test('YAML frontmatter valid in SKILL.md', () => {
  const content = readFile('SKILL.md');
  assert(content.startsWith('---'), 'SKILL.md must start with YAML frontmatter');
  const end = content.indexOf('---', 3);
  assert(end > 0, 'SKILL.md frontmatter must be closed');
  const fm = content.slice(3, end);
  assert(fm.includes('name: huawei-cbr-backup-restore'), 'name field missing or incorrect');
  assert(fm.includes('version:'), 'version field missing');
  assert(fm.includes('category:'), 'category field missing');
  assert(fm.includes('risk_level:'), 'risk_level field missing');
  assert(fm.includes('status:'), 'status field missing');
  assert(fm.includes('requires_explicit_approval:'), 'requires_explicit_approval field missing');
});

test('skill.yaml valid', () => {
  const content = readFile('skill.yaml');
  assert(content.includes('name: huawei-cbr-backup-restore'), 'name missing in skill.yaml');
  assert(content.includes('version:'), 'version missing in skill.yaml');
  assert(content.includes('category:'), 'category missing in skill.yaml');
  assert(content.includes('status:'), 'status missing in skill.yaml');
  assert(content.includes('risk_level:'), 'risk_level missing in skill.yaml');
  assert(content.includes('requires_explicit_approval:'), 'requires_explicit_approval missing in skill.yaml');
});

test('mcp-dependencies.yaml valid', () => {
  const content = readFile('mcp-dependencies.yaml');
  assert(content.includes('required_mcps:'), 'required_mcps missing');
  assert(content.includes('optional_mcps:'), 'optional_mcps missing');
});

test('required sections exist in SKILL.md', () => {
  const content = readFile('SKILL.md');
  const sections = [
    '# Purpose',
    '# Supported scenario',
    '# When to use this skill',
    '# When not to use this skill',
    '# Required inputs',
    '# Optional inputs',
    '# Required MCPs',
    '# Optional MCPs',
    '# Tool selection policy',
    '# Safety and approval gates',
    '# Rules',
    '# Prerequisites',
    '# Workflow',
    '# Capability gap handling',
    '# Output artifacts',
    '# Failure handling',
    '# Recovery procedure',
    '# Evidence and traceability',
    '# Known limitations',
    '# Status justification'
  ];
  for (const section of sections) {
    assert(content.includes(section), `Missing section: ${section}`);
  }
});

test('Step 1 is PARSE INTENT', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('STEP 1') && content.includes('PARSE INTENT'), 'STEP 1 PARSE INTENT not found');
});

test('discover-before-create language exists', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('DISCOVER BEFORE CREATE'), 'DISCOVER BEFORE CREATE not found in SKILL.md');
});

test('every write phase declares approval', () => {
  const content = readFile('SKILL.md');
  const writeSteps = [
    'STEP 6',
    'STEP 7',
    'STEP 8',
    'STEP 9',
    'STEP 12'
  ];
  for (const step of writeSteps) {
    assert(content.includes(step), `${step} not found`);
  }
  assert(content.includes('EXPLICIT'), 'No EXPLICIT approval declaration found');
});

test('verification exists after each write', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('VERIFY AFTER EVERY STEP'), 'VERIFY AFTER EVERY STEP not found');
  const verifyPatterns = ['ShowVault', 'ShowBackup', 'ShowPolicy', 'ListBackups'];
  for (const p of verifyPatterns) {
    assert(content.includes(p), `Verification pattern ${p} not found`);
  }
});

test('no hardcoded IDs', () => {
  const content = readFile('SKILL.md');
  const uuidPattern = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;
  assert(!uuidPattern.test(content), 'Found hardcoded UUID in SKILL.md');
});

test('no secrets', () => {
  const files = ['SKILL.md', 'README.md', 'skill.yaml', 'mcp-dependencies.yaml'];
  const secretPatterns = [
    /AK[=:]\s*[A-Z0-9]{10,}/,
    /SK[=:]\s*[A-Z0-9]{10,}/,
    /password[=:]\s*['"][^'"]+['"]/i,
    /secret[=:]\s*['"][^'"]+['"]/i,
    /private_key[=:]\s*['"]/i
  ];
  for (const file of files) {
    const content = readFile(file);
    for (const pattern of secretPatterns) {
      assert(!pattern.test(content), `Found secret pattern in ${file}`);
    }
  }
});

test('hcloud version is documented', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('6.2.9'), 'hcloud 6.2.9 not documented');
  assert(content.includes('7.2.12'), 'hcloud 7.2.12 pending validation not documented');
});

test('no unsupported CBR MCP is declared', () => {
  const content = readFile('SKILL.md');
  assert(!content.includes('huaweicloud-cbr'), 'Must not declare a non-existent CBR MCP');
  const skillYaml = readFile('skill.yaml');
  const requiredMcpsMatch = skillYaml.match(/required:\s*\[([^\]]*)\]/);
  if (requiredMcpsMatch) {
    assert(!requiredMcpsMatch[1].includes('cbr'), 'Must not require a CBR MCP');
  }
});

test('optional MCP paths exist', () => {
  const content = readFile('mcp-dependencies.yaml');
  assert(content.includes('huaweicloud-pricing'), 'huaweicloud-pricing not in optional MCPs');
  assert(content.includes('huaweicloud-ticket'), 'huaweicloud-ticket not in optional MCPs');
  assert(content.includes('huaweicloud-deploy'), 'huaweicloud-deploy not in optional MCPs');
});

test('relative links work', () => {
  const readme = readFile('README.md');
  const linkPattern = /\[([^\]]+)\]\(([^)]+)\)/g;
  let match;
  while ((match = linkPattern.exec(readme)) !== null) {
    const link = match[2];
    if (link.startsWith('http') || link.startsWith('#')) continue;
    assert(fileExists(link), `Broken relative link in README.md: ${link}`);
  }
});

test('status is READY_WITH_WARNINGS', () => {
  const skillYaml = readFile('skill.yaml');
  assert(skillYaml.includes('status: READY_WITH_WARNINGS'), 'status must be READY_WITH_WARNINGS');
  const skillMd = readFile('SKILL.md');
  assert(skillMd.includes('READY_WITH_WARNINGS'), 'SKILL.md must document READY_WITH_WARNINGS status');
});

test('docs files exist', () => {
  const docs = [
    'docs/architecture.md',
    'docs/prerequisites.md',
    'docs/execution-runbook.md',
    'docs/validation.md',
    'docs/rollback.md',
    'docs/known-issues.md',
    'docs/lessons-learned.md',
    'docs/capability-gap-policy.md'
  ];
  for (const doc of docs) {
    assert(fileExists(doc), `Missing doc: ${doc}`);
  }
});

test('workflow files exist', () => {
  const workflows = [
    'workflows/discovery.md',
    'workflows/readiness.md',
    'workflows/execution.md',
    'workflows/validation.md',
    'workflows/rollback.md'
  ];
  for (const wf of workflows) {
    assert(fileExists(wf), `Missing workflow: ${wf}`);
  }
});

test('prompt files exist', () => {
  const prompts = [
    'prompts/discovery-prompt.md',
    'prompts/execution-prompt.md',
    'prompts/recovery-prompt.md'
  ];
  for (const p of prompts) {
    assert(fileExists(p), `Missing prompt: ${p}`);
  }
});

test('example file exists', () => {
  assert(fileExists('examples/cbr-backup-restore.example.md'), 'Missing example file');
});

test('domain metadata present', () => {
  const skillYaml = readFile('skill.yaml');
  assert(skillYaml.includes('domain:'), 'domain missing in skill.yaml');
  assert(skillYaml.includes('family:'), 'family missing in skill.yaml');
  assert(skillYaml.includes('service:'), 'service missing in skill.yaml');
});

test('hcloud operations documented in skill.yaml', () => {
  const skillYaml = readFile('skill.yaml');
  assert(skillYaml.includes('hcloud:'), 'hcloud section missing');
  assert(skillYaml.includes('verified_version: 6.2.9'), 'verified_version not documented');
  assert(skillYaml.includes('newer_version_pending: 7.2.12'), 'newer_version_pending not documented');
  assert(skillYaml.includes('operations_verified:'), 'operations_verified not documented');
});

test('troubleshooting table exists in known-issues.md', () => {
  const content = readFile('docs/known-issues.md');
  assert(content.includes('Symptom') && content.includes('Likely cause') && content.includes('Diagnostic command') && content.includes('Resolution') && content.includes('Retry safe'), 'Troubleshooting table missing required columns');
});

test('capability gap policy documents USE_HCLOUD_CLI', () => {
  const content = readFile('docs/capability-gap-policy.md');
  assert(content.includes('USE_HCLOUD_CLI'), 'USE_HCLOUD_CLI decision not documented');
  assert(content.includes('No dedicated CBR MCP'), 'Gap description missing');
});

console.log('\n=== CBR Skill Structure Tests ===\n');
for (const r of results) {
  const icon = r.status === 'PASS' ? '✓' : '✗';
  console.log(`${icon} ${r.name}${r.error ? ` — ${r.error}` : ''}`);
}
console.log(`\nResults: ${passed} passed, ${failed} failed, ${passed + failed} total\n`);
process.exit(failed > 0 ? 1 : 0);
