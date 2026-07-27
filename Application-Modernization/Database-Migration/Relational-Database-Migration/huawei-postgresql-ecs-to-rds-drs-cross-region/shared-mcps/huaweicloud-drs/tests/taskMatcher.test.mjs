import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { classifyTaskMatch, findMatchingTasks, resolveCreationStrategy } from '../src/taskMatcher.mjs';

const SCENARIO = {
  target_region: 'cn-north-4',
  source_endpoint: '110.238.67.209:5432',
  source_port: 5432,
  source_database: 'demodb',
  target_rds_id: '82a6795906de4c6db33e1c0e96594840in03',
  target_database: 'demodb',
  source_engine: 'PostgreSQL',
  target_engine: 'PostgreSQL',
  sync_mode: 'Full + Incremental',
  network_type: 'Public Network',
  task_name: 'pg-ecs-to-rds-cross-region',
};

describe('taskMatcher - classifyTaskMatch', () => {
  it('classifies exact match when all fields match', () => {
    const task = {
      target_region: 'cn-north-4',
      source_endpoint: '110.238.67.209:5432',
      source_port: 5432,
      source_database: 'demodb',
      target_rds_id: '82a6795906de4c6db33e1c0e96594840in03',
      target_database: 'demodb',
      source_engine: 'PostgreSQL',
      target_engine: 'PostgreSQL',
      sync_mode: 'Full + Incremental',
      network_type: 'Public Network',
      task_name: 'pg-ecs-to-rds-cross-region',
    };
    const result = classifyTaskMatch(task, SCENARIO);
    assert.equal(result.classification, 'EXACT_MATCH');
  });

  it('classifies partial match when some fields are missing', () => {
    const task = {
      target_region: 'cn-north-4',
      source_endpoint: '110.238.67.209:5432',
      source_database: 'demodb',
      target_database: 'demodb',
      source_engine: 'PostgreSQL',
      target_engine: 'PostgreSQL',
      task_name: 'pg-ecs-to-rds-cross-region',
    };
    const result = classifyTaskMatch(task, SCENARIO);
    assert.equal(result.classification, 'PARTIAL_MATCH');
  });

  it('classifies name only match when name matches but fields differ', () => {
    const task = {
      target_region: 'eu-west-1',
      source_endpoint: '192.168.1.1:5432',
      source_database: 'otherdb',
      target_database: 'otherdb',
      source_engine: 'MySQL',
      target_engine: 'MySQL',
      task_name: 'pg-ecs-to-rds-cross-region',
    };
    const result = classifyTaskMatch(task, SCENARIO);
    assert.equal(result.classification, 'NAME_ONLY_MATCH');
  });

  it('classifies not matching when nothing matches', () => {
    const task = {
      target_region: 'eu-west-1',
      source_endpoint: '192.168.1.1:3306',
      source_database: 'otherdb',
      target_database: 'otherdb',
      source_engine: 'MySQL',
      target_engine: 'MySQL',
      task_name: 'mysql-rds-sync',
    };
    const result = classifyTaskMatch(task, SCENARIO);
    assert.equal(result.classification, 'NOT_MATCHING');
  });

  it('handles missing task or scenario', () => {
    assert.equal(classifyTaskMatch(null, SCENARIO).classification, 'NOT_MATCHING');
    assert.equal(classifyTaskMatch({}, null).classification, 'NOT_MATCHING');
  });
});

describe('taskMatcher - findMatchingTasks', () => {
  it('returns reuse_candidate when exact match exists', () => {
    const tasks = [
      { task_name: 'pg-ecs-to-rds-cross-region', target_region: 'cn-north-4', source_endpoint: '110.238.67.209:5432', source_database: 'demodb', target_database: 'demodb', source_engine: 'PostgreSQL', target_engine: 'PostgreSQL', sync_mode: 'Full + Incremental', network_type: 'Public Network', source_port: 5432, target_rds_id: '82a6795906de4c6db33e1c0e96594840in03' },
    ];
    const result = findMatchingTasks(tasks, SCENARIO);
    assert.equal(result.recommendation, 'reuse_candidate');
    assert.equal(result.exactMatches.length, 1);
  });

  it('returns ask_user when partial match exists', () => {
    const tasks = [
      { task_name: 'pg-ecs-to-rds-cross-region', target_region: 'cn-north-4', source_engine: 'PostgreSQL', target_engine: 'PostgreSQL' },
    ];
    const result = findMatchingTasks(tasks, SCENARIO);
    assert.equal(result.recommendation, 'ask_user');
    assert.equal(result.partialMatches.length, 1);
  });

  it('returns create_new when no matches exist', () => {
    const tasks = [
      { task_name: 'mysql-sync', target_region: 'eu-west-1', source_engine: 'MySQL' },
    ];
    const result = findMatchingTasks(tasks, SCENARIO);
    assert.equal(result.recommendation, 'create_new');
  });

  it('handles empty task list', () => {
    const result = findMatchingTasks([], SCENARIO);
    assert.equal(result.recommendation, 'create_new');
    assert.equal(result.candidates.length, 0);
  });
});

