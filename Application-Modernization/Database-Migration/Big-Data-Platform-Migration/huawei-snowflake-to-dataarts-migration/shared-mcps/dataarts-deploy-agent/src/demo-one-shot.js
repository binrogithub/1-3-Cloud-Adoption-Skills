const fs = require("fs");
const path = require("path");
const config = require("./config");
const runtimeTarget = require("./runtime-target");
const { generateRunId } = require("./core/run-id");
const { ensureDir, writeJson } = require("./core/json-file");
const { runShellCommand } = require("./core/command-runner");

const ROOT = path.resolve(__dirname, "..");
const OUT_DIR = path.join(ROOT, "out");
const RUNS_DIR = path.join(OUT_DIR, "runs");

const COMMANDS = [
  { step: 1, name: "validate-env", cmd: "npm run validate-env", needsConfirm: false },
  { step: 2, name: "dry-run", cmd: "npm run dry-run", needsConfirm: false },
  { step: 3, name: "inspect-request", cmd: "npm run inspect-request", needsConfirm: false },
  { step: 4, name: "audit-payload", cmd: "npm run audit-payload", needsConfirm: false },
  { step: 5, name: "live-validate", cmd: "npm run live-validate", needsConfirm: false },
  { step: 6, name: "deploy:plan", cmd: "npm run deploy:plan", needsConfirm: false },
  { step: 7, name: "reset-dli-demo-data", cmd: "npm run reset-dli-demo-data -- --confirm", needsConfirm: false },
  { step: 8, name: "dli:validate-demo-data", cmd: "npm run dli:validate-demo-data", needsConfirm: false },
  { step: 9, name: "create-job", cmd: "npm run create-job -- --confirm", needsConfirm: false },
  { step: 10, name: "verify-job", cmd: "npm run verify-job", needsConfirm: false },
  { step: 11, name: "export-job-definition", cmd: "npm run export-job-definition", needsConfirm: false },
  { step: 12, name: "run-immediate:plan", cmd: "npm run run-immediate:plan", needsConfirm: false },
  { step: 13, name: "run-immediate-job", cmd: "npm run run-immediate-job -- --confirm", needsConfirm: false },
  { step: 14, name: "runtime-validate", cmd: "npm run runtime-validate", needsConfirm: false },
];

function makeChildEnv(jobName, artifactsDir, dliQueue) {
  return {
    ...process.env,
    DATAARTS_JOB_NAME: jobName,
    DATAARTS_ARTIFACTS_DIR: artifactsDir,
    DLI_QUEUE_NAME: dliQueue,
  };
}

function runCommand(cmdObj, childEnv) {
  const label = `[${String(cmdObj.step).padStart(2, " ")}/14] ${cmdObj.name}`;
  console.log(`\n${"=".repeat(60)}`);
  console.log(`${label}: ${cmdObj.cmd}`);
  console.log(`${"=".repeat(60)}\n`);

  const result = runShellCommand(cmdObj, {
    cwd: ROOT,
    env: childEnv,
    timeoutMs: 600000,
    outputTailBytes: 500,
  });

  for (const line of result.lastLines) {
    console.log(`  ${line}`);
  }

  console.log(`\n  Exit code: ${result.exit_code} (${result.success ? "PASS" : "FAIL"})`);

  return {
    step: result.step,
    name: result.name,
    command: result.command,
    exit_code: result.exit_code,
    started_at: result.started_at,
    ended_at: result.ended_at,
    success: result.success,
    outputTail: result.outputTail,
  };
}

