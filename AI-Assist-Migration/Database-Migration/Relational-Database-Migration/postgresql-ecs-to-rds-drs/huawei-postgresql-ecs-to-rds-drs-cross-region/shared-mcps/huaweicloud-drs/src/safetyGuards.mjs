const SECRET_PATTERNS = [
  /password\s*[:=]\s*\S+/gi,
  /passwd\s*[:=]\s*\S+/gi,
  /token\s*[:=]\s*\S+/gi,
  /access[_-]?key\s*[:=]\s*\S+/gi,
  /secret[_-]?key\s*[:=]\s*\S+/gi,
  /ak\s*[:=]\s*\S+/gi,
  /sk\s*[:=]\s*\S+/gi,
  /private[_-]?key[\s\S]{0,200}-----BEGIN/gi,
  /session[_-]?cookie\s*[:=]\s*\S+/gi,
  /-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----/g,
];

const REDACTED = '[REDACTED]';

export function redactSecrets(text) {
  if (!text || typeof text !== 'string') return text;
  let result = text;
  for (const pattern of SECRET_PATTERNS) {
    result = result.replace(pattern, (match) => {
      const eqIndex = match.indexOf('=') !== -1 ? match.indexOf('=') : match.indexOf(':');
      if (eqIndex !== -1) {
        return match.substring(0, eqIndex + 1) + ' ' + REDACTED;
      }
      return REDACTED;
    });
  }
  return result;
}

export function rejectBroadCidr(cidr, port = 5432, options = {}) {
  const { allowBroaderThan32 = false } = options;

  if (!cidr || typeof cidr !== 'string') {
    return { allowed: false, reason: 'CIDR is required' };
  }

  const parts = cidr.split('/');
  if (parts.length !== 2) {
    return { allowed: false, reason: 'Invalid CIDR format' };
  }

  const [ip, maskStr] = parts;
  const mask = parseInt(maskStr, 10);

  if (isNaN(mask) || mask < 0 || mask > 32) {
    return { allowed: false, reason: 'Invalid CIDR mask' };
  }

  if (ip === '0.0.0.0' && mask === 0) {
    return { allowed: false, reason: `Reject 0.0.0.0/0 for port ${port}` };
  }

  if (ip === '0.0.0.0') {
    return { allowed: false, reason: `Reject 0.0.0.0 source for port ${port}` };
  }

  if (mask < 32 && !allowBroaderThan32) {
    return { allowed: false, reason: `Reject CIDR broader than /32 for port ${port} (got /${mask}). Set allowBroaderThan32=true to override.` };
  }

  return { allowed: true, reason: 'CIDR is acceptable' };
}

export function validateStartConditions({
  explicit_approval,
  region,
  source_endpoint,
  source_database,
  target_rds_id,
  target_database,
  sync_mode,
  network_type,
  connection_test_passed,
  precheck_passed,
  precheck_warnings_approved = [],
  has_open_5432_to_world = false,
}) {
  const blockers = [];

  if (!explicit_approval) {
    blockers.push('explicit_approval is required to start a DRS task');
  }

  if (region !== 'cn-north-4') {
    blockers.push(`Region must be cn-north-4, got ${region}`);
  }

  if (source_endpoint && source_endpoint !== '198.51.100.1:5432') {
    blockers.push(`Source endpoint must be 198.51.100.1:5432, got ${source_endpoint}`);
  }

  if (source_database && source_database !== 'demodb') {
    blockers.push(`Source database must be demodb, got ${source_database}`);
  }

  if (target_rds_id && target_rds_id !== 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa01in03') {
    blockers.push(`Target RDS ID must be aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa01in03, got ${target_rds_id}`);
  }

  if (target_database && target_database !== 'demodb') {
    blockers.push(`Target database must be demodb, got ${target_database}`);
  }

  if (sync_mode && sync_mode !== 'Full + Incremental') {
    blockers.push(`Sync mode must be Full + Incremental, got ${sync_mode}`);
  }

  if (network_type && network_type !== 'Public Network') {
    blockers.push(`Network type must be Public Network, got ${network_type}`);
  }

  if (connection_test_passed !== true) {
    blockers.push('Connection test must pass before starting');
  }

  if (precheck_passed !== true) {
    const unapproved = (precheck_warnings_approved || []).length === 0;
    if (unapproved) {
      blockers.push('Pre-check must pass or warnings must be explicitly approved before starting');
    }
  }

  if (has_open_5432_to_world) {
    blockers.push('Port 5432 is open to 0.0.0.0/0 - this is not allowed');
  }

  return {
    allowed: blockers.length === 0,
    blockers,
  };
}

export function validateCreateConditions({
  explicit_approval,
  duplicate_task_approval = false,
  matching_task_exists = false,
}) {
  const blockers = [];

  if (!explicit_approval) {
    blockers.push('explicit_approval=true is required to create a DRS task');
  }

  if (matching_task_exists && !duplicate_task_approval) {
    blockers.push('A matching task already exists. Set duplicate_task_approval=true to create a duplicate');
  }

  return {
    allowed: blockers.length === 0,
    blockers,
  };
}

export function validateCidrPlan(rules) {
  const results = [];
  for (const rule of rules) {
    const check = rejectBroadCidr(rule.cidr, rule.port || 5432, { allowBroaderThan32: rule.allowBroaderThan32 });
    results.push({
      cidr: rule.cidr,
      port: rule.port || 5432,
      allowed: check.allowed,
      reason: check.reason,
    });
  }
  return results;
}
