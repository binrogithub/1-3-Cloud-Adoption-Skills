const fs = require("fs");
const path = require("path");
const https = require("https");
const config = require("./config");
const { buildSignedHeaders } = require("./huawei-signer");

const OUT_DIR = path.resolve(__dirname, "..", "out");

function maskId(id) {
  if (!id || id.length < 8) return "***";
  return id.slice(0, 4) + "***" + id.slice(-4);
}

function httpsRequest(url, options, timeoutMs = 30000) {
  return new Promise((resolve, reject) => {
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

    if (options.body) {
      req.write(options.body);
    }
    req.end();
  });
}

async function signedGet(url, ak, sk) {
  const headers = {
    "Content-Type": "application/json",
  };

  const signed = buildSignedHeaders({
    method: "GET",
    url,
    headers,
    body: "",
    ak,
    sk,
  });

  const parsed = new URL(url);
  const options = {
    hostname: parsed.hostname,
    port: 443,
    path: parsed.pathname + parsed.search,
    method: "GET",
    headers: signed,
  };

  return httpsRequest(url, options);
}

function normalizeQueue(raw) {
  return {
    queueName: raw.queue_name || raw.queueName || null,
    queueType: raw.queue_type || raw.queueType || null,
    queueId: raw.queue_id !== undefined ? raw.queue_id : (raw.queueId || null),
    owner: raw.owner || null,
    cuCount: raw.cu_count !== undefined ? raw.cu_count : (raw.cuCount || null),
    chargingMode: raw.charging_mode !== undefined ? raw.charging_mode : (raw.chargingMode || null),
    description: raw.description || null,
  };
}

function isSuitableQueue(queue) {
  const queueType = (queue.queueType || "").toLowerCase();
  const queueName = (queue.queueName || "").toLowerCase();
  if (queueType === "sql" || queueType === "general") return true;
  if (queueName.includes("default") || queueName.includes("sql") || queueName.includes("general")) return true;
  return false;
}

function recommendQueue(queues) {
  const suitable = queues.filter(isSuitableQueue);
  if (suitable.length > 0) return suitable[0];
  if (queues.length > 0) return queues[0];
  return null;
}

function generateMarkdownReport(data) {
  const lines = [];
  const ts = data.timestamp;

  lines.push("# DLI Validation Report");
  lines.push("");
  lines.push(`**Timestamp:** ${ts}`);
  lines.push(`**Status:** ${data.status}`);
  lines.push(`**DLI Access:** ${data.dli_access}`);
  lines.push("");

  lines.push("## Environment");
  lines.push("");
  lines.push("| Field | Value |");
  lines.push("|-------|-------|");
  lines.push(`| Region | ${data.region} |`);
  lines.push(`| Project ID | ${data.project_id_masked} |`);
  lines.push(`| DLI Endpoint | ${data.endpoint} |`);
  lines.push(`| Configured Queue | ${data.configured_queue} |`);
  lines.push("");

  lines.push("## Queue Discovery");
  lines.push("");

  if (data.dli_access === "VALID") {
    lines.push(`DLI API is reachable. Found **${data.queues_found}** queue(s).`);
    lines.push("");

    if (data.queues && data.queues.length > 0) {
      lines.push("| # | Queue Name | Type | Owner | CU | Suitable |");
      lines.push("|---|------------|------|-------|----|----------|");
      for (let i = 0; i < data.queues.length; i++) {
        const q = data.queues[i];
        lines.push(`| ${i + 1} | ${q.queueName || "N/A"} | ${q.queueType || "N/A"} | ${q.owner || "N/A"} | ${q.cuCount !== null ? q.cuCount : "N/A"} | ${isSuitableQueue(q) ? "Yes" : "No"} |`);
      }
      lines.push("");
    }

    if (data.selected_queue) {
      lines.push(`**Selected/Recommended Queue:** \`${data.selected_queue}\``);
    } else {
      lines.push("**No suitable queue found.**");
    }
  } else {
    lines.push(`DLI API is **not** reachable or returned an error.`);
    lines.push("");
    if (data.api_error) {
      lines.push(`**API Error:** ${data.api_error}`);
      lines.push("");
    }
  }

  lines.push("");

  if (data.blockers && data.blockers.length > 0) {
    lines.push("## Blockers");
    lines.push("");
    for (const b of data.blockers) {
      lines.push(`- ${b}`);
    }
    lines.push("");
  } else {
    lines.push("## Blockers");
    lines.push("");
    lines.push("None.");
    lines.push("");
  }

  lines.push("## Safety Statement");
  lines.push("");
  lines.push("> **No SQL was executed. No DLI job was submitted. No resources were created, updated, or deleted.**");
  lines.push(">");
  lines.push("> This command only called `GET /v1.0/{project_id}/queues` (read-only).");
  lines.push("> It did NOT call POST, PUT, PATCH, or DELETE on any endpoint.");
  lines.push("> No SQL was executed.");
  lines.push("");

  return lines.join("\n");
}

