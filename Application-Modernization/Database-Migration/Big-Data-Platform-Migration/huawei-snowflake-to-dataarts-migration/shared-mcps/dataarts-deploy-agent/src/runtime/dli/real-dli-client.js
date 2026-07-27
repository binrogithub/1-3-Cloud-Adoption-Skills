const crypto = require("crypto");
const https = require("https");
const { buildSafetyPolicy } = require("../../core/safety-policy");
const { buildSignedHeaders } = require("../../huawei-signer");
const { scrubSecrets } = require("../../core/secret-scrubber");
const { loadRuntimeConfig, maskRuntimeConfig, validateRuntimeConfig } = require("../../config/runtime-config-loader");
const { createDliHttpTransport } = require("./dli-http-transport");

function hashSql(sql) {
  return crypto.createHash("sha256").update(sql).digest("hex").slice(0, 16);
}

function truncateSqlPreview(sql, maxLength = 120) {
  if (!sql || typeof sql !== "string") return "";
  const singleLine = sql.replace(/\n/g, " ").replace(/\s+/g, " ").trim();
  if (singleLine.length <= maxLength) return singleLine;
  return singleLine.slice(0, maxLength) + "...";
}

function createRealDliSafetyPolicy() {
  return buildSafetyPolicy({
    real_dli_client_scaffold: true,
    plan_only: true,
    no_real_sql_execution: true,
    no_cloud_write_calls: true,
    no_runtime_execution: true,
    no_confirm: true,
    secrets_redacted: true,
  });
}

function createDliLivePreflightSafetyPolicy() {
  return buildSafetyPolicy({
    dli_live_preflight: true,
    read_only: true,
    no_sql_execution: true,
    no_runtime_execution: true,
    no_cloud_write_calls: true,
    no_confirm: true,
    no_mutation_methods_allowed: true,
    secrets_redacted: true,
  });
}

function buildDliListQueuesRequest(options = {}) {
  const { region, projectId } = options;
  const resolvedRegion = region || process.env.HUAWEI_REGION || null;
  const resolvedProjectId = projectId || process.env.HUAWEI_PROJECT_ID || null;

  return {
    service: "DLI",
    operation: "listQueues",
    method: "GET",
    endpoint: resolvedRegion ? `https://dli.${resolvedRegion}.myhuaweicloud.com` : null,
    path: resolvedProjectId ? `/v1.0/${resolvedProjectId}/queues` : null,
    region: resolvedRegion,
    project_id: resolvedProjectId,
    read_only: true,
    execution_mode: "READ_ONLY_LIVE",
  };
}

