function fieldCheck(taskVal, scenarioVal, caseInsensitive = false) {
  if (!scenarioVal) return { status: 'skip' };
  if (!taskVal) return { status: 'unknown' };
  const match = caseInsensitive
    ? taskVal.toLowerCase() === scenarioVal.toLowerCase()
    : taskVal === scenarioVal;
  return { status: match ? 'match' : 'fail' };
}

export function classifyTaskMatch(task, scenario) {
  if (!task || !scenario) {
    return { classification: 'NOT_MATCHING', reasons: ['Missing task or scenario'] };
  }

  const checks = {
    targetRegion: fieldCheck(task.target_region, scenario.target_region),
    sourceEndpoint: fieldCheck(task.source_endpoint, scenario.source_endpoint),
    sourcePort: fieldCheck(task.source_port, scenario.source_port),
    sourceDatabase: fieldCheck(task.source_database, scenario.source_database),
    targetRdsId: fieldCheck(task.target_rds_id, scenario.target_rds_id),
    targetDatabase: fieldCheck(task.target_database, scenario.target_database),
    sourceEngine: fieldCheck(task.source_engine, scenario.source_engine, true),
    targetEngine: fieldCheck(task.target_engine, scenario.target_engine, true),
    syncMode: fieldCheck(task.sync_mode, scenario.sync_mode),
    networkType: fieldCheck(task.network_type, scenario.network_type),
  };

  const hasUnknown = Object.values(checks).some(c => c.status === 'unknown');
  const hasFail = Object.values(checks).some(c => c.status === 'fail');
  const allMatchOrSkip = Object.values(checks).every(c => c.status === 'match' || c.status === 'skip');

  const failedChecks = Object.entries(checks).filter(([, v]) => v.status === 'fail').map(([k]) => k);
  const passedChecks = Object.entries(checks).filter(([, v]) => v.status === 'match').map(([k]) => k);
  const unknownChecks = Object.entries(checks).filter(([, v]) => v.status === 'unknown').map(([k]) => k);

  if (!hasFail && allMatchOrSkip && !hasUnknown) {
    return {
      classification: 'EXACT_MATCH',
      passedChecks,
      failedChecks: [],
      reasons: ['All visible fields match the scenario exactly'],
    };
  }

  if (!hasFail && allMatchOrSkip && hasUnknown) {
    return {
      classification: 'PARTIAL_MATCH',
      passedChecks,
      failedChecks: [],
      unknownChecks,
      reasons: ['All visible fields match but some task fields are missing/empty'],
    };
  }

  const nameMatch = task.task_name && scenario.task_name &&
    task.task_name.toLowerCase().includes(scenario.task_name.toLowerCase());

  if (nameMatch && hasFail) {
    return {
      classification: 'NAME_ONLY_MATCH',
      passedChecks,
      failedChecks,
      reasons: ['Task name matches but other fields differ'],
    };
  }

  if (nameMatch) {
    return {
      classification: 'PARTIAL_MATCH',
      passedChecks,
      failedChecks,
      reasons: ['Task name matches, some fields match or are not visible'],
    };
  }

  return {
    classification: 'NOT_MATCHING',
    passedChecks,
    failedChecks,
    reasons: ['Task does not match the scenario'],
  };
}

export function findMatchingTasks(tasks, scenario) {
  const results = [];

  for (const task of tasks) {
    const match = classifyTaskMatch(task, scenario);
    results.push({
      task_name: task.task_name,
      task_id: task.task_id,
      classification: match.classification,
      passedChecks: match.passedChecks,
      failedChecks: match.failedChecks,
      reasons: match.reasons,
    });
  }

  const exactMatches = results.filter(r => r.classification === 'EXACT_MATCH');
  const partialMatches = results.filter(r => r.classification === 'PARTIAL_MATCH');
  const nameOnlyMatches = results.filter(r => r.classification === 'NAME_ONLY_MATCH');

  let recommendation;
  if (exactMatches.length > 0) {
    recommendation = 'reuse_candidate';
  } else if (partialMatches.length > 0) {
    recommendation = 'ask_user';
  } else if (nameOnlyMatches.length > 0) {
    recommendation = 'ask_user';
  } else {
    recommendation = 'create_new';
  }

  return {
    candidates: results,
    exactMatches,
    partialMatches,
    nameOnlyMatches,
    recommendation,
  };
}

export function resolveCreationStrategy(strategy, matchingResult, explicit_approval, duplicate_task_approval) {
  const { exactMatches, partialMatches, nameOnlyMatches } = matchingResult;
  const hasAnyMatch = exactMatches.length > 0 || partialMatches.length > 0 || nameOnlyMatches.length > 0;

  switch (strategy) {
    case 'reuse_existing': {
      if (exactMatches.length > 0) {
        return { action: 'reuse', task: exactMatches[0], reason: 'Exact match found' };
      }
      if (partialMatches.length > 0) {
        return { action: 'reuse', task: partialMatches[0], reason: 'Partial match found, selecting for reuse' };
      }
      return {
        action: 'BLOCKED',
        reason: 'No matching task found. Creation requires explicit_approval=true and strategy change.',
      };
    }

    case 'create_new': {
      if (!explicit_approval) {
        return { action: 'BLOCKED', reason: 'explicit_approval=true required to create a new task' };
      }
      if (hasAnyMatch && !duplicate_task_approval) {
        return {
          action: 'WARNING',
          reason: 'Matching task(s) exist. Set duplicate_task_approval=true to proceed with creation.',
          matchingTasks: [...exactMatches, ...partialMatches, ...nameOnlyMatches],
        };
      }
      return { action: 'create', reason: 'Creating new task' };
    }

    case 'ask_if_matching_exists': {
      if (hasAnyMatch) {
        return {
          action: 'ask_user',
          reason: 'Matching task(s) found. User must decide: reuse or create new.',
          candidates: [...exactMatches, ...partialMatches, ...nameOnlyMatches],
        };
      }
      if (explicit_approval) {
        return { action: 'create', reason: 'No matching task found, creating new with approval' };
      }
      return { action: 'READY_TO_CREATE_PENDING_APPROVAL', reason: 'No matching task found. Set explicit_approval=true to create.' };
    }

    case 'create_new_even_if_matching_exists': {
      if (!explicit_approval) {
        return { action: 'BLOCKED', reason: 'explicit_approval=true required' };
      }
      if (hasAnyMatch && !duplicate_task_approval) {
        return {
          action: 'BLOCKED',
          reason: 'Matching task exists and duplicate_task_approval=true is required for this strategy.',
          matchingTasks: [...exactMatches, ...partialMatches, ...nameOnlyMatches],
        };
      }
      return {
        action: 'create',
        reason: 'Creating new task even though matching task exists (approved)',
        warning: hasAnyMatch ? 'A matching task already exists' : undefined,
      };
    }

    default:
      return { action: 'BLOCKED', reason: `Unknown strategy: ${strategy}` };
  }
}
