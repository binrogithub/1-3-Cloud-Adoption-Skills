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
  assert(fileExists('references/legacy-skill-readme.md'), 'references/legacy-skill-readme.md not found');
});

test('skill.yaml exists', () => {
  assert(fileExists('assets/metadata/skill.yaml'), 'assets/metadata/skill.yaml not found');
});

test('mcp-dependencies.yaml exists', () => {
  assert(fileExists('assets/metadata/mcp-dependencies.yaml'), 'assets/metadata/mcp-dependencies.yaml not found');
});

test('YAML frontmatter valid in SKILL.md', () => {
  const content = readFile('SKILL.md');
  assert(content.startsWith('---'), 'SKILL.md must start with YAML frontmatter');
  const end = content.indexOf('---', 3);
  assert(end > 0, 'SKILL.md frontmatter must be closed');
  const fm = content.slice(3, end);
  assert(fm.includes('name: huawei-dws-cluster-deployment'), 'name field missing or incorrect');
  assert(fm.includes('version:'), 'version field missing');
  assert(fm.includes('category:'), 'category field missing');
  assert(fm.includes('risk_level:'), 'risk_level field missing');
  assert(fm.includes('status:'), 'status field missing');
  assert(fm.includes('requires_explicit_approval:'), 'requires_explicit_approval field missing');
});

test('skill.yaml valid', () => {
  const content = readFile('assets/metadata/skill.yaml');
  assert(content.includes('name: huawei-dws-cluster-deployment'), 'name missing in skill.yaml');
  assert(content.includes('version:'), 'version missing in skill.yaml');
  assert(content.includes('category:'), 'category missing in skill.yaml');
  assert(content.includes('status:'), 'status missing in skill.yaml');
  assert(content.includes('risk_level:'), 'risk_level missing in skill.yaml');
  assert(content.includes('requires_explicit_approval:'), 'requires_explicit_approval missing in skill.yaml');
});

test('mcp-dependencies.yaml valid', () => {
  const content = readFile('assets/metadata/mcp-dependencies.yaml');
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

test('discover-before-create exists', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('DISCOVER BEFORE CREATE'), 'DISCOVER BEFORE CREATE not found in SKILL.md');
});

test('verify-after-every-step exists', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('VERIFY AFTER EVERY STEP'), 'VERIFY AFTER EVERY STEP not found in SKILL.md');
});

test('no hardcoded IDs', () => {
  const content = readFile('SKILL.md');
  const uuidPattern = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;
  assert(!uuidPattern.test(content), 'Found hardcoded UUID in SKILL.md');
});

test('no secrets', () => {
  const files = ['SKILL.md', 'references/legacy-skill-readme.md', 'assets/metadata/skill.yaml', 'assets/metadata/mcp-dependencies.yaml'];
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

test('no plain-text password examples', () => {
  const content = readFile('SKILL.md');
  assert(!content.match(/--cluster\.user_pwd=[^\s<]/), 'Password should not be directly embedded in command');
});

test('hcloud version documented', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('6.2.9'), 'hcloud 6.2.9 not documented');
  assert(content.includes('7.2.12'), 'hcloud 7.2.12 pending validation not documented');
});

test('no unsupported DWS MCP declared', () => {
  const content = readFile('SKILL.md');
  assert(!content.includes('huaweicloud-dws'), 'Must not declare a non-existent DWS MCP');
  const skillYaml = readFile('assets/metadata/skill.yaml');
  const requiredMcpsMatch = skillYaml.match(/required:\s*\[([^\]]*)\]/);
  if (requiredMcpsMatch) {
    assert(!requiredMcpsMatch[1].includes('dws'), 'Must not require a DWS MCP');
  }
});

test('huaweicloud-deploy not described as DWS-capable', () => {
  const content = readFile('assets/metadata/mcp-dependencies.yaml');
  assert(content.includes('DWS is NOT supported'), 'Must document that deploy MCP does not support DWS');
});

test('capability gap is EXTEND_EXISTING_MCP', () => {
  const content = readFile('references/capability-gap-policy.md');
  assert(content.includes('EXTEND_EXISTING_MCP'), 'EXTEND_EXISTING_MCP decision not documented');
});

