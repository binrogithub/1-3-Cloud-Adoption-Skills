const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const OUT_DIR = path.join(ROOT, "out");
const RUNS_DIR = path.join(OUT_DIR, "runs");

function parseCliArgs(argv) {
  const args = argv.slice(2);
  const parsed = {};
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--run-id" && args[i + 1]) {
      parsed.runId = args[++i];
    } else if (args[i] === "--job-name" && args[i + 1]) {
      parsed.jobName = args[++i];
    }
  }
  return parsed;
}

function readJsonSafe(filePath) {
  if (!fs.existsSync(filePath)) return null;
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf-8"));
  } catch {
    return null;
  }
}

function main() {
  const cliArgs = parseCliArgs(process.argv);
  const runId = cliArgs.runId || null;
  const jobName = cliArgs.jobName || null;

  let currentRun = null;
  let demoResult = null;

  if (runId) {
    const runDir = path.join(RUNS_DIR, runId);
    currentRun = readJsonSafe(path.join(runDir, "current_run.json"));
    demoResult = readJsonSafe(path.join(runDir, "demo_one_shot_result.json"));
  }

  if (!currentRun) {
    currentRun = readJsonSafe(path.join(OUT_DIR, "current_run.json"));
  }
  if (!demoResult) {
    demoResult = readJsonSafe(path.join(OUT_DIR, "demo_one_shot_result.json"));
  }

  if (!currentRun && !demoResult) {
    console.log("No run found.");
    process.exit(1);
  }

  const status = demoResult?.status ?? currentRun?.status ?? "UNKNOWN";
  const rid = currentRun?.run_id ?? demoResult?.run_id ?? runId ?? "N/A";
  const jn = currentRun?.job_name ?? demoResult?.job_name ?? jobName ?? "N/A";

  console.log("=== One-Shot Demo Status ===\n");
  console.log(`  Run ID:           ${rid}`);
  console.log(`  Job Name:         ${jn}`);
  console.log(`  Status:           ${status}`);

  if (currentRun) {
    console.log(`  Current Step:     ${currentRun.current_step ?? "N/A"} (${currentRun.current_step_name ?? "N/A"})`);
    if (currentRun.completed_steps?.length > 0) {
      console.log(`  Completed Steps:  ${currentRun.completed_steps.length}`);
    }
    if (currentRun.failed_step != null) {
      console.log(`  Failed Step:      ${currentRun.failed_step} (${currentRun.failed_step_name})`);
    }
  }

  if (demoResult) {
    console.log(`  Instance ID:      ${demoResult.instance_id ?? "N/A"}`);
    console.log(`  Runtime-Validate: ${demoResult.runtime_validate_status ?? "N/A"}`);
    console.log(`  Equivalence:      ${demoResult.final_equivalence ?? "N/A"}`);
    console.log(`  Stale Detected:   ${demoResult.stale_result_detected ?? false}`);
    if (demoResult.failed_command) {
      console.log(`  Failed Command:   ${demoResult.failed_command}`);
    }
  }

  console.log("");
}

main();