function buildDliQueueDescribeRequest(options = {}) {
  const { queueName, region, projectId } = options;
  const resolvedRegion = region || process.env.HUAWEI_REGION || null;
  const resolvedProjectId = projectId || process.env.HUAWEI_PROJECT_ID || null;
  const resolvedQueue = queueName || "default";

  return {
    service: "DLI",
    operation: "describeQueue",
    method: "GET",
    endpoint: resolvedRegion ? `https://dli.${resolvedRegion}.myhuaweicloud.com` : null,
    path: resolvedProjectId ? `/v1.0/${resolvedProjectId}/queues/${encodeURIComponent(resolvedQueue)}` : null,
    queue_name: resolvedQueue,
    region: resolvedRegion,
    project_id: resolvedProjectId,
    read_only: true,
    execution_mode: "READ_ONLY_LIVE",
  };
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

    const req = https.request(url, options, (res) => {
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

function buildDliSqlExecutionRequest(options = {}) {
  const { sql, queueName, step, region, projectId } = options;
  const sqlHash = hashSql(sql || "");

  return {
    service: "DLI",
    operation: "executeSql",
    queue_name: queueName || "default",
    sql_hash: sqlHash,
    sql_preview: truncateSqlPreview(sql),
    step_name: step && step.name ? step.name : null,
    step_type: step && step.type ? step.type : null,
    execution_mode: "PLAN_ONLY",
    region: region || null,
    project_id: projectId || null,
  };
}

function buildDliQueryRequest(options = {}) {
  const { sql, queueName, step, region, projectId } = options;
  const sqlHash = hashSql(sql || "");

  return {
    service: "DLI",
    operation: "querySql",
    queue_name: queueName || "default",
    sql_hash: sqlHash,
    sql_preview: truncateSqlPreview(sql),
    step_name: step && step.name ? step.name : null,
    step_type: step && step.type ? step.type : null,
    execution_mode: "PLAN_ONLY",
    region: region || null,
    project_id: projectId || null,
  };
}

function validateRealDliClientConfig(options = {}) {
  const configOverrides = options.config || {};

  const rtConfig = loadRuntimeConfig({
    configJsValues: configOverrides,
    envFilePath: options.envFilePath,
  });

  const validation = validateRuntimeConfig(rtConfig);

  const valid = validation.valid;

  return {
    valid,
    region: rtConfig.region,
    project_id: rtConfig.project_id ? "present" : null,
    dli_queue: rtConfig.dli_queue,
    has_ak: rtConfig.ak_present,
    has_sk: rtConfig.sk_present,
    source_map: rtConfig.source_map,
    env_file_status: rtConfig.env_file_status,
    masked_config: maskRuntimeConfig(rtConfig),
    errors: validation.errors,
    warnings: validation.warnings,
  };
}

function assertRealDliExecutionAllowed(options = {}) {
  const errors = [];

  if (options.allowRealExecution !== true) {
    errors.push("Native DLI real execution requires allowRealExecution=true");
  }

  if (options.confirmNativeDli !== true) {
    errors.push("Native DLI real execution requires --confirm-native-dli");
  }

  if (options.understandExecutesSql !== true) {
    errors.push("Native DLI real execution requires --i-understand-this-executes-sql");
  }

  return {
    allowed: errors.length === 0,
    errors,
  };
}

function createRealDliClient(options = {}) {
  const allowRealExecution = options.allowRealExecution === true;
  const confirmNativeDli = options.confirmNativeDli === true;
  const understandExecutesSql = options.understandExecutesSql === true;
  const liveReadOnly = options.liveReadOnly === true;
  const configOverrides = options.config || {};

  const rtConfig = loadRuntimeConfig({
    configJsValues: configOverrides,
    envFilePath: options.envFilePath,
  });

  const region = options.region || rtConfig.region || null;
  const projectId = options.projectId || rtConfig.project_id || null;
  const ak = rtConfig.ak || null;
  const sk = rtConfig.sk || null;
  const resolvedRegion = region;
  const resolvedProjectId = projectId;
  let planCounter = 0;

  const transport = createDliHttpTransport({
    allowRealExecution,
    confirmNativeDli,
    understandExecutesSql,
    httpClient: options.httpClient || null,
    config: {
      region: resolvedRegion,
      projectId: resolvedProjectId,
      ak,
      sk,
      database: options.database || null,
    },
  });

  function nextPlanId() {
    planCounter++;
    return `plan_${planCounter}_${Date.now()}`;
  }

  function isRealExecutionAllowed() {
    return allowRealExecution && confirmNativeDli && understandExecutesSql;
  }

  async function executeSql({ sql, queueName, step, currentdb }) {
    if (allowRealExecution && !isRealExecutionAllowed()) {
      const guardCheck = assertRealDliExecutionAllowed({
        allowRealExecution,
        confirmNativeDli,
        understandExecutesSql,
      });
      const firstError = guardCheck.errors[0] || "Native DLI real execution guardrail blocked execution";
      throw new Error(firstError);
    }

    if (isRealExecutionAllowed()) {
      const transportResult = await transport.submitSqlJob({ sql, queueName, step, currentdb });

      if (transportResult.status === "NATIVE_DLI_TRANSPORT_NOT_CONFIGURED" ||
          transportResult.status === "NATIVE_DLI_TRANSPORT_NOT_IMPLEMENTED") {
        return {
          status: transportResult.status,
          valid: false,
          real_execution: false,
          message: transportResult.message || "DLI transport cannot execute. No SQL was executed.",
        };
      }

      if (transportResult.status === "SUBMITTED" || transportResult.status === "SUBMITTED_TIMEOUT_ACCEPTED") {
        const jobId = transportResult.job_id;
        let finalStatus = transportResult.status;

        if (jobId) {
          try {
            const pollResult = await pollTransportJob(transport, jobId, 60, 5000);
            finalStatus = pollResult.status;
          } catch {
            finalStatus = transportResult.status === "SUBMITTED_TIMEOUT_ACCEPTED"
              ? "SUBMITTED_TIMEOUT_ACCEPTED"
              : "SUBMITTED";
          }
        }

        return {
          job_id: jobId,
          status: finalStatus === "FINISHED" ? "FINISHED" : finalStatus,
          valid: true,
          real_execution: true,
          statement_type: "EXECUTE_SQL",
          sql_hash: hashSql(sql || ""),
          sql_preview: truncateSqlPreview(sql),
          queue_name: queueName || "default",
          step_name: step && step.name ? step.name : null,
          step_type: step && step.type ? step.type : null,
        };
      }

      if (transportResult.status === "SUBMISSION_FAILED" || transportResult.status === "SUBMISSION_ERROR") {
        return {
          status: transportResult.status,
          valid: false,
          real_execution: true,
          http_status: transportResult.http_status || null,
          message: scrubSecrets(transportResult.message || "DLI SQL job submission failed."),
          response_body_snippet: transportResult.response_body_snippet || null,
        };
      }

      return {
        status: transportResult.status,
        valid: false,
        real_execution: false,
        message: transportResult.message || "Unexpected transport status.",
      };
    }

    const planId = nextPlanId();
    const sqlHash = hashSql(sql || "");

    return {
      job_id: planId,
      status: "PLANNED_NOT_EXECUTED",
      statement_type: "EXECUTE_SQL",
      sql_hash: sqlHash,
      sql_preview: truncateSqlPreview(sql),
      real_execution: false,
      queue_name: queueName || "default",
      step_name: step && step.name ? step.name : null,
      step_type: step && step.type ? step.type : null,
      planned_request: buildDliSqlExecutionRequest({
        sql,
        queueName,
        step,
        region: resolvedRegion,
        projectId: resolvedProjectId,
      }),
    };
  }

  async function querySql({ sql, queueName, step, currentdb }) {
    if (allowRealExecution && !isRealExecutionAllowed()) {
      const guardCheck = assertRealDliExecutionAllowed({
        allowRealExecution,
        confirmNativeDli,
        understandExecutesSql,
      });
      const firstError = guardCheck.errors[0] || "Native DLI real execution guardrail blocked execution";
      throw new Error(firstError);
    }

    if (isRealExecutionAllowed()) {
      const transportResult = await transport.submitSqlJob({ sql, queueName, step, currentdb });

      if (transportResult.status === "NATIVE_DLI_TRANSPORT_NOT_CONFIGURED" ||
          transportResult.status === "NATIVE_DLI_TRANSPORT_NOT_IMPLEMENTED") {
        return {
          status: transportResult.status,
          valid: false,
          real_execution: false,
          message: transportResult.message || "DLI transport cannot execute. No SQL was executed.",
        };
      }

      if (transportResult.status === "SUBMITTED" || transportResult.status === "SUBMITTED_TIMEOUT_ACCEPTED") {
        const jobId = transportResult.job_id;
        let rows = [];
        let columnNames = [];

        if (jobId) {
          try {
            const pollResult = await pollTransportJob(transport, jobId);
            if (pollResult.status === "FINISHED") {
              const resultResp = await transport.getSqlJobResult({ jobId });
              rows = resultResp.rows || [];
              columnNames = resultResp.column_names || [];
            }
          } catch {
            rows = [];
            columnNames = [];
          }
        }

        return {
          job_id: jobId,
          status: "FINISHED",
          valid: true,
          real_execution: true,
          statement_type: "QUERY",
          sql_hash: hashSql(sql || ""),
          sql_preview: truncateSqlPreview(sql),
          queue_name: queueName || "default",
          step_name: step && step.name ? step.name : null,
          step_type: step && step.type ? step.type : null,
          rows,
          column_names: columnNames,
        };
      }

      if (transportResult.status === "SUBMISSION_FAILED" || transportResult.status === "SUBMISSION_ERROR") {
        return {
          status: transportResult.status,
          valid: false,
          real_execution: true,
          http_status: transportResult.http_status || null,
          message: scrubSecrets(transportResult.message || "DLI SQL query submission failed."),
          response_body_snippet: transportResult.response_body_snippet || null,
        };
      }

      return {
        status: transportResult.status,
        valid: false,
        real_execution: false,
        message: transportResult.message || "Unexpected transport status.",
      };
    }

    const planId = nextPlanId();
    const sqlHash = hashSql(sql || "");

    return {
      job_id: planId,
      status: "PLANNED_NOT_EXECUTED",
      statement_type: "QUERY",
      sql_hash: sqlHash,
      sql_preview: truncateSqlPreview(sql),
      real_execution: false,
      queue_name: queueName || "default",
      step_name: step && step.name ? step.name : null,
      step_type: step && step.type ? step.type : null,
      planned_request: buildDliQueryRequest({
        sql,
        queueName,
        step,
        region: resolvedRegion,
        projectId: resolvedProjectId,
      }),
    };
  }

  async function getJobStatus({ jobId }) {
    if (allowRealExecution && !isRealExecutionAllowed()) {
      const guardCheck = assertRealDliExecutionAllowed({
        allowRealExecution,
        confirmNativeDli,
        understandExecutesSql,
      });
      const firstError = guardCheck.errors[0] || "Native DLI real execution guardrail blocked execution";
      throw new Error(firstError);
    }

    if (isRealExecutionAllowed()) {
      const transportResult = await transport.getSqlJobStatus({ jobId });

      if (transportResult.status === "NATIVE_DLI_TRANSPORT_NOT_CONFIGURED" ||
          transportResult.status === "NATIVE_DLI_TRANSPORT_NOT_IMPLEMENTED") {
        return {
          job_id: jobId,
          status: transportResult.status,
          valid: false,
          real_execution: false,
        };
      }

      return {
        job_id: transportResult.job_id || jobId,
        status: transportResult.status,
        valid: transportResult.status === "FINISHED",
        real_execution: transportResult.real_execution || false,
      };
    }

    return {
      job_id: jobId,
      status: "PLANNED_NOT_EXECUTED",
      real_execution: false,
    };
  }

  async function getJobResult({ jobId }) {
    if (allowRealExecution && !isRealExecutionAllowed()) {
      const guardCheck = assertRealDliExecutionAllowed({
        allowRealExecution,
        confirmNativeDli,
        understandExecutesSql,
      });
      const firstError = guardCheck.errors[0] || "Native DLI real execution guardrail blocked execution";
      throw new Error(firstError);
    }

    if (isRealExecutionAllowed()) {
      const transportResult = await transport.getSqlJobResult({ jobId });

      if (transportResult.status === "NATIVE_DLI_TRANSPORT_NOT_CONFIGURED" ||
          transportResult.status === "NATIVE_DLI_TRANSPORT_NOT_IMPLEMENTED") {
        return {
          job_id: jobId,
          status: transportResult.status,
          valid: false,
          real_execution: false,
          rows: [],
          column_names: [],
        };
      }

      return {
        job_id: transportResult.job_id || jobId,
        status: transportResult.status,
        valid: transportResult.status === "FINISHED",
        real_execution: transportResult.real_execution || false,
        rows: transportResult.rows || [],
        column_names: transportResult.column_names || [],
      };
    }

    return {
      job_id: jobId,
      status: "PLANNED_NOT_EXECUTED",
      real_execution: false,
      rows: [],
      column_names: [],
    };
  }

  async function pollTransportJob(transportInstance, jobId, maxAttempts = 60, intervalMs = 3000) {
    const { pollJobStatus: pollFn } = require("./dli-http-transport");
    return pollFn(transportInstance, jobId, maxAttempts, intervalMs);
  }

  async function listQueues() {
    if (!liveReadOnly) {
      return {
        status: "PLANNED_NOT_EXECUTED",
        real_execution: false,
        read_only: true,
        planned_request: buildDliListQueuesRequest({
          region: resolvedRegion,
          projectId: resolvedProjectId,
        }),
      };
    }

    if (!resolvedRegion || !resolvedProjectId || !ak || !sk) {
      throw new Error("Cannot list queues: missing region, project_id, AK, or SK for live read-only mode.");
    }

    const endpoint = `https://dli.${resolvedRegion}.myhuaweicloud.com`;
    const url = `${endpoint}/v1.0/${resolvedProjectId}/queues`;
    const res = await httpsGet(url, ak, sk);

    let queues = [];
    if (res.statusCode >= 200 && res.statusCode < 300) {
      try {
        const body = JSON.parse(res.body);
        queues = (body.queues || []).map((q) => ({
          queue_name: q.queue_name || q.queueName || null,
          queue_type: q.queue_type || q.queueType || null,
          queue_id: q.queue_id !== undefined ? q.queue_id : (q.queueId || null),
          owner: q.owner || null,
          cu_count: q.cu_count !== undefined ? q.cu_count : (q.cuCount || null),
        }));
      } catch {
        queues = [];
      }
    }

    return {
      status: res.statusCode >= 200 && res.statusCode < 300 ? "OK" : "ERROR",
      http_status: res.statusCode,
      read_only: true,
      real_execution: false,
      queues,
      queues_found: queues.length,
    };
  }

  async function describeQueue({ queueName } = {}) {
    const resolvedQueue = queueName || "default";

    if (!liveReadOnly) {
      return {
        status: "PLANNED_NOT_EXECUTED",
        real_execution: false,
        read_only: true,
        planned_request: buildDliQueueDescribeRequest({
          queueName: resolvedQueue,
          region: resolvedRegion,
          projectId: resolvedProjectId,
        }),
      };
    }

    if (!resolvedRegion || !resolvedProjectId || !ak || !sk) {
      throw new Error("Cannot describe queue: missing region, project_id, AK, or SK for live read-only mode.");
    }

    const endpoint = `https://dli.${resolvedRegion}.myhuaweicloud.com`;
    const url = `${endpoint}/v1.0/${resolvedProjectId}/queues/${encodeURIComponent(resolvedQueue)}`;
    const res = await httpsGet(url, ak, sk);

    let queue = null;
    if (res.statusCode >= 200 && res.statusCode < 300) {
      try {
        const body = JSON.parse(res.body);
        queue = {
          queue_name: body.queue_name || body.queueName || resolvedQueue,
          queue_type: body.queue_type || body.queueType || null,
          queue_id: body.queue_id !== undefined ? body.queue_id : (body.queueId || null),
          owner: body.owner || null,
          cu_count: body.cu_count !== undefined ? body.cu_count : (body.cuCount || null),
          status: body.status || null,
        };
      } catch {
        queue = null;
      }
    }

    return {
      status: res.statusCode >= 200 && res.statusCode < 300 ? "OK" : "ERROR",
      http_status: res.statusCode,
      read_only: true,
      real_execution: false,
      queue_name: resolvedQueue,
      queue,
      queue_exists: !!queue,
    };
  }

  return {
    executeSql,
    querySql,
    getJobStatus,
    getJobResult,
    listQueues,
    describeQueue,
    _liveReadOnly: liveReadOnly,
    _transport: transport,
  };
}

async function runReadOnlyDliPreflight(options = {}) {
  const configOverrides = options.config || {};

  const rtConfig = loadRuntimeConfig({
    configJsValues: configOverrides,
    envFilePath: options.envFilePath,
  });

  const region = options.region || rtConfig.region || null;
  const projectId = options.projectId || rtConfig.project_id || null;
  const ak = rtConfig.ak || null;
  const sk = rtConfig.sk || null;
  const queueName = options.queueName || rtConfig.dli_queue || "default";
  const client = options.client || createRealDliClient({ liveReadOnly: true, config: configOverrides, region, projectId });

  const safety = createDliLivePreflightSafetyPolicy();
  const liveChecks = [];
  const findings = [];
  const warnings = [];

  const credentialsPresent = !!(region && projectId && ak && sk);

  liveChecks.push({ name: "config_present", status: credentialsPresent ? "PASS" : "FAIL" });

  if (!credentialsPresent) {
    if (!region) findings.push("HUAWEI_REGION is not set");
    if (!projectId) findings.push("HUAWEI_PROJECT_ID is not set");
    if (!ak) findings.push("HUAWEI_AK is not set");
    if (!sk) findings.push("HUAWEI_SK is not set");

    return {
      status: "DLI_LIVE_PREFLIGHT_NOT_CONFIGURED",
      healthy: false,
      read_only: true,
      region,
      project_id: projectId ? "present" : null,
      queue_name: queueName,
      credentials_present: false,
      queue_accessible: false,
      source_map: rtConfig.source_map,
      env_file_status: rtConfig.env_file_status,
      live_checks: liveChecks,
      findings,
      warnings,
      safety,
    };
  }

  let clientInterfaceValid = false;
  try {
    if (client && typeof client.listQueues === "function" && typeof client.describeQueue === "function") {
      clientInterfaceValid = true;
    } else {
      findings.push("DLI client interface is missing read-only methods (listQueues, describeQueue)");
    }
  } catch (err) {
    findings.push(`Client interface validation failed: ${scrubSecrets(err.message)}`);
  }
  liveChecks.push({ name: "client_interface_valid", status: clientInterfaceValid ? "PASS" : "FAIL" });

  let authOk = false;
  let queueAccessible = false;

  try {
    const queuesResult = await client.listQueues();
    if (queuesResult.status === "OK" || queuesResult.status === "PLANNED_NOT_EXECUTED") {
      authOk = true;
      liveChecks.push({ name: "auth_or_credentials_check", status: "PASS" });

      const queues = queuesResult.queues || [];
      const queueMatch = queues.find((q) => q.queue_name === queueName);

      if (queuesResult.status === "PLANNED_NOT_EXECUTED") {
        liveChecks.push({ name: "queue_accessibility_check", status: "NOT_CHECKED" });
        warnings.push("Live API not invoked (plan-only mode). Queue accessibility not checked.");
      } else if (queueMatch) {
        queueAccessible = true;
        liveChecks.push({ name: "queue_accessibility_check", status: "PASS" });
      } else if (queues.length > 0) {
        liveChecks.push({ name: "queue_accessibility_check", status: "FAIL" });
        findings.push(`Queue "${queueName}" not found among ${queues.length} available queue(s).`);
      } else {
        liveChecks.push({ name: "queue_accessibility_check", status: "FAIL" });
        findings.push("No DLI queues found in this project.");
      }
    } else {
      liveChecks.push({ name: "auth_or_credentials_check", status: "FAIL" });
      findings.push(`DLI API authentication or connectivity failed (HTTP ${queuesResult.http_status || "unknown"})`);
      liveChecks.push({ name: "queue_accessibility_check", status: "NOT_CHECKED" });
    }
  } catch (err) {
    liveChecks.push({ name: "auth_or_credentials_check", status: "FAIL" });
    findings.push(`Live read-only check failed: ${scrubSecrets(err.message)}`);
    liveChecks.push({ name: "queue_accessibility_check", status: "NOT_CHECKED" });
  }

  const healthy = findings.length === 0 && authOk && (queueAccessible || liveChecks.some((c) => c.name === "queue_accessibility_check" && c.status === "NOT_CHECKED"));

  return {
    status: healthy ? "DLI_LIVE_PREFLIGHT_HEALTHY" : "DLI_LIVE_PREFLIGHT_UNHEALTHY",
    healthy,
    read_only: true,
    region,
    project_id: "present",
    queue_name: queueName,
    credentials_present: true,
    queue_accessible: queueAccessible,
    source_map: rtConfig.source_map,
    env_file_status: rtConfig.env_file_status,
    live_checks: liveChecks,
    findings,
    warnings,
    safety,
  };
}

module.exports = {
  createRealDliClient,
  assertRealDliExecutionAllowed,
  buildDliSqlExecutionRequest,
  buildDliQueryRequest,
  buildDliListQueuesRequest,
  buildDliQueueDescribeRequest,
  validateRealDliClientConfig,
  createRealDliSafetyPolicy,
  createDliLivePreflightSafetyPolicy,
  runReadOnlyDliPreflight,
  hashSql,
  truncateSqlPreview,
};
