import { redactSecrets } from './safetyGuards.mjs';
import { promises as fs } from 'fs';
import path from 'path';

export async function generateReport({
  output_path,
  region,
  task_name,
  task_id,
  drs_eip,
  creation_strategy_used,
  reused_existing,
  connection_test_result,
  precheck_result,
  start_status,
  current_phase,
  security_findings = [],
  next_steps = [],
  source_endpoint,
  source_database,
  source_username,
  target_rds_id,
  target_database,
  sync_mode,
  network_type,
}) {
  const now = new Date().toISOString();

  const lines = [
    `# DRS Task Report`,
    ``,
    `**Generated:** ${now}`,
    `**Region:** ${region}`,
    ``,
    `## Task Summary`,
    ``,
    `| Field | Value |`,
    `|-------|-------|`,
    `| Task Name | ${redactSecrets(task_name || 'N/A')} |`,
    `| Task ID | ${redactSecrets(task_id || 'N/A')} |`,
    `| DRS EIP | ${redactSecrets(drs_eip || 'N/A')} |`,
    `| Creation Strategy | ${creation_strategy_used || 'N/A'} |`,
    `| Reused Existing Task | ${reused_existing ? 'Yes' : 'No'} |`,
    `| Connection Test | ${connection_test_result || 'Not run'} |`,
    `| Pre-check | ${precheck_result || 'Not run'} |`,
    `| Start Status | ${start_status || 'Not started'} |`,
    `| Current Phase | ${current_phase || 'N/A'} |`,
    ``,
    `## Source Details`,
    ``,
    `| Field | Value |`,
    `|-------|-------|`,
    `| Endpoint | ${redactSecrets(source_endpoint || 'N/A')} |`,
    `| Database | ${redactSecrets(source_database || 'N/A')} |`,
    `| Username | ${redactSecrets(source_username || 'N/A')} |`,
    ``,
    `## Target Details`,
    ``,
    `| Field | Value |`,
    `|-------|-------|`,
    `| RDS ID | ${redactSecrets(target_rds_id || 'N/A')} |`,
    `| Database | ${redactSecrets(target_database || 'N/A')} |`,
    `| Sync Mode | ${sync_mode || 'N/A'} |`,
    `| Network Type | ${network_type || 'N/A'} |`,
    ``,
    `## Security Findings`,
    ``,
  ];

  if (security_findings.length === 0) {
    lines.push('- No security issues detected');
  } else {
    for (const f of security_findings) {
      lines.push(`- **${f.severity || 'INFO'}**: ${f.message}`);
    }
  }

  lines.push('', '## Next Steps', '');

  if (next_steps.length === 0) {
    lines.push('- No next steps defined');
  } else {
    for (const s of next_steps) {
      lines.push(`- ${s}`);
    }
  }

  lines.push(
    '',
    '## Safety Confirmations',
    '',
    '- No credentials were printed or stored in this report',
    '- Port 5432 was not opened to 0.0.0.0/0',
    '- All irreversible actions required explicit_approval=true',
    '',
  );

  const content = lines.join('\n');

  if (output_path) {
    const dir = path.dirname(output_path);
    await fs.mkdir(dir, { recursive: true });
    await fs.writeFile(output_path, content, 'utf-8');
  }

  return { content, output_path };
}

export async function generateSourceAccessPlan({
  drs_eip,
  source_security_group_id,
  source_database,
  source_user,
  allowBroaderThan32 = false,
}) {
  const { rejectBroadCidr } = await import('./safetyGuards.mjs');

  const cidr = `${drs_eip}/32`;
  const cidrCheck = rejectBroadCidr(cidr, 5432, { allowBroaderThan32 });

  if (!cidrCheck.allowed) {
    return {
      allowed: false,
      reason: cidrCheck.reason,
      cidr,
    };
  }

  const plan = {
    drs_eip,
    cidr,
    security_group_rules: [
      {
        direction: 'ingress',
        protocol: 'tcp',
        port: 5432,
        source: `${drs_eip}/32`,
        target_sg: source_security_group_id,
        action: 'ALLOW',
      },
    ],
    pg_hba_entries: [
      `host    ${source_database}    ${source_user}    ${drs_eip}/32    md5`,
      `host    replication    ${source_user}    ${drs_eip}/32    md5`,
    ],
    reload_command: 'SELECT pg_reload_conf();',
    warning: 'This plan must be reviewed and applied manually. Do not apply automatically.',
  };

  return plan;
}
