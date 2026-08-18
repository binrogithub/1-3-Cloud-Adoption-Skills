const crypto = require("crypto");
const https = require("https");
const { buildSignedHeaders } = require("../../huawei-signer");
const { scrubSecrets } = require("../../core/secret-scrubber");

function hashSql(sql) {
  return crypto.createHash("sha256").update(sql).digest("hex").slice(0, 16);
}

function truncateSqlPreview(sql, maxLength = 120) {
  if (!sql || typeof sql !== "string") return "";
  const singleLine = sql.replace(/\n/g, " ").replace(/\s+/g, " ").trim();
  if (singleLine.length <= maxLength) return singleLine;
  return singleLine.slice(0, maxLength) + "...";
}

function buildDliSqlJobRequest(options = {}) {
  const { sql, queueName, region, projectId, database } = options;
  const resolvedRegion = region || null;
  const resolvedProjectId = projectId || null;
  const resolvedQueue = queueName || "default";

  const endpoint = resolvedRegion ? `https://dli.${resolvedRegion}.myhuaweicloud.com` : null;
  const path = resolvedProjectId ? `/v1.0/${resolvedProjectId}/jobs/submit-job` : null;
  const url = endpoint && path ? `${endpoint}${path}` : null;

  const body = {
    sql: sql || "",
    queue_name: resolvedQueue,
  };
  if (database) {
    body.currentdb = database;
  }

  return {
    service: "DLI",
    operation: "submitSqlJob",
    method: "POST",
    endpoint,
    path,
    url,
    region: resolvedRegion,
    project_id: resolvedProjectId,
    queue_name: resolvedQueue,
    sql_hash: hashSql(sql || ""),
    sql_preview: truncateSqlPreview(sql),
    body_keys: Object.keys(body),
    execution_mode: "PLAN_ONLY",
  };
}

function buildDliJobStatusRequest(options = {}) {
  const { jobId, region, projectId } = options;
  const resolvedRegion = region || null;
  const resolvedProjectId = projectId || null;

  const endpoint = resolvedRegion ? `https://dli.${resolvedRegion}.myhuaweicloud.com` : null;
  const path = resolvedProjectId && jobId
    ? `/v1.0/${resolvedProjectId}/jobs?job_id=${encodeURIComponent(jobId)}&limit=1`
    : null;
  const url = endpoint && path ? `${endpoint}${path}` : null;

  return {
    service: "DLI",
    operation: "getSqlJobStatus",
    method: "GET",
    endpoint,
    path,
    url,
    region: resolvedRegion,
    project_id: resolvedProjectId,
    job_id: jobId || null,
    execution_mode: "PLAN_ONLY",
  };
}

function buildDliJobResultRequest(options = {}) {
  const { jobId, region, projectId } = options;
  const resolvedRegion = region || null;
  const resolvedProjectId = projectId || null;

  const endpoint = resolvedRegion ? `https://dli.${resolvedRegion}.myhuaweicloud.com` : null;
  const path = resolvedProjectId && jobId
    ? `/v1.0/${resolvedProjectId}/jobs/${encodeURIComponent(jobId)}`
    : null;
  const url = endpoint && path ? `${endpoint}${path}` : null;

  return {
    service: "DLI",
    operation: "getSqlJobResult",
    method: "GET",
    endpoint,
    path,
    url,
    region: resolvedRegion,
    project_id: resolvedProjectId,
    job_id: jobId || null,
    execution_mode: "PLAN_ONLY",
  };
}

function assertDliTransportSafety(options = {}) {
  const errors = [];

  if (options.allowRealExecution !== true) {
    errors.push("DLI transport requires allowRealExecution=true for real execution");
  }

  if (options.confirmNativeDli !== true) {
    errors.push("DLI transport requires --confirm-native-dli");
  }

  if (options.understandExecutesSql !== true) {
    errors.push("DLI transport requires --i-understand-this-executes-sql");
  }

  return {
    safe: errors.length === 0,
    errors,
  };
}

