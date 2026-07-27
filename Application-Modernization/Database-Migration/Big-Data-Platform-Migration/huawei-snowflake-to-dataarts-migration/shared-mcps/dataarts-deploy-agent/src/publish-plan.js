const fs = require("fs");
const path = require("path");
const config = require("./config");

const OUT_DIR = path.resolve(__dirname, "..", "out");
const EVIDENCE_DIR = path.join(OUT_DIR, "evidence");

const VERIFY_RESULT_FILE = path.join(OUT_DIR, "verify_job_result.json");
const VERIFY_REPORT_FILE = path.join(OUT_DIR, "verify_job_report.md");
const V1_REQUEST_FILE = path.join(OUT_DIR, "dataarts_create_job_request.v1.dryrun.json");
const FINAL_STATUS_FILE = path.join(EVIDENCE_DIR, "final_demo_status_report.json");

function maskId(id) {
  if (!id || id.length < 8) return "***";
  return id.slice(0, 4) + "***" + id.slice(-4);
}

function readFileJson(filePath, label) {
  if (!fs.existsSync(filePath)) {
    throw new Error(`Missing ${label}: ${filePath}`);
  }
  return JSON.parse(fs.readFileSync(filePath, "utf-8"));
}

function readFileText(filePath, label) {
  if (!fs.existsSync(filePath)) {
    throw new Error(`Missing ${label}: ${filePath}`);
  }
  return fs.readFileSync(filePath, "utf-8");
}

