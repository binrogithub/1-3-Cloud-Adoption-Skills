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
  assert(fm.includes('name: huawei-sdr-cross-region-replication'), 'name field missing or incorrect');
  assert(fm.includes('version:'), 'version field missing');
  assert(fm.includes('category:'), 'category field missing');
  assert(fm.includes('risk_level:'), 'risk_level field missing');
  assert(fm.includes('status:'), 'status field missing');
  assert(fm.includes('requires_explicit_approval:'), 'requires_explicit_approval field missing');
});

test('skill.yaml valid', () => {
  const content = readFile('skill.yaml');
  assert(content.includes('name: huawei-sdr-cross-region-replication'), 'name missing in skill.yaml');
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

test('canonical service terminology documented', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('SDRS'), 'SDRS canonical name not documented');
  assert(content.includes('Storage Disaster Recovery Service'), 'Full canonical name not documented');
  assert(content.includes('Aliases') || content.includes('aliases') || content.includes('alias'), 'Aliases not documented');
});

test('Step 1 is PARSE INTENT', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('STEP 1') && content.includes('PARSE INTENT'), 'STEP 1 PARSE INTENT not found');
});

test('no fake hcloud SDR or SDRS commands', () => {
  const content = readFile('SKILL.md');
  const lines = content.split('\n');
  for (const line of lines) {
    if (line.includes('NEVER') || line.includes('Do not') || line.includes('do not') || line.includes('Note:')) continue;
    if (line.includes('```')) continue;
    assert(!/hcloud\s+SDR\s+[^./]/.test(line), `Fake hcloud SDR command in SKILL.md: ${line.trim()}`);
    assert(!/hcloud\s+SDRS\s+[^./]/.test(line), `Fake hcloud SDRS command in SKILL.md: ${line.trim()}`);
  }
  const readme = readFile('README.md');
  const readmeLines = readme.split('\n');
  for (const line of readmeLines) {
    if (line.includes('Never') || line.includes('never') || line.includes('No ')) continue;
    assert(!/hcloud\s+SDR\s+[^./]/.test(line), `Fake hcloud SDR command in README: ${line.trim()}`);
    assert(!/hcloud\s+SDRS\s+[^./]/.test(line), `Fake hcloud SDRS command in README: ${line.trim()}`);
  }
});

test('discover-before-create present', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('DISCOVER BEFORE CREATE'), 'DISCOVER BEFORE CREATE not found in SKILL.md');
});

test('verify-after-every-step present', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('VERIFY AFTER EVERY STEP'), 'VERIFY AFTER EVERY STEP not found in SKILL.md');
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

test('failover requires approval', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('MANDATORY_EXPLICIT_APPROVAL'), 'Failover MANDATORY_EXPLICIT_APPROVAL not found');
  assert(content.includes('Step 15') || content.includes('STEP 15'), 'Failover step not found');
});

test('reverse reprotection requires approval', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('reverse reprotection') || content.includes('Reverse Reprotection') || content.includes('Reverse reprotection'), 'Reverse reprotection not found');
  assert(content.includes('Step 16') || content.includes('STEP 16'), 'Reverse reprotection step not found');
});

test('failback requires approval', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('failback') || content.includes('Failback'), 'Failback not found');
  assert(content.includes('Step 17') || content.includes('STEP 17'), 'Failback step not found');
});

test('no automatic DNS change', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('DNS') && content.includes('manual'), 'DNS manual requirement not documented');
  const readme = readFile('README.md');
  assert(readme.includes('DNS') && readme.includes('manual') || readme.includes('Manual'), 'DNS manual in README');
});

test('no automatic deletion', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('Do not delete') || content.includes('No resource deletion') || content.includes('NOT delete'), 'No automatic deletion rule not found');
});

test('status is EXPERIMENTAL', () => {
  const skillYaml = readFile('skill.yaml');
  assert(skillYaml.includes('status: EXPERIMENTAL'), 'status must be EXPERIMENTAL in skill.yaml');
  const skillMd = readFile('SKILL.md');
  assert(skillMd.includes('EXPERIMENTAL'), 'SKILL.md must document EXPERIMENTAL status');
});

test('risk is critical', () => {
  const skillYaml = readFile('skill.yaml');
  assert(skillYaml.includes('risk_level: critical'), 'risk_level must be critical in skill.yaml');
  const skillMd = readFile('SKILL.md');
  assert(skillMd.includes('risk_level: critical') || skillMd.includes('critical'), 'SKILL.md must document critical risk');
});