test('all writes require approval', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('EXPLICIT REQUIRED'), 'No EXPLICIT REQUIRED approval found');
  assert(content.includes('EXPLICIT APPROVAL REQUIRED'), 'No EXPLICIT APPROVAL REQUIRED found');
});

test('CreateCluster has verification', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('CreateCluster'), 'CreateCluster not mentioned');
  assert(content.includes('ListClusters'), 'ListClusters verification not mentioned');
});

test('EIP binding has verification', () => {
  const content = readFile('SKILL.md');
  const readme = readFile('references/legacy-skill-readme.md');
  assert(content.includes('EIP') || readme.includes('EIP'), 'EIP not mentioned');
});

test('snapshot creation has verification', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('CreateSnapshot'), 'CreateSnapshot not mentioned');
  assert(content.includes('ListSnapshots'), 'ListSnapshots verification not mentioned');
});

test('no automatic delete', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('Never execute delete or restore automatically'), 'No automatic delete rule not found');
});

test('no automatic restore', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('RestoreCluster requires explicit approval'), 'RestoreCluster approval not found');
});

test('optional MCP paths exist', () => {
  const content = readFile('assets/metadata/mcp-dependencies.yaml');
  assert(content.includes('huaweicloud-pricing'), 'huaweicloud-pricing not in optional MCPs');
  assert(content.includes('huaweicloud-ticket'), 'huaweicloud-ticket not in optional MCPs');
  assert(content.includes('huaweicloud-deploy'), 'huaweicloud-deploy not in optional MCPs');
});

test('relative links work', () => {
  const readme = readFile('references/legacy-skill-readme.md');
  const linkPattern = /\[([^\]]+)\]\(([^)]+)\)/g;
  let match;
  while ((match = linkPattern.exec(readme)) !== null) {
    const link = match[2];
    if (link.startsWith('http') || link.startsWith('#')) continue;
    assert(fileExists(link), `Broken relative link in README.md: ${link}`);
  }
});

test('status is READY_WITH_WARNINGS', () => {
  const skillYaml = readFile('assets/metadata/skill.yaml');
  assert(skillYaml.includes('status: READY_WITH_WARNINGS'), 'status must be READY_WITH_WARNINGS');
  const skillMd = readFile('SKILL.md');
  assert(skillMd.includes('READY_WITH_WARNINGS'), 'SKILL.md must document READY_WITH_WARNINGS status');
});

test('risk is high', () => {
  const skillYaml = readFile('assets/metadata/skill.yaml');
  assert(skillYaml.includes('risk_level: high'), 'risk_level must be high');
});

test('docs files exist', () => {
  const docs = [
    'references/architecture.md',
    'references/prerequisites.md',
    'references/execution-runbook.md',
    'references/validation.md',
    'references/rollback.md',
    'references/known-issues.md',
    'references/lessons-learned.md',
    'references/capability-gap-policy.md'
  ];
  for (const doc of docs) {
    assert(fileExists(doc), `Missing doc: ${doc}`);
  }
});

test('workflow files exist', () => {
  const workflows = [
    'references/workflows/discovery.md',
    'references/workflows/readiness.md',
    'references/workflows/execution.md',
    'references/workflows/validation.md',
    'references/workflows/rollback.md'
  ];
  for (const wf of workflows) {
    assert(fileExists(wf), `Missing workflow: ${wf}`);
  }
});

test('prompt files exist', () => {
  const prompts = [
    'references/prompts/discovery-prompt.md',
    'references/prompts/execution-prompt.md',
    'references/prompts/recovery-prompt.md'
  ];
  for (const p of prompts) {
    assert(fileExists(p), `Missing prompt: ${p}`);
  }
});

test('example file exists', () => {
  assert(fileExists('assets/examples/dws-cluster-deployment.example.md'), 'Missing example file');
});

test('domain metadata present', () => {
  const skillYaml = readFile('assets/metadata/skill.yaml');
  assert(skillYaml.includes('domain:'), 'domain missing in skill.yaml');
  assert(skillYaml.includes('family:'), 'family missing in skill.yaml');
  assert(skillYaml.includes('service:'), 'service missing in skill.yaml');
});