async function main() {
  console.log("=== DataArts Deploy Agent: DLI VALIDATE (read-only) ===\n");

  try {
    const env = config.load();
    config.validate(env);

    const region = env.HUAWEI_REGION;
    const projectId = env.HUAWEI_PROJECT_ID;
    const ak = env.HUAWEI_AK;
    const sk = env.HUAWEI_SK;
    const configuredQueueName = (env.DLI_QUEUE_NAME || "AUTO_DISCOVER").trim();

    const endpointHost = `dli.${region}.myhuaweicloud.com`;
    const endpoint = `https://${endpointHost}`;

    console.log(`Endpoint:  ${endpoint}`);
    console.log(`Region:    ${region}`);
    console.log(`Project:   ${maskId(projectId)}`);
    console.log(`Queue:     ${configuredQueueName}`);
    console.log("");

    const queuesUrl = `${endpoint}/v1.0/${projectId}/queues`;
    console.log("Fetching DLI queues...");
    console.log(`  GET /v1.0/${maskId(projectId)}/queues`);

    let apiResult;
    let apiError = null;
    let dliAccess = "UNKNOWN";

    try {
      apiResult = await signedGet(queuesUrl, ak, sk);
    } catch (err) {
      apiError = `Network error: ${err.message}`;
      dliAccess = "INVALID";
      console.log(`  Error: ${err.message}`);
    }

    let queues = [];
    let httpStatus = null;

    if (apiResult) {
      httpStatus = apiResult.statusCode;
      console.log(`  Status: ${httpStatus}`);

      if (httpStatus >= 200 && httpStatus < 300) {
        dliAccess = "VALID";
        try {
          const body = JSON.parse(apiResult.body);
          const rawQueues = body.queues || [];
          if (Array.isArray(rawQueues)) {
            queues = rawQueues.map(normalizeQueue);
          }
        } catch {
          queues = [];
        }
        console.log(`  Queues found: ${queues.length}`);
        for (const q of queues) {
          console.log(`    - ${q.queueName || "(unnamed)"} [type=${q.queueType || "?"}, owner=${q.owner || "?"}]`);
        }
      } else if (httpStatus === 401 || httpStatus === 403) {
        dliAccess = "INVALID";
        apiError = `Authentication/authorization failed (HTTP ${httpStatus})`;
        console.log(`  Auth failed: HTTP ${httpStatus}`);
      } else if (httpStatus === 404) {
        dliAccess = "INVALID";
        apiError = `DLI endpoint not found (HTTP 404). DLI may not be available in region ${region}.`;
        console.log("  DLI endpoint not found in this region.");
      } else {
        dliAccess = "INVALID";
        apiError = `Unexpected HTTP ${httpStatus}: ${(apiResult.body || "").slice(0, 200)}`;
        console.log(`  Unexpected status: ${httpStatus}`);
      }
    }

    console.log("");

    let selectedQueue = null;
    let blockers = [];

    if (dliAccess !== "VALID") {
      blockers.push(`DLI API access is invalid: ${apiError || "unknown error"}`);
      blockers.push("Cannot validate or select a DLI queue.");
      blockers.push("Ensure DLI is enabled in this region and AK/SK has DLI permissions.");
    } else if (queues.length === 0) {
      blockers.push("No DLI queues found in this project.");
      blockers.push("A DLI queue must exist before executing SQL.");
      blockers.push("Create a queue via the DLI console or CLI, then re-run validation.");
    } else if (configuredQueueName !== "AUTO_DISCOVER") {
      const match = queues.find((q) => q.queueName === configuredQueueName);
      if (match) {
        selectedQueue = match.queueName;
        console.log(`Configured queue "${configuredQueueName}" found.`);
      } else {
        blockers.push(`Configured queue "${configuredQueueName}" not found among available queues.`);
        blockers.push(`Available queues: ${queues.map((q) => q.queueName).join(", ")}`);
        const rec = recommendQueue(queues);
        if (rec) {
          console.log(`  Queue "${configuredQueueName}" NOT found. Recommending: ${rec.queueName}`);
          selectedQueue = null;
        }
      }
    } else {
      const rec = recommendQueue(queues);
      if (rec) {
        selectedQueue = rec.queueName;
        console.log(`Auto-discover: recommending queue "${selectedQueue}"`);
      } else {
        blockers.push("No suitable SQL/general queue found among available queues.");
        blockers.push("Create a DLI SQL queue via the DLI console or CLI.");
      }
    }

    console.log("");

    const status = blockers.length === 0 ? "PASS" : "FAIL";

    const timestamp = new Date().toISOString();

    const jsonReport = {
      timestamp,
      status,
      dli_access: dliAccess,
      region,
      project_id_masked: maskId(projectId),
      endpoint,
      configured_queue: configuredQueueName,
      queues_found: queues.length,
      queues: queues.map((q) => ({
        queueName: q.queueName,
        queueType: q.queueType,
        owner: q.owner,
        cuCount: q.cuCount,
        chargingMode: q.chargingMode,
        description: q.description,
      })),
      selected_queue: selectedQueue,
      api_error: apiError,
      http_status: httpStatus,
      blockers,
      safety: {
        no_sql_executed: true,
        no_job_submitted: true,
        no_create: true,
        no_update: true,
        no_delete: true,
        method: "GET",
        read_only: true,
      },
      no_secrets_included: true,
    };

    const mdReport = generateMarkdownReport(jsonReport);

    if (!fs.existsSync(OUT_DIR)) {
      fs.mkdirSync(OUT_DIR, { recursive: true });
    }

    fs.writeFileSync(
      path.join(OUT_DIR, "dli_validation_result.json"),
      JSON.stringify(jsonReport, null, 2),
      "utf-8"
    );

    fs.writeFileSync(
      path.join(OUT_DIR, "dli_validation_report.md"),
      mdReport,
      "utf-8"
    );

    console.log("=== Validation Result ===");
    console.log(`  Status:      ${status}`);
    console.log(`  DLI Access:  ${dliAccess}`);
    console.log(`  Queues:      ${queues.length}`);
    console.log(`  Selected:    ${selectedQueue || "(none)"}`);
    if (blockers.length > 0) {
      console.log("  Blockers:");
      for (const b of blockers) {
        console.log(`    - ${b}`);
      }
    }
    console.log("");
    console.log("Safety: No SQL was executed. No DLI job was submitted. No resources were created, updated, or deleted.");
    console.log("");
    console.log("Reports saved:");
    console.log(`  ${path.join(OUT_DIR, "dli_validation_result.json")}`);
    console.log(`  ${path.join(OUT_DIR, "dli_validation_report.md")}`);

    process.exit(status === "PASS" ? 0 : 1);
  } catch (err) {
    console.error(`DLI VALIDATE FAILED: ${err.message}`);
    process.exit(1);
  }
}

main();