function main() {
  console.log("=== DataArts Deploy Agent: PUBLISH PLAN (read-only) ===\n");

  try {
    const env = config.load();
    config.validate(env);
    console.log("[1/5] Environment loaded and validated.\n");

    const verifyResult = readFileJson(VERIFY_RESULT_FILE, "verify-job result");
    const verifyReportMd = readFileText(VERIFY_REPORT_FILE, "verify-job report");
    const v1Request = readFileJson(V1_REQUEST_FILE, "v1 dry-run request");
    const finalStatus = readFileJson(FINAL_STATUS_FILE, "final status report");
    console.log("[2/5] Input files read successfully.\n");

    const v1Body = v1Request.body || v1Request;
    const jobName = v1Body.name;
    const processType = v1Body.processType;
    const nodeCount = (v1Body.nodes || []).length;
    const verifySummary = verifyResult.summary || {};
    const failCount = verifySummary.fail || 0;
    const passCount = verifySummary.pass || 0;
    const warnCount = verifySummary.warn || 0;
    const apiJobName = verifyResult.job_name;
    const apiJobFound = verifyResult.job_found;

    console.log("[3/5] Pre-readiness checks...\n");

    const readinessChecks = [];

    const check1 = apiJobFound && apiJobName === "snowflake_to_dataarts_demo_v2";
    readinessChecks.push({
      check: "Job exists and name matches",
      status: check1 ? "PASS" : "FAIL",
      detail: check1
        ? `Job "${apiJobName}" found via API`
        : `Job name mismatch or not found: "${apiJobName}"`,
    });

    const check2 = failCount === 0;
    readinessChecks.push({
      check: "verify-job had 0 FAIL",
      status: check2 ? "PASS" : "FAIL",
      detail: check2
        ? `verify-job: PASS=${passCount} WARN=${warnCount} FAIL=${failCount}`
        : `verify-job had ${failCount} FAIL(s)`,
    });

    const check3 = nodeCount === 3;
    readinessChecks.push({
      check: "Node count = 3",
      status: check3 ? "PASS" : "FAIL",
      detail: check3 ? "3 nodes in payload" : `${nodeCount} nodes in payload`,
    });

    const check4 = processType === "BATCH";
    readinessChecks.push({
      check: "processType = BATCH",
      status: check4 ? "PASS" : "FAIL",
      detail: check4 ? "BATCH confirmed" : `Got: ${processType}`,
    });

    const allReady = readinessChecks.every((c) => c.status === "PASS");

    console.log("[4/5] Publish readiness assessment...\n");

    const timestamp = new Date().toISOString();
    const projectIdMasked = maskId(env.HUAWEI_PROJECT_ID);
    const workspaceIdMasked = maskId(env.DATAARTS_WORKSPACE_ID);
    const publishEndpointStatus = "UNKNOWN_REQUIRES_CONFIRMATION";

    const publishPlanResult = {
      timestamp,
      status: allReady ? "PUBLISH_READY_PLAN_ONLY" : "NOT_READY",
      job_name: jobName,
      verify_job_passed: check2,
      verify_job_summary: { pass: passCount, warn: warnCount, fail: failCount },
      node_count: nodeCount,
      process_type: processType,
      publish_endpoint_status: publishEndpointStatus,
      no_api_calls_made: true,
      safety: {
        no_publish: true,
        no_start: true,
        no_run: true,
        no_update: true,
        no_delete: true,
      },
    };

    const lines = [];
    lines.push("# Publish Plan Report");
    lines.push("");
    lines.push(`**Timestamp:** ${timestamp}`);
    lines.push(`**Status:** ${allReady ? "PUBLISH READY (plan only — no action taken)" : "NOT READY"}`);
    lines.push("");

    lines.push("## Current Job");
    lines.push("");
    lines.push("| Field | Value |");
    lines.push("|-------|-------|");
    lines.push(`| Job Name | ${jobName} |`);
    lines.push(`| processType | ${processType} |`);
    lines.push(`| Node Count | ${nodeCount} |`);
    lines.push(`| project_id | ${projectIdMasked} |`);
    lines.push(`| workspace_id | ${workspaceIdMasked} |`);
    lines.push(`| Current State | Created and verified |`);
    lines.push(`| Publish Status | Not published yet |`);
    lines.push(`| Start/Run Status | Not started |`);
    lines.push("");

    lines.push("## Verification Result Summary");
    lines.push("");
    lines.push("| Status | Count |");
    lines.push("|--------|-------|");
    lines.push(`| PASS | ${passCount} |`);
    lines.push(`| WARN | ${warnCount} |`);
    lines.push(`| FAIL | ${failCount} |`);
    lines.push("");

    lines.push("## Readiness Checks");
    lines.push("");
    lines.push("| Check | Status | Detail |");
    lines.push("|-------|--------|--------|");
    for (const c of readinessChecks) {
      lines.push(`| ${c.check} | ${c.status} | ${c.detail} |`);
    }
    lines.push("");

    lines.push("## Publish Endpoint Status");
    lines.push("");
    lines.push(`**${publishEndpointStatus}**`);
    lines.push("");
    lines.push("No confirmed DataArts Factory publish endpoint has been identified from local API Explorer capture or official documentation available in this workspace.");
    lines.push("");

    lines.push("## What Publishing Would Mean");
    lines.push("");
    lines.push("Publishing the DataArts job would:");
    lines.push("");
    lines.push("1. Make the job available for scheduling/execution according to the DataArts Factory job lifecycle.");
    lines.push("2. Transition the job from a draft/unpublished state to a published state where it can be scheduled.");
    lines.push("3. Be a **separate** operation from start/run — publishing does not immediately execute the pipeline.");
    lines.push("");
    lines.push("The exact API endpoint and payload for publishing require confirmation before implementation.");
    lines.push("");

    lines.push("## Safety Statement");
    lines.push("");
    lines.push("> **No publish, start, run, update, delete, or API write operation was executed.**");
    lines.push(">");
    lines.push("> This command performed a read-only assessment of local files only.");
    lines.push("> No Huawei Cloud API calls were made.");
    lines.push("> No write, publish, start, or destructive operation was executed.");
    lines.push("");

    lines.push("## Next Recommended Step");
    lines.push("");
    lines.push("**Confirm the official DataArts publish endpoint/payload before implementing `publish-job`.**");
    lines.push("");
    lines.push("Potential sources:");
    lines.push("- DataArts Factory API Explorer in Huawei Cloud console");
    lines.push("- Official DataArts Factory API documentation (publish/submit version endpoint)");
    lines.push("- Local API capture from a manual publish operation in the console");
    lines.push("");

    const mdReport = lines.join("\n");

    if (!fs.existsSync(OUT_DIR)) {
      fs.mkdirSync(OUT_DIR, { recursive: true });
    }

    const mdPath = path.join(OUT_DIR, "publish_plan_report.md");
    const jsonPath = path.join(OUT_DIR, "publish_plan_result.json");

    fs.writeFileSync(mdPath, mdReport, "utf-8");
    fs.writeFileSync(jsonPath, JSON.stringify(publishPlanResult, null, 2), "utf-8");

    console.log("[5/5] Reports generated.\n");

    console.log("=== Publish Readiness Summary ===\n");
    console.log(`  Job Name:       ${jobName}`);
    console.log(`  project_id:     ${projectIdMasked}`);
    console.log(`  workspace_id:   ${workspaceIdMasked}`);
    console.log(`  Current State:  Created and verified`);
    console.log(`  Publish Status: Not published yet`);
    console.log(`  Start/Run:      Not started`);
    console.log(`  Publish Ready:  ${allReady ? "YES" : "NO"}`);
    console.log(`  Endpoint:       ${publishEndpointStatus}`);
    console.log("");

    console.log("=== Readiness Checks ===\n");
    for (const c of readinessChecks) {
      console.log(`  [${c.status}] ${c.check}: ${c.detail}`);
    }
    console.log("");

    console.log("=== What Publishing Would Mean ===\n");
    console.log("  Publishing would make the DataArts job available for");
    console.log("  scheduling/execution according to the DataArts lifecycle.");
    console.log("  It is separate from start/run — publishing does not execute the pipeline.");
    console.log("");

    console.log("Safety: No publish, start, run, update, delete, or API write operation was executed.");
    console.log("No Huawei Cloud API calls were made.\n");

    console.log("Reports saved:");
    console.log(`  ${mdPath}`);
    console.log(`  ${jsonPath}`);

    process.exit(allReady ? 0 : 1);
  } catch (err) {
    console.error(`PUBLISH PLAN FAILED: ${err.message}`);
    process.exit(1);
  }
}

main();
