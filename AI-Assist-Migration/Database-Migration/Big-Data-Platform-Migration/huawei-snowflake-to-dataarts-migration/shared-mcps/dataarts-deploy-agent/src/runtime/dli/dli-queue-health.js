const { buildSafetyPolicy } = require("../../core/safety-policy");
const { scrubSecrets } = require("../../core/secret-scrubber");
const { loadRuntimeConfig, validateRuntimeConfig } = require("../../config/runtime-config-loader");
const { buildSignedHeaders } = require("../../huawei-signer");
const https = require("https");

function buildDliQueueHealthSafetyPolicy() {
  return buildSafetyPolicy({
    dli_queue_health: true,
    read_only: true,
    no_sql_execution: true,
    no_job_cancel: true,
    no_cloud_write_calls: true,
    no_runtime_execution: true,
    no_confirm: true,
    secrets_redacted: true,
  });
}

function buildDliListJobsRequest(options = {}) {
  const { region, projectId } = options;
  const resolvedRegion = region || null;
  const resolvedProjectId = projectId || null;

  return {
    service: "DLI",
    operation: "listSqlJobs",
    method: "GET",
    endpoint: resolvedRegion ? `https://dli.${resolvedRegion}.myhuaweicloud.com` : null,
    path: resolvedProjectId ? `/v1.0/${resolvedProjectId}/jobs?limit=1000` : null,
    region: resolvedRegion,
    project_id: resolvedProjectId,
    read_only: true,
    execution_mode: "READ_ONLY",
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

function countJobsByState(jobs) {
  const counts = {
    LAUNCHING: 0,
    RUNNING: 0,
    FINISHED: 0,
    FAILED: 0,
    CANCELLED: 0,
    UNKNOWN: 0,
  };

  for (const job of jobs) {
    const status = (job.status || "UNKNOWN").toUpperCase();
    if (counts[status] !== undefined) {
      counts[status]++;
    } else {
      counts.UNKNOWN++;
    }
  }

  return counts;
}

async function checkDliQueueHealth(options = {}) {
  const safety = buildDliQueueHealthSafetyPolicy();

  if (options.readOnly !== true) {
    return {
      status: "READ_ONLY_FLAG_REQUIRED",
      healthy: false,
      read_only: true,
      queue_name: options.queueName || "default",
      jobs_by_state: null,
      total_jobs: null,
      findings: ["--read-only is required for DLI queue health check"],
      warnings: [],
      safety,
    };
  }

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

  const findings = [];
  const warnings = [];

  const credentialsPresent = !!(region && projectId && ak && sk);

  if (!credentialsPresent) {
    if (!region) findings.push("HUAWEI_REGION is not set");
    if (!projectId) findings.push("HUAWEI_PROJECT_ID is not set");
    if (!ak) findings.push("HUAWEI_AK is not set");
    if (!sk) findings.push("HUAWEI_SK is not set");

    return {
      status: "DLI_QUEUE_HEALTH_NOT_CONFIGURED",
      healthy: false,
      read_only: true,
      queue_name: queueName,
      jobs_by_state: null,
      total_jobs: null,
      credentials_present: false,
      findings,
      warnings,
      safety,
    };
  }

  const plannedRequest = buildDliListJobsRequest({ region, projectId });

  if (!plannedRequest.endpoint || !plannedRequest.path) {
    return {
      status: "DLI_QUEUE_HEALTH_NOT_CONFIGURED",
      healthy: false,
      read_only: true,
      queue_name: queueName,
      jobs_by_state: null,
      total_jobs: null,
      credentials_present: true,
      findings: ["Cannot construct DLI jobs list URL without region and projectId"],
      warnings,
      safety,
    };
  }

  const listJobsUrl = `${plannedRequest.endpoint}${plannedRequest.path}`;

  try {
    const res = await httpsGet(listJobsUrl, ak, sk);

    if (res.statusCode < 200 || res.statusCode >= 300) {
      findings.push(`DLI jobs list API returned HTTP ${res.statusCode}`);
      return {
        status: "DLI_QUEUE_HEALTH_API_ERROR",
        healthy: false,
        read_only: true,
        queue_name: queueName,
        jobs_by_state: null,
        total_jobs: null,
        credentials_present: true,
        api_http_status: res.statusCode,
        findings,
        warnings,
        safety,
      };
    }

    let jobs = [];
    try {
      const body = JSON.parse(res.body);
      jobs = body.jobs || [];
    } catch {
      warnings.push("Could not parse DLI jobs list response body");
    }

    const jobsByState = countJobsByState(jobs);
    const totalJobs = jobs.length;

    const congested = jobsByState.LAUNCHING > (options.maxLaunchingJobs || 10);
    if (congested) {
      findings.push(`Queue congestion detected: ${jobsByState.LAUNCHING} jobs in LAUNCHING state (threshold: ${options.maxLaunchingJobs || 10})`);
    }

    const healthy = !congested && findings.length === 0;

    return {
      status: healthy ? "DLI_QUEUE_HEALTH_OK" : "DLI_QUEUE_HEALTH_UNHEALTHY",
      healthy,
      congested,
      read_only: true,
      queue_name: queueName,
      jobs_by_state: jobsByState,
      total_jobs: totalJobs,
      credentials_present: true,
      findings,
      warnings,
      safety,
    };
  } catch (err) {
    findings.push(`DLI jobs list API call failed: ${scrubSecrets(err.message)}`);

    return {
      status: "DLI_QUEUE_HEALTH_API_ERROR",
      healthy: false,
      read_only: true,
      queue_name: queueName,
      jobs_by_state: null,
      total_jobs: null,
      credentials_present: true,
      findings,
      warnings,
      safety,
    };
  }
}

module.exports = {
  checkDliQueueHealth,
  buildDliQueueHealthSafetyPolicy,
  buildDliListJobsRequest,
  countJobsByState,
};
