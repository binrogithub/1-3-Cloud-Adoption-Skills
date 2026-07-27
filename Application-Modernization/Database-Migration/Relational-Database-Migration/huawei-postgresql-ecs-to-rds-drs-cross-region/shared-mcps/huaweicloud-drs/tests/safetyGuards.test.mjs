import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { redactSecrets, rejectBroadCidr, validateStartConditions, validateCreateConditions } from '../src/safetyGuards.mjs';

describe('safetyGuards - redactSecrets', () => {
  it('redacts password=xxx patterns', () => {
    const result = redactSecrets('password=mysecret123');
    assert.ok(!result.includes('mysecret123'));
    assert.ok(result.includes('[REDACTED]'));
  });

  it('redacts password: xxx patterns', () => {
    const result = redactSecrets('password: mysecret123');
    assert.ok(!result.includes('mysecret123'));
    assert.ok(result.includes('[REDACTED]'));
  });

  it('redacts AK/SK patterns', () => {
    const result = redactSecrets('access_key=AKIA1234567890 secret_key=sk1234567890');
    assert.ok(!result.includes('AKIA1234567890'));
    assert.ok(!result.includes('sk1234567890'));
  });

  it('redacts token patterns', () => {
    const result = redactSecrets('token=abc123def456');
    assert.ok(!result.includes('abc123def456'));
  });

  it('redacts private key markers', () => {
    const result = redactSecrets('-----BEGIN RSA PRIVATE KEY-----');
    assert.ok(!result.includes('PRIVATE KEY'));
  });

  it('leaves non-secret text unchanged', () => {
    const input = 'task_name=pg-ecs-to-rds-cross-region status=Configuration';
    assert.equal(redactSecrets(input), input);
  });

  it('handles null and undefined', () => {
    assert.equal(redactSecrets(null), null);
    assert.equal(redactSecrets(undefined), undefined);
  });
});

describe('safetyGuards - rejectBroadCidr', () => {
  it('rejects 0.0.0.0/0 for port 5432', () => {
    const result = rejectBroadCidr('0.0.0.0/0', 5432);
    assert.equal(result.allowed, false);
    assert.ok(result.reason.includes('0.0.0.0/0'));
  });

  it('rejects 0.0.0.0/0 for any port', () => {
    const result = rejectBroadCidr('0.0.0.0/0', 8080);
    assert.equal(result.allowed, false);
  });

  it('rejects 0.0.0.0 with non-zero mask', () => {
    const result = rejectBroadCidr('0.0.0.0/8', 5432);
    assert.equal(result.allowed, false);
  });

  it('rejects CIDRs broader than /32 by default', () => {
    const result = rejectBroadCidr('10.0.0.0/24', 5432);
    assert.equal(result.allowed, false);
    assert.ok(result.reason.includes('broader than /32'));
  });

  it('allows /32 CIDRs', () => {
    const result = rejectBroadCidr('124.70.109.210/32', 5432);
    assert.equal(result.allowed, true);
  });

  it('allows broader CIDRs when explicitly approved', () => {
    const result = rejectBroadCidr('10.0.0.0/24', 5432, { allowBroaderThan32: true });
    assert.equal(result.allowed, true);
  });

  it('rejects invalid CIDR format', () => {
    const result = rejectBroadCidr('not-a-cidr', 5432);
    assert.equal(result.allowed, false);
  });

  it('rejects missing CIDR', () => {
    const result = rejectBroadCidr(null, 5432);
    assert.equal(result.allowed, false);
  });
});

describe('safetyGuards - validateStartConditions', () => {
  it('blocks start without explicit_approval', () => {
    const result = validateStartConditions({
      explicit_approval: false,
      region: 'cn-north-4',
      connection_test_passed: true,
      precheck_passed: true,
    });
    assert.equal(result.allowed, false);
    assert.ok(result.blockers.some(b => b.includes('explicit_approval')));
  });

  it('blocks start if region is not cn-north-4', () => {
    const result = validateStartConditions({
      explicit_approval: true,
      region: 'la-south-2',
      connection_test_passed: true,
      precheck_passed: true,
    });
    assert.equal(result.allowed, false);
    assert.ok(result.blockers.some(b => b.includes('cn-north-4')));
  });

  it('blocks start if connection test not passed', () => {
    const result = validateStartConditions({
      explicit_approval: true,
      region: 'cn-north-4',
      connection_test_passed: false,
      precheck_passed: true,
    });
    assert.equal(result.allowed, false);
    assert.ok(result.blockers.some(b => b.includes('Connection test')));
  });

  it('blocks start if precheck not passed', () => {
    const result = validateStartConditions({
      explicit_approval: true,
      region: 'cn-north-4',
      connection_test_passed: true,
      precheck_passed: false,
    });
    assert.equal(result.allowed, false);
    assert.ok(result.blockers.some(b => b.includes('Pre-check')));
  });

  it('allows start when all conditions met', () => {
    const result = validateStartConditions({
      explicit_approval: true,
      region: 'cn-north-4',
      source_endpoint: '110.238.67.209:5432',
      source_database: 'demodb',
      target_rds_id: '82a6795906de4c6db33e1c0e96594840in03',
      target_database: 'demodb',
      sync_mode: 'Full + Incremental',
      network_type: 'Public Network',
      connection_test_passed: true,
      precheck_passed: true,
    });
    assert.equal(result.allowed, true);
    assert.equal(result.blockers.length, 0);
  });

  it('blocks start if 5432 open to world', () => {
    const result = validateStartConditions({
      explicit_approval: true,
      region: 'cn-north-4',
      connection_test_passed: true,
      precheck_passed: true,
      has_open_5432_to_world: true,
    });
    assert.equal(result.allowed, false);
    assert.ok(result.blockers.some(b => b.includes('0.0.0.0/0')));
  });

  it('blocks start if sync mode is wrong', () => {
    const result = validateStartConditions({
      explicit_approval: true,
      region: 'cn-north-4',
      sync_mode: 'Full only',
      connection_test_passed: true,
      precheck_passed: true,
    });
    assert.equal(result.allowed, false);
    assert.ok(result.blockers.some(b => b.includes('Full + Incremental')));
  });
});

describe('safetyGuards - validateCreateConditions', () => {
  it('blocks creation without explicit_approval', () => {
    const result = validateCreateConditions({
      explicit_approval: false,
    });
    assert.equal(result.allowed, false);
  });

  it('blocks duplicate creation without duplicate_task_approval', () => {
    const result = validateCreateConditions({
      explicit_approval: true,
      matching_task_exists: true,
      duplicate_task_approval: false,
    });
    assert.equal(result.allowed, false);
    assert.ok(result.blockers.some(b => b.includes('duplicate')));
  });

  it('allows creation with all approvals', () => {
    const result = validateCreateConditions({
      explicit_approval: true,
      matching_task_exists: true,
      duplicate_task_approval: true,
    });
    assert.equal(result.allowed, true);
  });

  it('allows creation when no matching task exists', () => {
    const result = validateCreateConditions({
      explicit_approval: true,
      matching_task_exists: false,
    });
    assert.equal(result.allowed, true);
  });
});
