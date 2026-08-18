import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { redactSecrets, rejectBroadCidr, validateStartConditions, validateCreateConditions, validateCidrPlan } from '../src/safetyGuards.mjs';
import { classifyTaskMatch, findMatchingTasks, resolveCreationStrategy } from '../src/taskMatcher.mjs';

describe('dryRun - full scenario validation', () => {
  const SCENARIO = {
    target_region: 'cn-north-4',
    source_endpoint: '198.51.100.1:5432',
    source_port: 5432,
    source_database: 'demodb',
    target_rds_id: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa01in03',
    target_database: 'demodb',
    source_engine: 'PostgreSQL',
    target_engine: 'PostgreSQL',
    sync_mode: 'Full + Incremental',
    network_type: 'Public Network',
    task_name: 'pg-ecs-to-rds-cross-region',
  };

  it('known existing task matches scenario', () => {
    const existingTask = {
      task_name: 'pg-ecs-to-rds-cross-region',
      task_id: 'drs-task-001',
      target_region: 'cn-north-4',
      source_endpoint: '198.51.100.1:5432',
      source_port: 5432,
      source_database: 'demodb',
      target_rds_id: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa01in03',
      target_database: 'demodb',
      source_engine: 'PostgreSQL',
      target_engine: 'PostgreSQL',
      sync_mode: 'Full + Incremental',
      network_type: 'Public Network',
    };

    const result = classifyTaskMatch(existingTask, SCENARIO);
    assert.equal(result.classification, 'EXACT_MATCH');
  });

  it('known existing task in Configuration status is reusable', () => {
    const existingTask = {
      task_name: 'pg-ecs-to-rds-cross-region',
      target_region: 'cn-north-4',
      source_endpoint: '198.51.100.1:5432',
      source_database: 'demodb',
      target_database: 'demodb',
      source_engine: 'PostgreSQL',
      target_engine: 'PostgreSQL',
      sync_mode: 'Full + Incremental',
      network_type: 'Public Network',
      source_port: 5432,
      target_rds_id: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa01in03',
    };

    const matching = findMatchingTasks([existingTask], SCENARIO);
    assert.equal(matching.recommendation, 'reuse_candidate');

    const resolution = resolveCreationStrategy('ask_if_matching_exists', matching, false, false);
    assert.equal(resolution.action, 'ask_user');
  });

  it('dry-run: start is blocked without explicit_approval', () => {
    const result = validateStartConditions({
      explicit_approval: false,
      region: 'cn-north-4',
      connection_test_passed: true,
      precheck_passed: true,
    });
    assert.equal(result.allowed, false);
  });

  it('dry-run: creation is blocked without explicit_approval', () => {
    const result = validateCreateConditions({
      explicit_approval: false,
      matching_task_exists: false,
    });
    assert.equal(result.allowed, false);
  });

  it('dry-run: duplicate creation is blocked without duplicate_task_approval', () => {
    const result = validateCreateConditions({
      explicit_approval: true,
      matching_task_exists: true,
      duplicate_task_approval: false,
    });
    assert.equal(result.allowed, false);
  });

  it('source access plan rejects 0.0.0.0/0', () => {
    const result = rejectBroadCidr('0.0.0.0/0', 5432);
    assert.equal(result.allowed, false);
  });

  it('source access plan allows DRS EIP /32', () => {
    const result = rejectBroadCidr('198.51.100.2/32', 5432);
    assert.equal(result.allowed, true);
  });

  it('CIDR plan validation catches multiple violations', () => {
    const rules = [
      { cidr: '0.0.0.0/0', port: 5432 },
      { cidr: '10.0.0.0/24', port: 5432 },
      { cidr: '198.51.100.2/32', port: 5432 },
    ];
    const results = validateCidrPlan(rules);
    assert.equal(results[0].allowed, false);
    assert.equal(results[1].allowed, false);
    assert.equal(results[2].allowed, true);
  });

  it('no credentials leaked in redacted output', () => {
    const input = 'password=supersecret token=abc123 access_key=AKIA123';
    const redacted = redactSecrets(input);
    assert.ok(!redacted.includes('supersecret'));
    assert.ok(!redacted.includes('abc123'));
    assert.ok(!redacted.includes('AKIA123'));
  });

  it('task lifecycle: reuse_existing with exact match does not create', () => {
    const existingTask = {
      task_name: 'pg-ecs-to-rds-cross-region',
      target_region: 'cn-north-4',
      source_endpoint: '198.51.100.1:5432',
      source_database: 'demodb',
      target_database: 'demodb',
      source_engine: 'PostgreSQL',
      target_engine: 'PostgreSQL',
      sync_mode: 'Full + Incremental',
      network_type: 'Public Network',
      source_port: 5432,
      target_rds_id: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa01in03',
    };

    const matching = findMatchingTasks([existingTask], SCENARIO);
    const resolution = resolveCreationStrategy('reuse_existing', matching, false, false);
    assert.equal(resolution.action, 'reuse');
    assert.ok(!resolution.action.includes('create'));
  });

  it('task lifecycle: create_new without approval is blocked', () => {
    const matching = findMatchingTasks([], SCENARIO);
    const resolution = resolveCreationStrategy('create_new', matching, false, false);
    assert.equal(resolution.action, 'BLOCKED');
  });

  it('task lifecycle: start with wrong region is blocked', () => {
    const result = validateStartConditions({
      explicit_approval: true,
      region: 'la-south-2',
      connection_test_passed: true,
      precheck_passed: true,
    });
    assert.equal(result.allowed, false);
    assert.ok(result.blockers.some(b => b.includes('cn-north-4')));
  });
});