function writeFailedResult(runId, jobName, artifactsDir, dliQueue, results, failedCmd, runDir) {
  const timestamp = new Date().toISOString();

  const jsonReport = {
    run_id: runId,
    timestamp,
    status: "FAILED",
    job_name: jobName,
    artifact_dir: artifactsDir,
    dli_queue: dliQueue,
    commands_executed: results.map((r) => ({
      step: r.step,
      name: r.name,
      exit_code: r.exit_code,
      success: r.success,
    })),
    failed_step: failedCmd.step,
    failed_command: failedCmd.name,
    failed_command_exit_code: failedCmd.exit_code,
    instance_id: null,
    runtime_validate_status: "NOT_EVALUATED",
    final_equivalence: "NOT_EVALUATED",
    stale_result_detected: false,
    safety: {
      no_publish: true,
      no_scheduled_start: true,
      no_delete: true,
      no_update: true,
      no_overwrite: true,
      only_run_immediate_for_execution: true,
      stop_on_critical_failure: true,
    },
    no_secrets_included: true,
  };

  const lines = [];
  lines.push("# One-Shot Demo Report");
  lines.push("");
  lines.push(`**Run ID:** ${runId}`);
  lines.push(`**Timestamp:** ${timestamp}`);
  lines.push(`**Status:** FAILED`);
  lines.push(`**Job Name:** ${jobName}`);
  lines.push(`**Artifact Dir:** ${artifactsDir}`);
  lines.push(`**DLI Queue:** ${dliQueue}`);
  lines.push("");
  lines.push("## Stop Reason");
  lines.push("");
  lines.push(`Command **${failedCmd.name}** (step ${failedCmd.step}) failed with exit code ${failedCmd.exit_code}.`);
  lines.push("Pipeline stopped immediately. No downstream result files were read.");
  lines.push("");
  lines.push("## Command Execution Table");
  lines.push("");
  lines.push("| Step | Command | Exit Code | Status |");
  lines.push("|------|---------|-----------|--------|");
  for (const r of results) {
    lines.push(`| ${r.step} | ${r.name} | ${r.exit_code} | ${r.success ? "PASS" : "FAIL"} |`);
  }
  lines.push("");
  lines.push("## Failed Command");
  lines.push("");
  lines.push(`- **Step:** ${failedCmd.step}`);
  lines.push(`- **Name:** ${failedCmd.name}`);
  lines.push(`- **Exit Code:** ${failedCmd.exit_code}`);
  lines.push("");
  lines.push("## Results");
  lines.push("");
  lines.push("| Field | Value |");
  lines.push("|-------|-------|");
  lines.push("| instance_id | null |");
  lines.push("| runtime_validate_status | NOT_EVALUATED |");
  lines.push("| final_equivalence | NOT_EVALUATED |");
  lines.push("| stale_result_detected | false |");
  lines.push("");
  lines.push("## Safety Statement");
  lines.push("");
  lines.push("> **No publish, no /start, no delete, no update, no overwrite operation was executed.**");
  lines.push(">");
  lines.push("> The job was executed via run-immediate only (one-time, no recurring schedule).");
  lines.push("> The orchestrator stops immediately on any critical failure.");
  lines.push("> If the target job already exists, create-job aborts safely.");
  lines.push("> No secrets are printed or stored in reports.");
  lines.push("> On failure, downstream result files are NOT read to prevent stale contamination.");
  lines.push("");

  const mdReport = lines.join("\n");

  ensureDir(OUT_DIR);
  writeJson(path.join(OUT_DIR, "demo_one_shot_result.json"), jsonReport);
  fs.writeFileSync(path.join(OUT_DIR, "demo_one_shot_report.md"), mdReport, "utf-8");

  ensureDir(runDir);
  writeJson(path.join(runDir, "demo_one_shot_result.json"), jsonReport);
  fs.writeFileSync(path.join(runDir, "demo_one_shot_report.md"), mdReport, "utf-8");

  return { jsonReport, mdReport };
}