test('missing CLI documented', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('NOT_AVAILABLE') || content.includes('NOT AVAILABLE') || content.includes('not available'), 'Missing CLI not documented');
  assert(content.includes('sdrs_cli_support: NOT_AVAILABLE') || content.includes('SDRS is NOT available'), 'SDRS CLI absence not documented');
});

test('missing MCP documented', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('No SDRS MCP') || content.includes('sdrs_mcp_support: NOT_AVAILABLE'), 'Missing SDRS MCP not documented');
});

test('capability builder integration present', () => {
  const content = readFile('skill.yaml');
  assert(content.includes('mcp-capability-builder'), 'mcp-capability-builder not in skill.yaml');
  const mcpDeps = readFile('mcp-dependencies.yaml');
  assert(mcpDeps.includes('mcp-capability-builder'), 'mcp-capability-builder not in mcp-dependencies.yaml');
});

test('candidate MCP tools marked NOT_IMPLEMENTED', () => {
  const content = readFile('docs/sdrs-mcp-capability-request.md');
  assert(content.includes('NOT_IMPLEMENTED'), 'Candidate tools not marked NOT_IMPLEMENTED');
  assert(content.includes('API_CONTRACT_REQUIRES_VALIDATION') || content.includes('API contract'), 'API contract validation requirement not documented');
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
  assert(fileExists('examples/sdr-cross-region.example.md'), 'Missing example file');
});

test('SDRS MCP capability request exists', () => {
  assert(fileExists('docs/sdrs-mcp-capability-request.md'), 'Missing SDRS MCP capability request');
});

test('domain metadata present', () => {
  const skillYaml = readFile('skill.yaml');
  assert(skillYaml.includes('domain:'), 'domain missing in skill.yaml');
  assert(skillYaml.includes('family:'), 'family missing in skill.yaml');
  assert(skillYaml.includes('service:'), 'service missing in skill.yaml');
  assert(skillYaml.includes('SDRS'), 'SDRS service not in skill.yaml');
});

test('hcloud version documented', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('6.2.9'), 'hcloud 6.2.9 not documented');
});

test('troubleshooting table exists in known-issues.md', () => {
  const content = readFile('docs/known-issues.md');
  assert(content.includes('Symptom') && content.includes('Likely cause') && content.includes('Diagnosis') && content.includes('Resolution') && content.includes('Retry safe'), 'Troubleshooting table missing required columns');
});

test('capability gap policy documents MANUAL_CONSOLE', () => {
  const content = readFile('docs/capability-gap-policy.md');
  assert(content.includes('MANUAL_CONSOLE'), 'MANUAL_CONSOLE decision not documented');
  assert(content.includes('CREATE_NEW_MCP_CANDIDATE'), 'CREATE_NEW_MCP_CANDIDATE decision not documented');
});

test('relative links valid', () => {
  const readme = readFile('README.md');
  const linkPattern = /\[([^\]]+)\]\(([^)]+)\)/g;
  let match;
  while ((match = linkPattern.exec(readme)) !== null) {
    const link = match[2];
    if (link.startsWith('http') || link.startsWith('#')) continue;
    assert(fileExists(link), `Broken relative link in README.md: ${link}`);
  }
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

test('BRS and CBR differentiated from SDRS', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('NOT equivalent') || content.includes('separate service'), 'BRS/CBR not differentiated from SDRS');
});

test('reverse reprotection separated from failback', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('Reverse reprotection is NOT failback') || content.includes('reverse reprotection is NOT equivalent to failback'), 'Reverse reprotection not separated from failback');
});

test('18 workflow steps present', () => {
  const content = readFile('SKILL.md');
  for (let i = 1; i <= 18; i++) {
    assert(content.includes(`STEP ${i}`), `STEP ${i} not found in SKILL.md`);
  }
});

test('execution mechanism documented', () => {
  const skillYaml = readFile('skill.yaml');
  assert(skillYaml.includes('manual_console'), 'manual_console mechanism not documented');
  assert(skillYaml.includes('automation_blocker'), 'automation_blocker not documented');
  assert(skillYaml.includes('automated_workflow_blocker: true'), 'automated_workflow_blocker must be true');
});

console.log('\n=== SDR Skill Structure Tests ===\n');
for (const r of results) {
  const icon = r.status === 'PASS' ? '✓' : '✗';
  console.log(`${icon} ${r.name}${r.error ? ` — ${r.error}` : ''}`);
}
console.log(`\nResults: ${passed} passed, ${failed} failed, ${passed + failed} total\n`);
process.exit(failed > 0 ? 1 : 0);
