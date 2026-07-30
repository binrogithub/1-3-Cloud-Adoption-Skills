const fs = require("fs");
const path = require("path");
const config = require("./config");

const ROOT = path.resolve(__dirname, "..");
const OUT_DIR = path.join(ROOT, "out");

const VERIFY_RESULT_FILE = path.join(OUT_DIR, "verify_job_result.json");
const DLI_VALIDATE_RESULT_FILE = path.join(OUT_DIR, "dli_validate_demo_data_result.json");
const V1_REQUEST_FILE = path.join(OUT_DIR, "dataarts_create_job_request.v1.dryrun.json");
const EXPORT_RESULT_FILE = path.join(OUT_DIR, "exported_job", "export_job_definition_result.json");

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

function main() {
  console.log("=== DataArts Deploy Agent: RUN-IMMEDIATE PLAN (read-only, local-only) ===\n");

  try {
    console.log("[1/6] Loading and validating environment...\n");
    const env = config.load();
    config.validate(env);

    const jobName = env.DATAARTS_JOB_NAME;
    console.log(`  DATAARTS_JOB_NAME = ${jobName}`);

    if (!jobName) {
      throw new Error("DATAARTS_JOB_NAME is not set. Provide it via --job-name CLI arg, MCP argument, or env var.");
    }
    console.log("  Job name confirmed.\n");

    const endpointHost = `dayu-dlf.${env.HUAWEI_REGION}.myhuaweicloud.com`;
    const endpoint = `https://${endpointHost}`;
    const projectId = env.HUAWEI_PROJECT_ID;
    const workspaceId = env.DATAARTS_WORKSPACE_ID;
    const projectIdMasked = maskId(projectId);
    const workspaceIdMasked = maskId(workspaceId);

    console.log("[2/6] Reading verify/export results...\n");

    const verifyResult = readFileJson(VERIFY_RESULT_FILE, "verify-job result");
    console.log(`  verify_job_result.json loaded`);
    console.log(`    job_name: ${verifyResult.job_name}`);
    console.log(`    job_found: ${verifyResult.job_found}`);
    console.log(`    summary: PASS=${verifyResult.summary.pass} WARN=${verifyResult.summary.warn} FAIL=${verifyResult.summary.fail}`);

    const exportExists = fs.existsSync(EXPORT_RESULT_FILE);
    if (exportExists) {
      const exportResult = readFileJson(EXPORT_RESULT_FILE, "export-job result");
      console.log(`  export_job_definition_result.json loaded`);
      console.log(`    http_status: ${exportResult.http_status}`);
      console.log(`    export_successful: ${exportResult.export_successful}`);
    } else {
      console.log(`  export_job_definition_result.json not found (skipping)`);
    }

    const v1Exists = fs.existsSync(V1_REQUEST_FILE);
    if (v1Exists) {
      const v1Request = readFileJson(V1_REQUEST_FILE, "v1 dry-run request");
      const v1Body = v1Request.body || v1Request;
      console.log(`  v1 dry-run request loaded: name=${v1Body.name}, nodes=${(v1Body.nodes || []).length}`);
    } else {
      console.log(`  v1 dry-run request not found (skipping)`);
    }
    console.log("");

    console.log("[3/6] Confirming v3 has 0 FAIL in verify-job...\n");
    const failCount = verifyResult.summary.fail || 0;
    if (failCount > 0) {
      throw new Error(`verify-job has ${failCount} FAIL(s). Must resolve before run-immediate.`);
    }
    console.log(`  verify-job: 0 FAIL confirmed.\n`);

    console.log("[4/6] Confirming DLI demo data validation...\n");
    const dliValidateExists = fs.existsSync(DLI_VALIDATE_RESULT_FILE);
    let dliValidated = false;
    if (dliValidateExists) {
      const dliResult = readFileJson(DLI_VALIDATE_RESULT_FILE, "DLI validate demo data result");
      dliValidated = dliResult.overall_status === "PASS";
      if (dliValidated) {
        console.log(`  DLI demo data validation: PASS`);
        const checks = dliResult.checks || [];
        for (const c of checks) {
          console.log(`    [${c.result}] ${c.check}`);
        }
      } else {
        console.log(`  DLI demo data validation: ${dliResult.overall_status} (NOT PASS)`);
      }
    } else {
      console.log(`  dli_validate_demo_data_result.json not found. Skipping DLI validation check.`);
    }
    console.log("");

    console.log("[5/6] Generating execution plan...\n");

    const timestamp = new Date().toISOString();
    const apiPath = `/v1/${projectId}/jobs/${encodeURIComponent(jobName)}/run-immediate`;
    const apiPathMasked = `/v1/${projectIdMasked}/jobs/${jobName}/run-immediate`;

    const planResult = {
      timestamp,
      status: "PLAN_READY",
      job_name: jobName,
      endpoint,
      project_id_masked: projectIdMasked,
      workspace_id_masked: workspaceIdMasked,
      method: "POST",
      path: apiPathMasked,
      no_publish: true,
      no_start: true,
      no_delete: true,
      no_update: true,
      preflight: {
        method: "GET",
        path: `/v1/${projectIdMasked}/jobs/${jobName}`,
        purpose: "Confirm job exists before run-immediate",
      },
      verify_job_summary: verifyResult.summary,
      dli_demo_data_validated: dliValidated,
      dli_validation_checked: dliValidateExists,
      no_api_calls_made: true,
      safety: {
        no_publish: true,
        no_start: true,
        no_run_immediate_yet: true,
        no_update: true,
        no_delete: true,
        no_overwrite: true,
        no_api_calls_made: true,
      },
    };

    const lines = [];
    lines.push("# Run-Immediate Plan Report");
    lines.push("");
    lines.push(`**Timestamp:** ${timestamp}`);
    lines.push(`**Status:** PLAN READY — one-time controlled execution only`);
    lines.push("");
    lines.push("## Execution Plan");
    lines.push("");
    lines.push("This plan describes a **one-time immediate execution** of the DataArts job.");
    lines.push("No recurring schedule will be enabled.");
    lines.push("");
    lines.push("| Field | Value |");
    lines.push("|-------|-------|");
    lines.push(`| Job Name | ${jobName} |`);
    lines.push(`| Workspace | ${workspaceIdMasked} |`);
    lines.push(`| Endpoint | ${endpoint} |`);
    lines.push(`| Method | POST |`);
    lines.push(`| Path | ${apiPathMasked} |`);
    lines.push(`| No Publish | Yes |`);
    lines.push(`| No Start | Yes (run-immediate, not /start) |`);
    lines.push(`| No Delete | Yes |`);
    lines.push(`| No Update | Yes |`);
    lines.push("");

    lines.push("## Preflight Check");
    lines.push("");
    lines.push("Before calling run-immediate, a preflight GET will confirm the job exists:");
    lines.push("");
    lines.push(`- **Method:** GET`);
    lines.push(`- **Path:** /v1/${projectIdMasked}/jobs/${jobName}`);
    lines.push(`- **Purpose:** Abort if job is not found`);
    lines.push("");

    lines.push("## Verification Status");
    lines.push("");
    lines.push("| Check | Result |");
    lines.push("|-------|--------|");
    lines.push(`| verify-job PASS count | ${verifyResult.summary.pass} |`);
    lines.push(`| verify-job WARN count | ${verifyResult.summary.warn} |`);
    lines.push(`| verify-job FAIL count | ${verifyResult.summary.fail} |`);
    lines.push(`| DLI demo data validated | ${dliValidateExists ? (dliValidated ? "PASS" : "NOT PASS") : "Not checked (file absent)"} |`);
    lines.push("");

    lines.push("## Export Status");
    lines.push("");
    if (exportExists) {
      const exportResult = readFileJson(EXPORT_RESULT_FILE, "export-job result");
      lines.push(`- Exported: Yes (HTTP ${exportResult.http_status})`);
      lines.push(`- All nodes found: ${exportResult.all_nodes_found ? "Yes" : "No"}`);
    } else {
      lines.push("- Export result not available");
    }
    lines.push("");

    lines.push("## What Run-Immediate Does");
    lines.push("");
    lines.push("Calling `POST /v1/{project_id}/jobs/{job_name}/run-immediate` will:");
    lines.push("");
    lines.push("1. Trigger a **one-time execution** of the DataArts job.");
    lines.push("2. The job will execute its node dependency chain: load_silver_orders → build_gold_daily_sales → audit_pipeline.");
    lines.push("3. Each node runs its DLI SQL against the demo_migration database.");
    lines.push("4. This does **not** enable a recurring schedule.");
    lines.push("5. This does **not** publish the job.");
    lines.push("");

    lines.push("## What This Does NOT Do");
    lines.push("");
    lines.push("- Does NOT call `POST /v1/{project_id}/jobs/{job_name}/start` (no scheduled start)");
    lines.push("- Does NOT publish the job");
    lines.push("- Does NOT call any PUT, PATCH, or DELETE endpoint");
    lines.push("- Does NOT enable recurring schedule");
    lines.push("- Does NOT update or overwrite the job definition");
    lines.push("");

    lines.push("## Safety Statement");
    lines.push("");
    lines.push("> **No Huawei Cloud API write operation was executed.**");
    lines.push(">");
    lines.push("> This command performed a read-only assessment of local files only.");
    lines.push("> No Huawei Cloud API calls were made.");
    lines.push("> No publish, start, run-immediate, update, or delete operation was executed.");
    lines.push("");

    const mdReport = lines.join("\n");

    if (!fs.existsSync(OUT_DIR)) {
      fs.mkdirSync(OUT_DIR, { recursive: true });
    }

    const mdPath = path.join(OUT_DIR, "run_immediate_plan_report.md");
    const jsonPath = path.join(OUT_DIR, "run_immediate_plan_result.json");

    fs.writeFileSync(mdPath, mdReport, "utf-8");
    fs.writeFileSync(jsonPath, JSON.stringify(planResult, null, 2), "utf-8");

    console.log("[6/6] Summary\n");

    console.log("=== Run-Immediate Plan Summary ===\n");
    console.log(`  Job Name:     ${jobName}`);
    console.log(`  Endpoint:     ${endpoint}`);
    console.log(`  Method:       POST`);
    console.log(`  Path:         ${apiPathMasked}`);
    console.log(`  Preflight:    GET /v1/${projectIdMasked}/jobs/${jobName}`);
    console.log(`  No Publish:   Yes`);
    console.log(`  No Start:     Yes (run-immediate, not /start)`);
    console.log(`  No Delete:    Yes`);
    console.log(`  No Update:    Yes`);
    console.log(`  Verify:       PASS=${verifyResult.summary.pass} WARN=${verifyResult.summary.warn} FAIL=${verifyResult.summary.fail}`);
    console.log(`  DLI Validated: ${dliValidateExists ? (dliValidated ? "PASS" : "NOT PASS") : "N/A"}`);
    console.log("");

    console.log("Safety: No Huawei Cloud API write operation was executed.");
    console.log("No publish, start, run-immediate, update, or delete operation was executed.\n");

    console.log("Reports saved:");
    console.log(`  ${mdPath}`);
    console.log(`  ${jsonPath}`);

    process.exit(0);
  } catch (err) {
    console.error(`RUN-IMMEDIATE PLAN FAILED: ${err.message}`);
    process.exit(1);
  }
}

main();