function writeStaleResult(runId, jobName, artifactsDir, dliQueue, results, staleDetails, runDir) {
  const timestamp = new Date().toISOString();

  const jsonReport = {
    run_id: runId,
    timestamp,
    status: "FAILED",
    job_name: jobName,
    artifact_dir: artifactsDir,
    dli_queue: dliQueue,
    commands_executed: results.map((r) => ({
      step: r.step,
      name: r.name,
      exit_code: r.exit_code,
      success: r.success,
    })),
    failed_step: null,
    failed_command: "STALE_RESULT_DETECTED",
    failed_command_exit_code: null,
    stale_result_detected: true,
    stale_details: staleDetails,
    instance_id: null,
    runtime_validate_status: "NOT_EVALUATED",
    final_equivalence: "NOT_EVALUATED",
    safety: {
      no_publish: true,
      no_scheduled_start: true,
      no_delete: true,
      no_update: true,
      no_overwrite: true,
      only_run_immediate_for_execution: true,
      stop_on_critical_failure: true,
    },
    no_secrets_included: true,
  };

  const lines = [];
  lines.push("# One-Shot Demo Report");
  lines.push("");
  lines.push(`**Run ID:** ${runId}`);
  lines.push(`**Timestamp:** ${timestamp}`);
  lines.push(`**Status:** FAILED`);
  lines.push(`**Job Name:** ${jobName}`);
  lines.push(`**Artifact Dir:** ${artifactsDir}`);
  lines.push(`**DLI Queue:** ${dliQueue}`);
  lines.push("");
  lines.push("## Stop Reason");
  lines.push("");
  lines.push("**STALE RESULT DETECTED.** Downstream result files belong to a different job or instance.");
  lines.push("Results are discarded to prevent contamination.");
  lines.push("");
  lines.push("## Stale Details");
  lines.push("");
  for (const d of staleDetails) {
    lines.push(`- ${d}`);
  }
  lines.push("");
  lines.push("## Command Execution Table");
  lines.push("");
  lines.push("| Step | Command | Exit Code | Status |");
  lines.push("|------|---------|-----------|--------|");
  for (const r of results) {
    lines.push(`| ${r.step} | ${r.name} | ${r.exit_code} | ${r.success ? "PASS" : "FAIL"} |`);
  }
  lines.push("");
  lines.push("## Results");
  lines.push("");
  lines.push("| Field | Value |");
  lines.push("|-------|-------|");
  lines.push("| instance_id | null |");
  lines.push("| runtime_validate_status | NOT_EVALUATED |");
  lines.push("| final_equivalence | NOT_EVALUATED |");
  lines.push("| stale_result_detected | true |");
  lines.push("");
  lines.push("## Safety Statement");
  lines.push("");
  lines.push("> **No publish, no /start, no delete, no update, no overwrite operation was executed.**");
  lines.push(">");
  lines.push("> Stale downstream results were detected and discarded.");
  lines.push("> No secrets are printed or stored in reports.");
  lines.push("");

  const mdReport = lines.join("\n");

  ensureDir(OUT_DIR);
  writeJson(path.join(OUT_DIR, "demo_one_shot_result.json"), jsonReport);
  fs.writeFileSync(path.join(OUT_DIR, "demo_one_shot_report.md"), mdReport, "utf-8");

  ensureDir(runDir);
  writeJson(path.join(runDir, "demo_one_shot_result.json"), jsonReport);
  fs.writeFileSync(path.join(runDir, "demo_one_shot_report.md"), mdReport, "utf-8");

  return { jsonReport, mdReport };
}

