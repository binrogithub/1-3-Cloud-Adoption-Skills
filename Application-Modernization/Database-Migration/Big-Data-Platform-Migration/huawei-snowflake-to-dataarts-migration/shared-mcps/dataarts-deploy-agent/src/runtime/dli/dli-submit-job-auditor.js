const { scrubSecrets } = require("../../core/secret-scrubber");

const CREATE_DATABASE_PATTERN = /^\s*CREATE\s+DATABASE\b/i;
const DROP_DATABASE_PATTERN = /^\s*DROP\s+DATABASE\b/i;

function classifyStatement(sql) {
  if (!sql || typeof sql !== "string") return "UNKNOWN";
  const trimmed = sql.trim();
  if (CREATE_DATABASE_PATTERN.test(trimmed)) return "CREATE_DATABASE";
  if (DROP_DATABASE_PATTERN.test(trimmed)) return "DROP_DATABASE";
  if (/^\s*CREATE\s+TABLE\b/i.test(trimmed)) return "CREATE_TABLE";
  if (/^\s*DROP\s+TABLE\b/i.test(trimmed)) return "DROP_TABLE";
  if (/^\s*INSERT\s+INTO\b/i.test(trimmed)) return "INSERT";
  if (/^\s*SELECT\b/i.test(trimmed)) return "SELECT";
  if (/^\s*MERGE\s+INTO\b/i.test(trimmed)) return "MERGE";
  if (/^\s*ALTER\s+/i.test(trimmed)) return "ALTER";
  if (/^\s*TRUNCATE\s+TABLE\b/i.test(trimmed)) return "TRUNCATE";
  return "OTHER";
}

function isCreateOrDropDatabaseStatement(sql) {
  const cls = classifyStatement(sql);
  return cls === "CREATE_DATABASE" || cls === "DROP_DATABASE";
}

function auditDliSubmitJobRequest(request, options = {}) {
  const findings = [];
  const warnings = [];
  const requestedQueue = options.queueName || "default";
  const projectId = options.projectId || null;

  if (!request || typeof request !== "object") {
    findings.push("Request is null or not an object");
    return {
      status: "DLI_SUBMIT_JOB_AUDIT_FAIL",
      valid: false,
      findings,
      warnings,
      safety: buildAuditSafety(),
    };
  }

  if (request.method !== "POST") {
    findings.push(`Invalid method: expected POST, got ${request.method}`);
  }

  if (projectId && request.path) {
    const expectedPathPattern = new RegExp(`^/v1\\.0/${projectId}/jobs/submit-job$`);
    if (!expectedPathPattern.test(request.path)) {
      findings.push(`Path does not match /v1.0/{project_id}/jobs/submit-job: ${request.path}`);
    }
  } else if (request.path) {
    const submitJobPattern = /^\/v1\.0\/[^/]+\/jobs\/submit-job$/;
    if (!submitJobPattern.test(request.path)) {
      findings.push(`Path does not match /v1.0/{project_id}/jobs/submit-job pattern: ${request.path}`);
    }
  } else {
    warnings.push("path is null — request was built without projectId; will fail at submission time");
  }

  const bodyKeys = request.body_keys || [];
  const sqlPreview = request.sql_preview || "";
  const sqlHash = request.sql_hash || "";

  if (!bodyKeys.includes("sql") && !sqlPreview && !sqlHash) {
    findings.push("body.sql is missing or empty");
  }

  if (!bodyKeys.includes("queue_name")) {
    findings.push("body.queue_name is missing");
  } else if (request.queue_name && request.queue_name !== requestedQueue) {
    warnings.push(`body.queue_name "${request.queue_name}" does not match requested queue "${requestedQueue}"`);
  }

  const stmtType = classifyStatement(sqlPreview);
  const isCreateDropDb = isCreateOrDropDatabaseStatement(sqlPreview);

  if (!isCreateDropDb && !bodyKeys.includes("currentdb")) {
    if (stmtType === "CREATE_TABLE" || stmtType === "INSERT" || stmtType === "SELECT" || stmtType === "MERGE") {
      warnings.push(`Statement type ${stmtType} without currentdb — DLI may fail if default database is not set`);
    }
  }

  if (isCreateDropDb && bodyKeys.includes("currentdb")) {
    warnings.push(`${stmtType} statement includes currentdb — DLI may reject currentdb for database-level DDL`);
  }

  if (request.project_id === null || request.project_id === undefined) {
    warnings.push("project_id is null — request cannot be submitted without project_id");
  }

  if (request.region === null || request.region === undefined) {
    warnings.push("region is null — request cannot be submitted without region");
  }

  if (request.url === null || request.url === undefined) {
    warnings.push("url is null — request URL cannot be constructed without region and project_id");
  }

  if (sqlPreview.length > 200) {
    warnings.push("sql_preview exceeds 200 characters — should be truncated for logging");
  }

  const jsonStr = JSON.stringify(request);
  const secretPatterns = [/\bAK[=:]/i, /\bSK[=:]/i, /password/i, /secret[_-]?key/i, /access[_-]?key/i];
  for (const pat of secretPatterns) {
    if (pat.test(jsonStr)) {
      findings.push("Request body may expose secrets — found pattern matching " + pat.source);
      break;
    }
  }

  const valid = findings.length === 0;
  let status;
  if (valid && warnings.length === 0) {
    status = "DLI_SUBMIT_JOB_AUDIT_PASS";
  } else if (valid) {
    status = "DLI_SUBMIT_JOB_AUDIT_WARN";
  } else {
    status = "DLI_SUBMIT_JOB_AUDIT_FAIL";
  }

  return {
    status,
    valid,
    findings,
    warnings,
    statement_type: stmtType,
    safety: buildAuditSafety(),
  };
}