describe('taskMatcher - resolveCreationStrategy', () => {
  it('reuse_existing selects exact match', () => {
    const matching = { exactMatches: [{ task_name: 't1' }], partialMatches: [], nameOnlyMatches: [] };
    const result = resolveCreationStrategy('reuse_existing', matching, false, false);
    assert.equal(result.action, 'reuse');
  });

  it('reuse_existing is BLOCKED when no match', () => {
    const matching = { exactMatches: [], partialMatches: [], nameOnlyMatches: [] };
    const result = resolveCreationStrategy('reuse_existing', matching, false, false);
    assert.equal(result.action, 'BLOCKED');
  });

  it('create_new is BLOCKED without explicit_approval', () => {
    const matching = { exactMatches: [], partialMatches: [], nameOnlyMatches: [] };
    const result = resolveCreationStrategy('create_new', matching, false, false);
    assert.equal(result.action, 'BLOCKED');
  });

  it('create_new WARNING when matching exists without duplicate approval', () => {
    const matching = { exactMatches: [{ task_name: 't1' }], partialMatches: [], nameOnlyMatches: [] };
    const result = resolveCreationStrategy('create_new', matching, true, false);
    assert.equal(result.action, 'WARNING');
  });

  it('create_new proceeds with approval and no matches', () => {
    const matching = { exactMatches: [], partialMatches: [], nameOnlyMatches: [] };
    const result = resolveCreationStrategy('create_new', matching, true, false);
    assert.equal(result.action, 'create');
  });

  it('ask_if_matching_exists returns ask_user when matches exist', () => {
    const matching = { exactMatches: [{ task_name: 't1' }], partialMatches: [], nameOnlyMatches: [] };
    const result = resolveCreationStrategy('ask_if_matching_exists', matching, true, false);
    assert.equal(result.action, 'ask_user');
  });

  it('ask_if_matching_exists creates when no matches and approved', () => {
    const matching = { exactMatches: [], partialMatches: [], nameOnlyMatches: [] };
    const result = resolveCreationStrategy('ask_if_matching_exists', matching, true, false);
    assert.equal(result.action, 'create');
  });

  it('ask_if_matching_exists returns PENDING when no matches and not approved', () => {
    const matching = { exactMatches: [], partialMatches: [], nameOnlyMatches: [] };
    const result = resolveCreationStrategy('ask_if_matching_exists', matching, false, false);
    assert.equal(result.action, 'READY_TO_CREATE_PENDING_APPROVAL');
  });

  it('create_new_even_if_matching_exists is BLOCKED without duplicate approval', () => {
    const matching = { exactMatches: [{ task_name: 't1' }], partialMatches: [], nameOnlyMatches: [] };
    const result = resolveCreationStrategy('create_new_even_if_matching_exists', matching, true, false);
    assert.equal(result.action, 'BLOCKED');
  });

  it('create_new_even_if_matching_exists proceeds with all approvals', () => {
    const matching = { exactMatches: [{ task_name: 't1' }], partialMatches: [], nameOnlyMatches: [] };
    const result = resolveCreationStrategy('create_new_even_if_matching_exists', matching, true, true);
    assert.equal(result.action, 'create');
    assert.ok(result.warning);
  });

  it('unknown strategy returns BLOCKED', () => {
    const matching = { exactMatches: [], partialMatches: [], nameOnlyMatches: [] };
    const result = resolveCreationStrategy('invalid', matching, true, false);
    assert.equal(result.action, 'BLOCKED');
  });
});
