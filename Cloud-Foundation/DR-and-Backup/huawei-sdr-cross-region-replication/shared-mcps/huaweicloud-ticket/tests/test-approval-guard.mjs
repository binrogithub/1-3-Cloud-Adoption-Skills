import { readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SRC_DIR = join(__dirname, '..', 'src');

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

test('create_ticket schema requires explicit_approval', () => {
  const serverCode = readFileSync(join(SRC_DIR, 'server.mjs'), 'utf-8');
  assert(serverCode.includes('explicit_approval'), 'explicit_approval not in server code');
  assert(serverCode.includes('"explicit_approval"'), 'explicit_approval not in tool definition');
  assert(serverCode.includes('required: ["payload", "explicit_approval"]'), 'explicit_approval not in required fields');
});

test('create_ticket rejects missing approval', () => {
  const serverCode = readFileSync(join(SRC_DIR, 'server.mjs'), 'utf-8');
  assert(serverCode.includes('APPROVAL_REQUIRED'), 'APPROVAL_REQUIRED error not implemented');
  assert(serverCode.includes('explicit_approval=true'), 'Approval requirement message not documented');
});

test('create_ticket rejects non-true approval', () => {
  const serverCode = readFileSync(join(SRC_DIR, 'server.mjs'), 'utf-8');
  assert(serverCode.includes('args.explicit_approval !== true'), 'Strict boolean check not implemented');
});

test('create_ticket validates payload', () => {
  const serverCode = readFileSync(join(SRC_DIR, 'server.mjs'), 'utf-8');
  assert(serverCode.includes('INVALID_PAYLOAD'), 'INVALID_PAYLOAD error not implemented');
  assert(serverCode.includes('typeof args.payload'), 'Payload type validation not implemented');
});

test('no real ticket created in tests', () => {
  const testCode = readFileSync(join(__dirname, 'test-session.mjs'), 'utf-8');
  assert(!testCode.includes('createTicket('), 'Test must not call createTicket directly');
  assert(testCode.includes('NOT SUBMITTED'), 'Test must document non-submission');
});

test('approval guard is before createTicket call', () => {
  const serverCode = readFileSync(join(SRC_DIR, 'server.mjs'), 'utf-8');
  const approvalPos = serverCode.indexOf('args.explicit_approval !== true');
  const createTicketPos = serverCode.indexOf('await createTicket(session, args.payload)');
  assert(approvalPos > 0, 'Approval check not found');
  assert(createTicketPos > approvalPos, 'createTicket* call must be after approval check');
});

test('error messages do not contain secrets', () => {
  const serverCode = readFileSync(join(SRC_DIR, 'server.mjs'), 'utf-8');
  const secretPatterns = [
    /AK[=:]\s*[A-Z0-9]{10,}/,
    /SK[=:]\s*[A-Z0-9]{10,}/,
    /password[=:]\s*['"][^'"]+['"]/i
  ];
  for (const pattern of secretPatterns) {
    assert(!pattern.test(serverCode), 'Found secret pattern in server code');
  }
});

console.log('\n=== Ticket Approval Guard Tests ===\n');
for (const r of results) {
  const icon = r.status === 'PASS' ? '✓' : '✗';
  console.log(`${icon} ${r.name}${r.error ? ` — ${r.error}` : ''}`);
}
console.log(`\nResults: ${passed} passed, ${failed} failed, ${passed + failed} total\n`);
process.exit(failed > 0 ? 1 : 0);