function httpsPost(url, ak, sk, bodyStr, timeoutMs = 180000) {
  return new Promise((resolve, reject) => {
    const headers = { "Content-Type": "application/json" };
    const signed = buildSignedHeaders({ method: "POST", url, headers, body: bodyStr, ak, sk });
    const parsed = new URL(url);
    const options = {
      hostname: parsed.hostname,
      port: 443,
      path: parsed.pathname + parsed.search,
      method: "POST",
      headers: signed,
    };

    const timer = setTimeout(() => {
      req.destroy(new Error("REQUEST_TIMEOUT"));
    }, timeoutMs);

    const req = https.request(options, (res) => {
      clearTimeout(timer);
      let body = "";
      res.on("data", (chunk) => (body += chunk));
      res.on("end", () => {
        resolve({ statusCode: res.statusCode, headers: res.headers, body });
      });
    });

    req.on("error", (err) => {
      clearTimeout(timer);
      reject(err);
    });

    req.write(bodyStr);
    req.end();
  });
}

function httpsGet(url, ak, sk, timeoutMs = 30000) {
  return new Promise((resolve, reject) => {
    const headers = { "Content-Type": "application/json" };
    const signed = buildSignedHeaders({ method: "GET", url, headers, body: "", ak, sk });
    const parsed = new URL(url);
    const options = {
      hostname: parsed.hostname,
      port: 443,
      path: parsed.pathname + parsed.search,
      method: "GET",
      headers: signed,
    };

    const timer = setTimeout(() => {
      req.destroy(new Error("REQUEST_TIMEOUT"));
    }, timeoutMs);

    const req = https.request(options, (res) => {
      clearTimeout(timer);
      let body = "";
      res.on("data", (chunk) => (body += chunk));
      res.on("end", () => {
        resolve({ statusCode: res.statusCode, headers: res.headers, body });
      });
    });

    req.on("error", (err) => {
      clearTimeout(timer);
      reject(err);
    });

    req.end();
  });
}

function extractJobIdFromResponse(resBody) {
  try {
    const parsed = JSON.parse(resBody);
    if (parsed.job_id) return String(parsed.job_id);
    if (parsed.jobId) return String(parsed.jobId);
    const msgText = parsed.message || parsed.error_msg || "";
    const match1 = msgText.match(/job_id[=:]\s*([a-f0-9\-]+)/i);
    if (match1) return match1[1];
    const match2 = msgText.match(/with id[:\s]+([a-f0-9\-]+)/i);
    if (match2) return match2[1];
    return null;
  } catch {
    return null;
  }
}

function parseJobStatus(resBody) {
  try {
    const parsed = JSON.parse(resBody);
    const jobs = parsed.jobs || [];
    if (jobs.length > 0) {
      return {
        status: (jobs[0].status || "UNKNOWN").toUpperCase(),
        job_id: jobs[0].job_id || jobs[0].jobId || null,
      };
    }
    if (parsed.status) {
      return { status: (parsed.status || "UNKNOWN").toUpperCase(), job_id: parsed.job_id || parsed.jobId || null };
    }
    return { status: "UNKNOWN", job_id: null };
  } catch {
    return { status: "UNKNOWN", job_id: null };
  }
}

function parseJobResult(resBody) {
  try {
    const parsed = JSON.parse(resBody);
    const rows = parsed.rows || [];
    const schema = parsed.schema || [];
    const columnNames = schema.map((s) => {
      if (typeof s === "object" && s !== null) {
        return s.column_name || s.columnName || s.name || Object.keys(s)[0] || "";
      }
      return String(s);
    });

    const namedRows = rows.map((row) => {
      const obj = {};
      if (Array.isArray(row)) {
        for (let i = 0; i < columnNames.length; i++) {
          obj[columnNames[i] || `col_${i}`] = row[i];
        }
      } else if (typeof row === "object") {
        Object.assign(obj, row);
      }
      return obj;
    });

    return { rows: namedRows, column_names: columnNames };
  } catch {
    return { rows: [], column_names: [] };
  }
}

const TERMINAL_STATUSES = new Set(["FINISHED", "FAILED", "CANCELLED", "TIMEOUT"]);