function auditDliTransportPlan(options = {}) {
  const transportPlan = options.transportPlan || null;
  const queueName = options.queueName || "default";
  const projectId = options.projectId || null;

  if (!transportPlan || !transportPlan.valid) {
    return {
      status: "DLI_SUBMIT_JOB_AUDIT_FAIL",
      valid: false,
      findings: ["Transport plan is invalid or missing"],
      warnings: [],
      requests_audited: 0,
      safety: buildAuditSafety(),
    };
  }

  const transportRequests = transportPlan.transport_requests || [];
  const allFindings = [];
  const allWarnings = [];
  let passCount = 0;
  let warnCount = 0;
  let failCount = 0;
  const requestAudits = [];

  for (let i = 0; i < transportRequests.length; i++) {
    const tr = transportRequests[i];
    const req = tr.transport_request || {};
    const audit = auditDliSubmitJobRequest(req, { queueName, projectId });

    requestAudits.push({
      index: i + 1,
      phase: tr.phase,
      step_name: tr.step_name,
      step_type: tr.step_type,
      audit_status: audit.status,
      valid: audit.valid,
      findings: audit.findings,
      warnings: audit.warnings,
      statement_type: audit.statement_type,
    });

    for (const f of audit.findings) {
      allFindings.push(`[${tr.step_name}] ${f}`);
    }
    for (const w of audit.warnings) {
      allWarnings.push(`[${tr.step_name}] ${w}`);
    }

    if (audit.status === "DLI_SUBMIT_JOB_AUDIT_PASS") passCount++;
    else if (audit.status === "DLI_SUBMIT_JOB_AUDIT_WARN") warnCount++;
    else failCount++;
  }

  const valid = allFindings.length === 0;
  let status;
  if (valid && allWarnings.length === 0) {
    status = "DLI_SUBMIT_JOB_AUDIT_PASS";
  } else if (valid) {
    status = "DLI_SUBMIT_JOB_AUDIT_WARN";
  } else {
    status = "DLI_SUBMIT_JOB_AUDIT_FAIL";
  }

  return {
    status,
    valid,
    findings: allFindings,
    warnings: allWarnings,
    requests_audited: transportRequests.length,
    pass_count: passCount,
    warn_count: warnCount,
    fail_count: failCount,
    request_audits: requestAudits,
    safety: buildAuditSafety(),
  };
}

function buildAuditSafety() {
  return {
    local_audit_only: true,
    no_cloud_api_calls: true,
    no_sql_execution: true,
    no_runtime_execution: true,
    secrets_redacted: true,
  };
}

module.exports = {
  auditDliSubmitJobRequest,
  auditDliTransportPlan,
  classifyStatement,
  isCreateOrDropDatabaseStatement,
  buildAuditSafety,
};