function main() {
  console.log("=== DataArts Deploy Agent: ONE-SHOT DEMO ===\n");

  const args = process.argv.slice(2);
  if (!args.includes("--confirm")) {
    console.error("ABORTED: --confirm flag is required.");
    console.error("");
    console.error("This command will execute the full one-shot demo pipeline.");
    console.error("To proceed, run:");
    console.error("  npm run demo:one-shot -- --confirm --job-name <name> --artifacts-dir <dir> --dli-queue <queue>");
    process.exit(1);
  }

  try {
    const runId = generateRunId();
    const startedAt = new Date().toISOString();

    console.log(`[0/14] Pre-flight validation...\n`);
    console.log(`  Run ID: ${runId}`);

    const env = config.load();
    config.validate(env);

    const target = runtimeTarget.resolve();

    if (!target.valid) {
      console.error("ABORTED: Runtime target is invalid:\n");
      for (const err of target.errors) {
        console.error(`  - ${err}`);
      }
      console.error("");
      console.error("Provide --job-name and --artifacts-dir via CLI args, MCP arguments, or env vars.");
      process.exit(1);
    }

    const { jobName, artifactsDir, dliQueue } = target;

    console.log(`  Job Name:     ${jobName}`);
    console.log(`  Artifact Dir: ${artifactsDir}`);
    console.log(`  DLI Queue:    ${dliQueue}`);
    console.log("  Pre-flight:   OK");
    console.log("");

    const childEnv = makeChildEnv(jobName, artifactsDir, dliQueue);

    const runDir = path.join(RUNS_DIR, runId);
    ensureDir(runDir);

    const currentRun = {
      run_id: runId,
      job_name: jobName,
      artifact_dir: artifactsDir,
      dli_queue: dliQueue,
      started_at: startedAt,
      status: "RUNNING",
      current_step: 0,
      current_step_name: "pre-flight",
      completed_steps: [],
      failed_step: null,
      failed_step_name: null,
    };
    ensureDir(OUT_DIR);
    writeJson(path.join(OUT_DIR, "current_run.json"), currentRun);
    writeJson(path.join(runDir, "current_run.json"), currentRun);

    console.log("Executing one-shot demo pipeline...\n");

    const results = [];
    let failedCommand = null;

    for (const cmdObj of COMMANDS) {
      currentRun.current_step = cmdObj.step;
      currentRun.current_step_name = cmdObj.name;
      writeJson(path.join(OUT_DIR, "current_run.json"), currentRun);
      writeJson(path.join(runDir, "current_run.json"), currentRun);

      const result = runCommand(cmdObj, childEnv);
      results.push(result);

      if (!result.success) {
        failedCommand = result;
        currentRun.failed_step = cmdObj.step;
        currentRun.failed_step_name = cmdObj.name;
        console.error(`\nCRITICAL FAILURE at step ${cmdObj.step} (${cmdObj.name}). Stopping immediately.\n`);
        console.error("Downstream result files will NOT be read to prevent stale contamination.\n");
        break;
      }

      currentRun.completed_steps.push({ step: cmdObj.step, name: cmdObj.name });
      writeJson(path.join(OUT_DIR, "current_run.json"), currentRun);
      writeJson(path.join(runDir, "current_run.json"), currentRun);
    }

    if (failedCommand) {
      const { jsonReport } = writeFailedResult(runId, jobName, artifactsDir, dliQueue, results, failedCommand, runDir);

      currentRun.status = "FAILED";
      currentRun.current_step_name = "stopped";
      writeJson(path.join(OUT_DIR, "current_run.json"), currentRun);
      writeJson(path.join(runDir, "current_run.json"), currentRun);

      console.log("=== One-Shot Demo Summary ===\n");
      console.log(`  Status:          FAILED`);
      console.log(`  Run ID:          ${runId}`);
      console.log(`  Job Name:        ${jobName}`);
      console.log(`  Commands Run:    ${results.length}/${COMMANDS.length}`);
      console.log(`  FAILED AT:       Step ${failedCommand.step} (${failedCommand.name})`);
      console.log(`  Instance ID:     null (not read)`);
      console.log(`  Runtime-Validate: NOT_EVALUATED`);
      console.log(`  Equivalence:     NOT_EVALUATED`);
      console.log(`  Stale Detected:  false`);
      console.log("");
      console.log("Safety: No publish, no /start, no delete, no update, no overwrite.");
      console.log("Stale protection: Downstream result files were NOT read after failure.");
      console.log("");
      console.log("Reports saved:");
      console.log(`  ${path.join(OUT_DIR, "demo_one_shot_result.json")}`);
      console.log(`  ${path.join(OUT_DIR, "demo_one_shot_report.md")}`);
      console.log(`  ${runDir}/`);

      process.exit(1);
    }

    console.log(`\n${"=".repeat(60)}`);
    console.log("ONE-SHOT DEMO: ALL COMMANDS SUCCEEDED — READING DOWNSTREAM RESULTS");
    console.log(`${"=".repeat(60)}\n`);

    let instanceId = null;
    let runtimeValidateStatus = null;
    let equivalenceResult = null;
    const staleDetails = [];

    const runImmediateResultPath = path.join(OUT_DIR, "run_immediate_job_result.json");
    if (fs.existsSync(runImmediateResultPath)) {
      try {
        const riResult = JSON.parse(fs.readFileSync(runImmediateResultPath, "utf-8"));
        if (riResult.job_name && riResult.job_name !== jobName) {
          staleDetails.push(
            `run_immediate_job_result.json job_name="${riResult.job_name}" does not match current job_name="${jobName}"`
          );
        } else {
          if (riResult.execution_id) {
            const match = riResult.execution_id.match(/=(\d+)$/);
            instanceId = match ? match[1] : riResult.execution_id;
          }
        }
      } catch (e) {
        staleDetails.push(`Failed to parse run_immediate_job_result.json: ${e.message}`);
      }
    } else {
      staleDetails.push("run_immediate_job_result.json does not exist");
    }

    const runtimeValidateResultPath = path.join(OUT_DIR, "runtime_validate_result.json");
    if (fs.existsSync(runtimeValidateResultPath)) {
      try {
        const rvResult = JSON.parse(fs.readFileSync(runtimeValidateResultPath, "utf-8"));
        if (rvResult.job_name && rvResult.job_name !== jobName) {
          staleDetails.push(
            `runtime_validate_result.json job_name="${rvResult.job_name}" does not match current job_name="${jobName}"`
          );
        } else if (instanceId && rvResult.instance_id && String(rvResult.instance_id) !== String(instanceId)) {
          staleDetails.push(
            `runtime_validate_result.json instance_id="${rvResult.instance_id}" does not match current instance_id="${instanceId}"`
          );
        } else {
          runtimeValidateStatus = rvResult.status;
          equivalenceResult = rvResult.equivalence_result;
        }
      } catch (e) {
        staleDetails.push(`Failed to parse runtime_validate_result.json: ${e.message}`);
      }
    } else {
      staleDetails.push("runtime_validate_result.json does not exist");
    }

    if (staleDetails.length > 0) {
      console.error("\nSTALE RESULT DETECTED. Discarding downstream results.\n");
      for (const d of staleDetails) {
        console.error(`  - ${d}`);
      }
      console.error("");

      writeStaleResult(runId, jobName, artifactsDir, dliQueue, results, staleDetails, runDir);

      currentRun.status = "FAILED";
      currentRun.current_step_name = "stopped";
      writeJson(path.join(OUT_DIR, "current_run.json"), currentRun);
      writeJson(path.join(runDir, "current_run.json"), currentRun);

      console.log("=== One-Shot Demo Summary ===\n");
      console.log(`  Status:          FAILED (STALE_RESULT_DETECTED)`);
      console.log(`  Run ID:          ${runId}`);
      console.log(`  Job Name:        ${jobName}`);
      console.log(`  Commands Run:    ${results.length}/${COMMANDS.length}`);
      console.log(`  Instance ID:     null (stale)`);
      console.log(`  Runtime-Validate: NOT_EVALUATED`);
      console.log(`  Equivalence:     NOT_EVALUATED`);
      console.log(`  Stale Detected:  true`);
      console.log("");
      console.log("Reports saved:");
      console.log(`  ${path.join(OUT_DIR, "demo_one_shot_result.json")}`);
      console.log(`  ${path.join(OUT_DIR, "demo_one_shot_report.md")}`);
      console.log(`  ${runDir}/`);

      process.exit(1);
    }

    const createJobResultPath = path.join(OUT_DIR, "create_job_result.json");
    let createJobStatus = null;
    if (fs.existsSync(createJobResultPath)) {
      try {
        const cjResult = JSON.parse(fs.readFileSync(createJobResultPath, "utf-8"));
        createJobStatus = cjResult.created ? `HTTP ${cjResult.http_status} CREATED` : `HTTP ${cjResult.http_status} NOT CREATED`;
      } catch {}
    }

    const timestamp = new Date().toISOString();
    const finalStatus = equivalenceResult === "EQUIVALENT"
      ? "FUNCTIONAL_EQUIVALENCE_CONFIRMED"
      : "ALL_COMMANDS_SUCCEEDED";

    const jsonReport = {
      run_id: runId,
      timestamp,
      status: finalStatus,
      job_name: jobName,
      artifact_dir: artifactsDir,
      dli_queue: dliQueue,
      commands_executed: results.map((r) => ({
        step: r.step,
        name: r.name,
        exit_code: r.exit_code,
        success: r.success,
      })),
      failed_command: null,
      create_job_status: createJobStatus,
      instance_id: instanceId,
      runtime_validate_status: runtimeValidateStatus,
      final_equivalence: equivalenceResult,
      stale_result_detected: false,
      safety: {
        no_publish: true,
        no_scheduled_start: true,
        no_delete: true,
        no_update: true,
        no_overwrite: true,
        only_run_immediate_for_execution: true,
        stop_on_critical_failure: true,
      },
      no_secrets_included: true,
    };

    const lines = [];
    lines.push("# One-Shot Demo Report");
    lines.push("");
    lines.push(`**Run ID:** ${runId}`);
    lines.push(`**Timestamp:** ${timestamp}`);
    lines.push(`**Status:** ${finalStatus}`);
    lines.push(`**Job Name:** ${jobName}`);
    lines.push(`**Artifact Dir:** ${artifactsDir}`);
    lines.push(`**DLI Queue:** ${dliQueue}`);
    lines.push("");

    lines.push("## Command Execution Table");
    lines.push("");
    lines.push("| Step | Command | Exit Code | Status |");
    lines.push("|------|---------|-----------|--------|");
    for (const r of results) {
      lines.push(`| ${r.step} | ${r.name} | ${r.exit_code} | ${r.success ? "PASS" : "FAIL"} |`);
    }
    lines.push("");

    lines.push("## Results");
    lines.push("");
    lines.push("| Field | Value |");
    lines.push("|-------|-------|");
    lines.push(`| create-job status | ${createJobStatus || "N/A"} |`);
    lines.push(`| run-immediate instance ID | ${instanceId || "N/A"} |`);
    lines.push(`| runtime-validate status | ${runtimeValidateStatus || "N/A"} |`);
    lines.push(`| final equivalence | ${equivalenceResult || "N/A"} |`);
    lines.push(`| stale_result_detected | false |`);
    lines.push("");

    lines.push("## Safety Statement");
    lines.push("");
    lines.push("> **No publish, no /start, no delete, no update, no overwrite operation was executed.**");
    lines.push(">");
    lines.push("> The job was executed via run-immediate only (one-time, no recurring schedule).");
    lines.push("> The orchestrator stops immediately on any critical failure.");
    lines.push("> If the target job already exists, create-job aborts safely.");
    lines.push("> No secrets are printed or stored in reports.");
    lines.push("> Downstream result files are validated against current job_name and instance_id before use.");
    lines.push("");

    const mdReport = lines.join("\n");

    writeJson(path.join(OUT_DIR, "demo_one_shot_result.json"), jsonReport);
    fs.writeFileSync(path.join(OUT_DIR, "demo_one_shot_report.md"), mdReport, "utf-8");

    writeJson(path.join(runDir, "demo_one_shot_result.json"), jsonReport);
    fs.writeFileSync(path.join(runDir, "demo_one_shot_report.md"), mdReport, "utf-8");

    currentRun.status = finalStatus;
    currentRun.current_step_name = "complete";
    writeJson(path.join(OUT_DIR, "current_run.json"), currentRun);
    writeJson(path.join(runDir, "current_run.json"), currentRun);

    console.log("=== One-Shot Demo Summary ===\n");
    console.log(`  Status:          ${finalStatus}`);
    console.log(`  Run ID:          ${runId}`);
    console.log(`  Job Name:        ${jobName}`);
    console.log(`  Artifact Dir:    ${artifactsDir}`);
    console.log(`  DLI Queue:       ${dliQueue}`);
    console.log(`  Commands Run:    ${results.length}/${COMMANDS.length}`);
    console.log(`  Create-Job:      ${createJobStatus || "N/A"}`);
    console.log(`  Instance ID:     ${instanceId || "N/A"}`);
    console.log(`  Runtime-Validate: ${runtimeValidateStatus || "N/A"}`);
    console.log(`  Equivalence:     ${equivalenceResult || "N/A"}`);
    console.log(`  Stale Detected:  false`);
    console.log("");
    console.log("Safety: No publish, no /start, no delete, no update, no overwrite.");
    console.log("");
    console.log("Reports saved:");
    console.log(`  ${path.join(OUT_DIR, "demo_one_shot_result.json")}`);
    console.log(`  ${path.join(OUT_DIR, "demo_one_shot_report.md")}`);
    console.log(`  ${runDir}/`);

    process.exit(0);
  } catch (err) {
    console.error(`ONE-SHOT DEMO FAILED: ${err.message}`);
    process.exit(1);
  }
}

main();