async function pollJobStatus(transport, jobId, maxAttempts = 60, intervalMs = 5000) {
  for (let i = 0; i < maxAttempts; i++) {
    const statusResult = await transport.getSqlJobStatus({ jobId });
    if (TERMINAL_STATUSES.has(statusResult.status)) {
      return statusResult;
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  return { job_id: jobId, status: "TIMEOUT", message: "Polling exceeded max attempts" };
}

function createDliHttpTransport(options = {}) {
  const allowRealExecution = options.allowRealExecution === true;
  const confirmNativeDli = options.confirmNativeDli === true;
  const understandExecutesSql = options.understandExecutesSql === true;
  const httpClient = options.httpClient || null;
  const config = options.config || {};

  const region = config.region || null;
  const projectId = config.projectId || null;
  const ak = config.ak || null;
  const sk = config.sk || null;
  const database = config.database || null;

  function isRealExecutionAllowed() {
    return allowRealExecution && confirmNativeDli && understandExecutesSql;
  }

  function getEffectiveHttpClient() {
    if (httpClient) return httpClient;
    if (ak && sk) return "REAL_HUAWEI_SIGNER";
    return null;
  }

  async function submitSqlJob({ sql, queueName, step, currentdb }) {
    const safetyCheck = assertDliTransportSafety({
      allowRealExecution,
      confirmNativeDli,
      understandExecutesSql,
    });

    const effectiveDatabase = currentdb || database;

    if (!safetyCheck.safe) {
      return {
        status: "TRANSPORT_GUARDRAIL_BLOCKED",
        real_execution: false,
        planned_request: buildDliSqlJobRequest({
          sql,
          queueName,
          region,
          projectId,
          database: effectiveDatabase,
        }),
        guard_errors: safetyCheck.errors,
      };
    }

    const client = getEffectiveHttpClient();
    if (!client) {
      return {
        status: "NATIVE_DLI_TRANSPORT_NOT_CONFIGURED",
        real_execution: false,
        message: "DLI HTTP transport has no httpClient and no AK/SK for real execution.",
        planned_request: buildDliSqlJobRequest({
          sql,
          queueName,
          region,
          projectId,
          database: effectiveDatabase,
        }),
      };
    }

    const plannedRequest = buildDliSqlJobRequest({
      sql,
      queueName,
      region,
      projectId,
      database: effectiveDatabase,
    });

    if (!plannedRequest.url) {
      return {
        status: "NATIVE_DLI_TRANSPORT_NOT_CONFIGURED",
        real_execution: false,
        message: "DLI HTTP transport missing region or projectId for URL construction.",
        planned_request: plannedRequest,
      };
    }

    if (typeof client === "object" && typeof client.submitSqlJob === "function") {
      return client.submitSqlJob({ sql, queueName, step, currentdb });
    }

    if (client === "REAL_HUAWEI_SIGNER") {
      const bodyObj = { sql, queue_name: queueName || "default" };
      if (effectiveDatabase) bodyObj.currentdb = effectiveDatabase;
      const bodyStr = JSON.stringify(bodyObj);

      try {
        const res = await httpsPost(plannedRequest.url, ak, sk, bodyStr);
        const jobId = extractJobIdFromResponse(res.body);

        if (res.statusCode === 200 && jobId) {
          return {
            status: "SUBMITTED",
            job_id: jobId,
            real_execution: true,
            http_status: res.statusCode,
          };
        }

        if (res.statusCode === 408) {
          const timeoutJobId = extractJobIdFromResponse(res.body) || jobId;
          if (timeoutJobId) {
            return {
              status: "SUBMITTED_TIMEOUT_ACCEPTED",
              job_id: timeoutJobId,
              real_execution: true,
              http_status: res.statusCode,
              message: "Job submitted but HTTP 408 timeout. Job may still be running.",
            };
          }
        }

        const bodySnippet = scrubSecrets(res.body || "").slice(0, 500);
        let dliErrorDetail = "";
        try {
          const parsed = JSON.parse(res.body || "{}");
          if (parsed.error_code || parsed.message) {
            dliErrorDetail = ` [${parsed.error_code || "unknown"}] ${scrubSecrets(parsed.message || "").slice(0, 200)}`;
          }
        } catch {}

        return {
          status: "SUBMISSION_FAILED",
          real_execution: true,
          http_status: res.statusCode,
          message: scrubSecrets(`DLI SQL job submission returned HTTP ${res.statusCode}${dliErrorDetail}`),
          response_body_snippet: bodySnippet,
        };
      } catch (err) {
        return {
          status: "SUBMISSION_ERROR",
          real_execution: true,
          message: scrubSecrets(err.message),
        };
      }
    }

    return {
      status: "NATIVE_DLI_TRANSPORT_NOT_IMPLEMENTED",
      real_execution: false,
      message: "DLI HTTP transport real execution path is not fully implemented for this httpClient type.",
      planned_request: plannedRequest,
    };
  }

  async function getSqlJobStatus({ jobId }) {
    const safetyCheck = assertDliTransportSafety({
      allowRealExecution,
      confirmNativeDli,
      understandExecutesSql,
    });

    if (!safetyCheck.safe) {
      return {
        status: "TRANSPORT_GUARDRAIL_BLOCKED",
        job_id: jobId,
        real_execution: false,
        planned_request: buildDliJobStatusRequest({ jobId, region, projectId }),
        guard_errors: safetyCheck.errors,
      };
    }

    const client = getEffectiveHttpClient();
    if (!client) {
      return {
        status: "NATIVE_DLI_TRANSPORT_NOT_CONFIGURED",
        job_id: jobId,
        real_execution: false,
        planned_request: buildDliJobStatusRequest({ jobId, region, projectId }),
      };
    }

    const plannedRequest = buildDliJobStatusRequest({ jobId, region, projectId });

    if (!plannedRequest.url) {
      return {
        status: "NATIVE_DLI_TRANSPORT_NOT_CONFIGURED",
        job_id: jobId,
        real_execution: false,
        planned_request: plannedRequest,
      };
    }

    if (typeof client === "object" && typeof client.getSqlJobStatus === "function") {
      return client.getSqlJobStatus({ jobId });
    }

    if (client === "REAL_HUAWEI_SIGNER") {
      try {
        const res = await httpsGet(plannedRequest.url, ak, sk);
        const parsed = parseJobStatus(res.body);
        return {
          status: parsed.status,
          job_id: parsed.job_id || jobId,
          real_execution: true,
          http_status: res.statusCode,
        };
      } catch (err) {
        return {
          status: "STATUS_CHECK_ERROR",
          job_id: jobId,
          real_execution: true,
          message: scrubSecrets(err.message),
        };
      }
    }

    return {
      status: "NATIVE_DLI_TRANSPORT_NOT_IMPLEMENTED",
      job_id: jobId,
      real_execution: false,
      planned_request: plannedRequest,
    };
  }

  async function getSqlJobResult({ jobId }) {
    const safetyCheck = assertDliTransportSafety({
      allowRealExecution,
      confirmNativeDli,
      understandExecutesSql,
    });

    if (!safetyCheck.safe) {
      return {
        status: "TRANSPORT_GUARDRAIL_BLOCKED",
        job_id: jobId,
        real_execution: false,
        rows: [],
        column_names: [],
        planned_request: buildDliJobResultRequest({ jobId, region, projectId }),
        guard_errors: safetyCheck.errors,
      };
    }

    const client = getEffectiveHttpClient();
    if (!client) {
      return {
        status: "NATIVE_DLI_TRANSPORT_NOT_CONFIGURED",
        job_id: jobId,
        real_execution: false,
        rows: [],
        column_names: [],
        planned_request: buildDliJobResultRequest({ jobId, region, projectId }),
      };
    }

    const plannedRequest = buildDliJobResultRequest({ jobId, region, projectId });

    if (!plannedRequest.url) {
      return {
        status: "NATIVE_DLI_TRANSPORT_NOT_CONFIGURED",
        job_id: jobId,
        real_execution: false,
        rows: [],
        column_names: [],
        planned_request: plannedRequest,
      };
    }

    if (typeof client === "object" && typeof client.getSqlJobResult === "function") {
      return client.getSqlJobResult({ jobId });
    }

    if (client === "REAL_HUAWEI_SIGNER") {
      try {
        const res = await httpsGet(plannedRequest.url, ak, sk);
        const parsed = parseJobResult(res.body);
        return {
          status: "FINISHED",
          job_id: jobId,
          real_execution: true,
          http_status: res.statusCode,
          rows: parsed.rows,
          column_names: parsed.column_names,
        };
      } catch (err) {
        return {
          status: "RESULT_FETCH_ERROR",
          job_id: jobId,
          real_execution: true,
          rows: [],
          column_names: [],
          message: scrubSecrets(err.message),
        };
      }
    }

    return {
      status: "NATIVE_DLI_TRANSPORT_NOT_IMPLEMENTED",
      job_id: jobId,
      real_execution: false,
      rows: [],
      column_names: [],
      planned_request: plannedRequest,
    };
  }

  return {
    submitSqlJob,
    getSqlJobStatus,
    getSqlJobResult,
    _isRealExecutionAllowed: isRealExecutionAllowed(),
    _effectiveHttpClient: getEffectiveHttpClient(),
  };
}

module.exports = {
  createDliHttpTransport,
  buildDliSqlJobRequest,
  buildDliJobStatusRequest,
  buildDliJobResultRequest,
  assertDliTransportSafety,
  pollJobStatus,
  parseJobStatus,
  parseJobResult,
  hashSql,
  truncateSqlPreview,
};