test('hcloud operations documented in skill.yaml', () => {
  const skillYaml = readFile('assets/metadata/skill.yaml');
  assert(skillYaml.includes('hcloud:'), 'hcloud section missing');
  assert(skillYaml.includes('verified_version: 6.2.9'), 'verified_version not documented');
  assert(skillYaml.includes('newer_version_pending: 7.2.12'), 'newer_version_pending not documented');
  assert(skillYaml.includes('operations_verified:'), 'operations_verified not documented');
});

test('troubleshooting table exists in known-issues.md', () => {
  const content = readFile('references/known-issues.md');
  assert(content.includes('Symptom') && content.includes('Likely cause') && content.includes('Diagnostic command') && content.includes('Resolution') && content.includes('Retry safe'), 'Troubleshooting table missing required columns');
});

test('capability gap policy documents EXTEND_EXISTING_MCP', () => {
  const content = readFile('references/capability-gap-policy.md');
  assert(content.includes('EXTEND_EXISTING_MCP'), 'EXTEND_EXISTING_MCP decision not documented');
});

test('mcp extension request exists', () => {
  assert(fileExists('references/dws-mcp-extension-request.md'), 'MCP extension request doc missing');
});

test('mcp extension tools are NOT_IMPLEMENTED', () => {
  const content = readFile('references/dws-mcp-extension-request.md');
  assert(content.includes('NOT_IMPLEMENTED'), 'Tools must be marked NOT_IMPLEMENTED');
});

test('shared skill mcp-capability-builder required', () => {
  const content = readFile('assets/metadata/mcp-dependencies.yaml');
  assert(content.includes('mcp-capability-builder'), 'mcp-capability-builder not declared');
});

test('password security policy in skill.yaml', () => {
  const content = readFile('assets/metadata/skill.yaml');
  assert(content.includes('password_policy:'), 'password_policy missing');
  assert(content.includes('never_in_command_line:'), 'never_in_command_line missing');
  assert(content.includes('prefer_cli_json_input:'), 'prefer_cli_json_input missing');
});

test('CreateCluster polling documented', () => {
  const content = readFile('SKILL.md');
  assert(content.includes('STEP 12') && content.includes('Poll'), 'Polling step not found');
  assert(content.includes('timeout'), 'Timeout not documented for polling');
  assert(content.includes('failure'), 'Failure handling not documented for polling');
});

test('examples sanitized', () => {
  const content = readFile('assets/examples/dws-cluster-deployment.example.md');
  const uuidPattern = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;
  assert(!uuidPattern.test(content), 'Found hardcoded UUID in example');
  assert(content.includes('<REGION>'), 'Example should use placeholder for region');
  assert(content.includes('<CLUSTER') || content.includes('<DWS_CLUSTER_NAME>'), 'Example should use placeholder for cluster name');
});

test('20 workflow steps in SKILL.md', () => {
  const content = readFile('SKILL.md');
  for (let i = 1; i <= 20; i++) {
    assert(content.includes(`STEP ${i}`), `STEP ${i} not found in SKILL.md`);
  }
});

test('approval gates documented in skill.yaml', () => {
  const content = readFile('assets/metadata/skill.yaml');
  assert(content.includes('approval_gates:'), 'approval_gates missing');
  assert(content.includes('create_cluster'), 'create_cluster approval gate missing');
  assert(content.includes('delete_cluster'), 'delete_cluster approval gate missing');
});

test('execution mechanism documented', () => {
  const content = readFile('assets/metadata/skill.yaml');
  assert(content.includes('primary_mechanism: hcloud_dws_cli'), 'primary_mechanism not documented');
  assert(content.includes('automation_blocker:'), 'automation_blocker not documented');
});

console.log('\n=== DWS Skill Structure Tests ===\n');
for (const r of results) {
  const icon = r.status === 'PASS' ? '✓' : '✗';
  console.log(`${icon} ${r.name}${r.error ? ` — ${r.error}` : ''}`);
}
console.log(`\nResults: ${passed} passed, ${failed} failed, ${passed + failed} total\n`);
process.exit(failed > 0 ? 1 : 0);
