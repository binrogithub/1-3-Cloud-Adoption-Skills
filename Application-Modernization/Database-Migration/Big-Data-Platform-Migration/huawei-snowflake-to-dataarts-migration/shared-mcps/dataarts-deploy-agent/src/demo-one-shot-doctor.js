const fs = require("fs");
const path = require("path");
const dotenv = require("dotenv");

const ROOT = path.resolve(__dirname, "..");
const OUT_DIR = path.join(ROOT, "out");
const ENV_FILE = path.join(ROOT, ".env.dataarts");

function parseCliArgs(argv) {
  const args = argv.slice(2);
  const parsed = {};
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--job-name" && args[i + 1]) {
      parsed.jobName = args[++i];
    }
    if (args[i] === "--run-id" && args[i + 1]) {
      parsed.runId = args[++i];
    }
  }
  return parsed;
}

function readJsonSafe(filePath) {
  if (!fs.existsSync(filePath)) return null;
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf-8"));
  } catch (e) {
    return { _parse_error: e.message };
  }
}

function readEnvSafe() {
  if (!fs.existsSync(ENV_FILE)) return null;
  try {
    const result = dotenv.config({ path: ENV_FILE });
    return result.parsed || null;
  } catch {
    return null;
  }
}

function resolveInstanceId(executionId) {
  if (!executionId) return null;
  const match = executionId.match(/=(\d+)$/);
  return match ? match[1] : executionId;
}

function runDoctorRunIdMode(cliArgs, envParsed) {
  const runId = cliArgs.runId;
  const runDir = path.join(OUT_DIR, "runs", runId);

  const findings = [];
  const warnings = [];
  const info = [];

  const envJobName = envParsed?.DATAARTS_JOB_NAME ?? null;
  const currentArtifactsDir = envParsed?.DATAARTS_ARTIFACTS_DIR ?? null;
  const currentDliQueue = envParsed?.DLI_QUEUE_NAME ?? null;
  const requestedJobName = cliArgs.jobName || envJobName || null;

  info.push(`Mode: run_id-based (--run-id "${runId}")`);
  info.push(`Requested run_id = "${runId}"`);
  info.push(`Requested job_name = "${requestedJobName}" (source: ${cliArgs.jobName ? "--job-name CLI" : envJobName ? ".env.dataarts" : "none"})`);
  info.push(`Current .env.dataarts DATAARTS_JOB_NAME = "${envJobName}"`);
  info.push(`Current .env.dataarts DATAARTS_ARTIFACTS_DIR = "${currentArtifactsDir}"`);
  info.push(`Current .env.dataarts DLI_QUEUE_NAME = "${currentDliQueue}"`);

  if (!fs.existsSync(runDir)) {
    findings.push(`CRITICAL: Run directory not found: ${runDir}`);
    return { findings, warnings, info, isHealthy: false };
  }

  const currentRun = readJsonSafe(path.join(runDir, "current_run.json"));
  if (!currentRun) {
    findings.push(`CRITICAL: current_run.json not found in run directory: ${runDir}`);
    return { findings, warnings, info, isHealthy: false };
  }

  info.push(`Run current_run.json: run_id="${currentRun.run_id}", status="${currentRun.status}", job_name="${currentRun.job_name}"`);

  if (currentRun.run_id !== runId) {
    findings.push(`MISMATCH: current_run.json run_id="${currentRun.run_id}" does not match provided run_id="${runId}"`);
  }

  if (requestedJobName && currentRun.job_name && currentRun.job_name !== requestedJobName) {
    findings.push(`MISMATCH: current_run.json job_name="${currentRun.job_name}" does not match requested job_name="${requestedJobName}"`);
  }

  const demoResultRun = readJsonSafe(path.join(runDir, "demo_one_shot_result.json"));
  const demoResultGeneric = readJsonSafe(path.join(OUT_DIR, "demo_one_shot_result.json"));
  const demoResult = demoResultRun || demoResultGeneric;
  const demoResultSource = demoResultRun ? "run-specific" : demoResultGeneric ? "generic-fallback" : null;

  const runImmediateResultRun = readJsonSafe(path.join(runDir, "run_immediate_job_result.json"));
  const runImmediateResultGeneric = readJsonSafe(path.join(OUT_DIR, "run_immediate_job_result.json"));
  const runImmediateResult = runImmediateResultRun || runImmediateResultGeneric;
  const runImmediateSource = runImmediateResultRun ? "run-specific" : runImmediateResultGeneric ? "generic-fallback" : null;

  const runtimeValidateResultRun = readJsonSafe(path.join(runDir, "runtime_validate_result.json"));
  const runtimeValidateResultGeneric = readJsonSafe(path.join(OUT_DIR, "runtime_validate_result.json"));
  const runtimeValidateResult = runtimeValidateResultRun || runtimeValidateResultGeneric;
  const runtimeValidateSource = runtimeValidateResultRun ? "run-specific" : runtimeValidateResultGeneric ? "generic-fallback" : null;

  if (demoResult) {
    info.push(`demo_one_shot_result.json (${demoResultSource}): status="${demoResult.status}", job_name="${demoResult.job_name}", run_id="${demoResult.run_id ?? "N/A"}"`);
  } else {
    warnings.push("demo_one_shot_result.json not found (run-specific or generic)");
  }

  if (runImmediateResult) {
    info.push(`run_immediate_job_result.json (${runImmediateSource}): job_name="${runImmediateResult.job_name}", execution_id="${runImmediateResult.execution_id}"`);
  } else {
    warnings.push("run_immediate_job_result.json not found (run-specific or generic)");
  }

  if (runtimeValidateResult) {
    info.push(`runtime_validate_result.json (${runtimeValidateSource}): job_name="${runtimeValidateResult.job_name}", instance_id="${runtimeValidateResult.instance_id}", equivalence="${runtimeValidateResult.equivalence_result}"`);
  } else {
    warnings.push("runtime_validate_result.json not found (run-specific or generic)");
  }

  if (!requestedJobName) {
    findings.push("CRITICAL: No job_name provided. Use --job-name <name> or set DATAARTS_JOB_NAME in .env.dataarts.");
  }

  if (demoResultRun && requestedJobName && demoResultRun.job_name && demoResultRun.job_name !== requestedJobName) {
    findings.push(`STALE: run-specific demo_one_shot_result.json job_name="${demoResultRun.job_name}" does not match requested job_name="${requestedJobName}"`);
  }

  if (runImmediateResultRun && requestedJobName && runImmediateResultRun.job_name && runImmediateResultRun.job_name !== requestedJobName) {
    findings.push(`STALE: run-specific run_immediate_job_result.json job_name="${runImmediateResultRun.job_name}" does not match requested job_name="${requestedJobName}"`);
  }

  if (runtimeValidateResultRun && requestedJobName && runtimeValidateResultRun.job_name && runtimeValidateResultRun.job_name !== requestedJobName) {
    findings.push(`STALE: run-specific runtime_validate_result.json job_name="${runtimeValidateResultRun.job_name}" does not match requested job_name="${requestedJobName}"`);
  }

  const riInstanceId = runImmediateResult ? resolveInstanceId(runImmediateResult.execution_id) : null;
  const rvInstanceId = runtimeValidateResult?.instance_id ?? null;

  if (riInstanceId && rvInstanceId && String(riInstanceId) !== String(rvInstanceId)) {
    findings.push(`MISMATCH: run_immediate instance_id="${riInstanceId}" vs runtime_validate instance_id="${rvInstanceId}"`);
  }

  const effectiveInstanceId = rvInstanceId || riInstanceId || null;
  const effectiveEquivalence = runtimeValidateResult?.equivalence_result ?? null;
  const effectiveRvStatus = runtimeValidateResult?.status ?? null;

  if (effectiveEquivalence === "EQUIVALENT" && effectiveRvStatus && effectiveRvStatus !== "PASS") {
    findings.push(`IMPOSSIBLE_STATE: final_equivalence="EQUIVALENT" but runtime_validate_status="${effectiveRvStatus}". EQUIVALENT requires runtime_validate_status=PASS.`);
  }

  if (demoResultRun?.failed_command) {
    findings.push(`FAILED_COMMAND: run-specific demo_one_shot_result.json has failed_command="${demoResultRun.failed_command}"`);
  }

  if (demoResultRun?.status && (demoResultRun.status.startsWith("FAILED") || demoResultRun.status === "FAILED")) {
    if (demoResultRun.final_equivalence === "EQUIVALENT") {
      findings.push(`IMPOSSIBLE_STATE: run-specific demo result status="${demoResultRun.status}" but final_equivalence="EQUIVALENT". A failed run cannot be EQUIVALENT.`);
    }
    if (demoResultRun.runtime_validate_status === "PASS") {
      findings.push(`IMPOSSIBLE_STATE: run-specific demo result status="${demoResultRun.status}" but runtime_validate_status="PASS". A failed run should not have PASS.`);
    }
  }

  const isHealthy = findings.length === 0;

  return {
    findings,
    warnings,
    info,
    isHealthy,
    currentRun,
    demoResult,
    demoResultSource,
    runImmediateResult,
    runImmediateSource,
    runtimeValidateResult,
    runtimeValidateSource,
    effectiveInstanceId,
    effectiveEquivalence,
    effectiveRvStatus,
    requestedJobName,
    envJobName,
    currentArtifactsDir,
    currentDliQueue,
    runId,
  };
}

function runDoctorGenericMode(cliArgs, envParsed) {
  const findings = [];
  const warnings = [];
  const info = [];

  const envJobName = envParsed?.DATAARTS_JOB_NAME ?? null;
  const currentArtifactsDir = envParsed?.DATAARTS_ARTIFACTS_DIR ?? null;
  const currentDliQueue = envParsed?.DLI_QUEUE_NAME ?? null;
  const requestedJobName = cliArgs.jobName || envJobName || null;

  info.push(`Mode: generic (no --run-id)`);
  info.push(`Requested job_name = "${requestedJobName}" (source: ${cliArgs.jobName ? "--job-name CLI" : envJobName ? ".env.dataarts" : "none"})`);
  info.push(`Current .env.dataarts DATAARTS_JOB_NAME = "${envJobName}"`);
  info.push(`Current .env.dataarts DATAARTS_ARTIFACTS_DIR = "${currentArtifactsDir}"`);
  info.push(`Current .env.dataarts DLI_QUEUE_NAME = "${currentDliQueue}"`);

  const currentRun = readJsonSafe(path.join(OUT_DIR, "current_run.json"));
  const demoResult = readJsonSafe(path.join(OUT_DIR, "demo_one_shot_result.json"));
  const runImmediateResult = readJsonSafe(path.join(OUT_DIR, "run_immediate_job_result.json"));
  const runtimeValidateResult = readJsonSafe(path.join(OUT_DIR, "runtime_validate_result.json"));

  if (currentRun) {
    info.push(`out/current_run.json exists: run_id="${currentRun.run_id}", status="${currentRun.status}", job_name="${currentRun.job_name}"`);
  } else {
    warnings.push("out/current_run.json does not exist (no current run tracked)");
  }

  if (demoResult) {
    info.push(`out/demo_one_shot_result.json: status="${demoResult.status}", job_name="${demoResult.job_name}"`);
  } else {
    warnings.push("out/demo_one_shot_result.json does not exist");
  }

  if (runImmediateResult) {
    info.push(`out/run_immediate_job_result.json: job_name="${runImmediateResult.job_name}", execution_id="${runImmediateResult.execution_id}"`);
  } else {
    warnings.push("out/run_immediate_job_result.json does not exist");
  }

  if (runtimeValidateResult) {
    info.push(`out/runtime_validate_result.json: job_name="${runtimeValidateResult.job_name}", instance_id="${runtimeValidateResult.instance_id}", equivalence="${runtimeValidateResult.equivalence_result}"`);
  } else {
    warnings.push("out/runtime_validate_result.json does not exist");
  }

  if (!requestedJobName) {
    findings.push("CRITICAL: No job_name provided. Use --job-name <name> or set DATAARTS_JOB_NAME in .env.dataarts.");
  }

  if (requestedJobName && demoResult?.job_name && demoResult.job_name !== requestedJobName) {
    findings.push(
      `STALE: demo_one_shot_result.json job_name="${demoResult.job_name}" does not match requested job_name="${requestedJobName}"`
    );
  }

  if (requestedJobName && runImmediateResult?.job_name && runImmediateResult.job_name !== requestedJobName) {
    findings.push(
      `STALE: run_immediate_job_result.json job_name="${runImmediateResult.job_name}" does not match requested job_name="${requestedJobName}"`
    );
  }

  if (requestedJobName && runtimeValidateResult?.job_name && runtimeValidateResult.job_name !== requestedJobName) {
    findings.push(
      `STALE: runtime_validate_result.json job_name="${runtimeValidateResult.job_name}" does not match requested job_name="${requestedJobName}"`
    );
  }

  if (demoResult?.job_name && runImmediateResult?.job_name && demoResult.job_name !== runImmediateResult.job_name) {
    findings.push(
      `MISMATCH: demo result job_name="${demoResult.job_name}" vs run-immediate job_name="${runImmediateResult.job_name}"`
    );
  }

  if (demoResult?.job_name && runtimeValidateResult?.job_name && demoResult.job_name !== runtimeValidateResult.job_name) {
    findings.push(
      `MISMATCH: demo result job_name="${demoResult.job_name}" vs runtime-validate job_name="${runtimeValidateResult.job_name}"`
    );
  }

  if (demoResult?.instance_id && runImmediateResult?.execution_id) {
    const riInstanceId = resolveInstanceId(runImmediateResult.execution_id);
    if (String(demoResult.instance_id) !== String(riInstanceId)) {
      findings.push(
        `MISMATCH: demo result instance_id="${demoResult.instance_id}" vs run-immediate execution_id instance="${riInstanceId}"`
      );
    }
  }

  if (demoResult?.instance_id && runtimeValidateResult?.instance_id) {
    if (String(demoResult.instance_id) !== String(runtimeValidateResult.instance_id)) {
      findings.push(
        `MISMATCH: demo result instance_id="${demoResult.instance_id}" vs runtime-validate instance_id="${runtimeValidateResult.instance_id}"`
      );
    }
  }

  if (demoResult?.status && (demoResult.status.startsWith("FAILED") || demoResult.status === "FAILED")) {
    if (demoResult.final_equivalence === "EQUIVALENT") {
      findings.push(
        `IMPOSSIBLE_STATE: demo result status="${demoResult.status}" but final_equivalence="EQUIVALENT". A failed run cannot be EQUIVALENT.`
      );
    }
    if (demoResult.runtime_validate_status === "PASS") {
      findings.push(
        `IMPOSSIBLE_STATE: demo result status="${demoResult.status}" but runtime_validate_status="PASS". A failed run should not have PASS.`
      );
    }
  }

  if (demoResult?.failed_command && demoResult.final_equivalence === "EQUIVALENT") {
    findings.push(
      `IMPOSSIBLE_STATE: failed_command is present ("${demoResult.failed_command}") but final_equivalence="EQUIVALENT".`
    );
  }

  if (demoResult?.failed_command && demoResult.runtime_validate_status === "PASS") {
    findings.push(
      `IMPOSSIBLE_STATE: failed_command is present ("${demoResult.failed_command}") but runtime_validate_status="PASS".`
    );
  }

  const isHealthy = findings.length === 0;

  const effectiveInstanceId = runtimeValidateResult?.instance_id ?? demoResult?.instance_id ?? null;
  const effectiveEquivalence = runtimeValidateResult?.equivalence_result ?? demoResult?.final_equivalence ?? null;
  const effectiveRvStatus = runtimeValidateResult?.status ?? demoResult?.runtime_validate_status ?? null;

  return {
    findings,
    warnings,
    info,
    isHealthy,
    currentRun,
    demoResult,
    demoResultSource: "generic",
    runImmediateResult,
    runImmediateSource: "generic",
    runtimeValidateResult,
    runtimeValidateSource: "generic",
    effectiveInstanceId,
    effectiveEquivalence,
    effectiveRvStatus,
    requestedJobName,
    envJobName,
    currentArtifactsDir,
    currentDliQueue,
    runId: null,
  };
}

function main() {
  console.log("=== DataArts Deploy Agent: ONE-SHOT DOCTOR ===\n");

  const cliArgs = parseCliArgs(process.argv);
  const envParsed = readEnvSafe();

  const result = cliArgs.runId
    ? runDoctorRunIdMode(cliArgs, envParsed)
    : runDoctorGenericMode(cliArgs, envParsed);

  const {
    findings,
    warnings,
    info,
    isHealthy,
    currentRun,
    demoResult,
    demoResultSource,
    runImmediateResult,
    runImmediateSource,
    runtimeValidateResult,
    runtimeValidateSource,
    effectiveInstanceId,
    effectiveEquivalence,
    effectiveRvStatus,
    requestedJobName,
    envJobName,
    currentArtifactsDir,
    currentDliQueue,
    runId,
  } = result;

  const timestamp = new Date().toISOString();

  const doctorResult = {
    timestamp,
    healthy: isHealthy,
    mode: runId ? "run_id" : "generic",
    run_id: runId || null,
    requested_job_name: requestedJobName,
    current_env: {
      job_name: envJobName,
      artifact_dir: currentArtifactsDir,
      dli_queue: currentDliQueue,
    },
    effective_result: {
      instance_id: effectiveInstanceId,
      final_equivalence: effectiveEquivalence,
      runtime_validate_status: effectiveRvStatus,
    },
    demo_result_summary: demoResult ? {
      source: demoResultSource,
      status: demoResult.status,
      job_name: demoResult.job_name,
      instance_id: demoResult.instance_id,
      runtime_validate_status: demoResult.runtime_validate_status,
      final_equivalence: demoResult.final_equivalence,
      failed_command: demoResult.failed_command || null,
      stale_result_detected: demoResult.stale_result_detected ?? null,
      run_id: demoResult.run_id ?? null,
    } : null,
    run_immediate_summary: runImmediateResult ? {
      source: runImmediateSource,
      job_name: runImmediateResult.job_name,
      execution_id: runImmediateResult.execution_id,
    } : null,
    runtime_validate_summary: runtimeValidateResult ? {
      source: runtimeValidateSource,
      job_name: runtimeValidateResult.job_name,
      instance_id: runtimeValidateResult.instance_id,
      equivalence_result: runtimeValidateResult.equivalence_result,
      status: runtimeValidateResult.status,
    } : null,
    current_run_summary: currentRun ? {
      run_id: currentRun.run_id,
      job_name: currentRun.job_name,
      status: currentRun.status,
      started_at: currentRun.started_at,
    } : null,
    findings,
    warnings,
    info,
  };

  const lines = [];
  lines.push("# One-Shot Demo Doctor Report");
  lines.push("");
  lines.push(`**Timestamp:** ${timestamp}`);
  lines.push(`**Healthy:** ${isHealthy ? "YES" : "NO"}`);
  lines.push(`**Mode:** ${runId ? "run_id" : "generic"}`);
  if (runId) {
    lines.push(`**Run ID:** ${runId}`);
  }
  lines.push(`**Requested Job Name:** ${requestedJobName || "(none)"}`);
  lines.push(`**Instance ID:** ${effectiveInstanceId || "N/A"}`);
  lines.push(`**Final Equivalence:** ${effectiveEquivalence || "N/A"}`);
  lines.push(`**Runtime Validate Status:** ${effectiveRvStatus || "N/A"}`);
  lines.push("");

  lines.push("## Current Environment");
  lines.push("");
  lines.push(`- Requested job_name = \`${requestedJobName}\``);
  lines.push(`- DATAARTS_JOB_NAME = \`${envJobName}\``);
  lines.push(`- DATAARTS_ARTIFACTS_DIR = \`${currentArtifactsDir}\``);
  lines.push(`- DLI_QUEUE_NAME = \`${currentDliQueue}\``);
  lines.push("");

  lines.push("## Result File Summaries");
  lines.push("");

  if (demoResult) {
    lines.push(`### demo_one_shot_result.json (${demoResultSource})`);
    lines.push("");
    lines.push(`- status: \`${demoResult.status}\``);
    lines.push(`- job_name: \`${demoResult.job_name}\``);
    lines.push(`- instance_id: \`${demoResult.instance_id}\``);
    lines.push(`- runtime_validate_status: \`${demoResult.runtime_validate_status}\``);
    lines.push(`- final_equivalence: \`${demoResult.final_equivalence}\``);
    lines.push(`- failed_command: \`${demoResult.failed_command || "none"}\``);
    lines.push(`- stale_result_detected: \`${demoResult.stale_result_detected ?? "N/A"}\``);
    lines.push("");
  }

  if (runImmediateResult) {
    lines.push(`### run_immediate_job_result.json (${runImmediateSource})`);
    lines.push("");
    lines.push(`- job_name: \`${runImmediateResult.job_name}\``);
    lines.push(`- execution_id: \`${runImmediateResult.execution_id}\``);
    lines.push("");
  }

  if (runtimeValidateResult) {
    lines.push(`### runtime_validate_result.json (${runtimeValidateSource})`);
    lines.push("");
    lines.push(`- job_name: \`${runtimeValidateResult.job_name}\``);
    lines.push(`- instance_id: \`${runtimeValidateResult.instance_id}\``);
    lines.push(`- equivalence_result: \`${runtimeValidateResult.equivalence_result}\``);
    lines.push(`- status: \`${runtimeValidateResult.status}\``);
    lines.push("");
  }

  if (currentRun) {
    lines.push("### current_run.json");
    lines.push("");
    lines.push(`- run_id: \`${currentRun.run_id}\``);
    lines.push(`- job_name: \`${currentRun.job_name}\``);
    lines.push(`- status: \`${currentRun.status}\``);
    lines.push(`- started_at: \`${currentRun.started_at}\``);
    lines.push("");
  }

  if (findings.length > 0) {
    lines.push("## Findings (Issues Detected)");
    lines.push("");
    for (const f of findings) {
      lines.push(`- **${f}**`);
    }
    lines.push("");
  } else {
    lines.push("## Findings");
    lines.push("");
    lines.push("No issues detected.");
    lines.push("");
  }

  if (warnings.length > 0) {
    lines.push("## Warnings");
    lines.push("");
    for (const w of warnings) {
      lines.push(`- ${w}`);
    }
    lines.push("");
  }

  lines.push("## Info");
  lines.push("");
  for (const i of info) {
    lines.push(`- ${i}`);
  }
  lines.push("");

  if (!isHealthy) {
    lines.push("## Recommended Next Step");
    lines.push("");
    if (runId) {
      lines.push("1. Fix the root cause of the finding(s) above.");
      lines.push("2. Re-run: `npm run demo:one-shot -- --confirm --job-name <name> --artifacts-dir <dir> --dli-queue <queue>`");
      lines.push("3. The orchestrator will generate a fresh run_id and validate all downstream results.");
    } else {
      lines.push("1. Fix the root cause of the failure (e.g., reset-dli-demo-data).");
      lines.push("2. Re-run: `npm run demo:one-shot -- --confirm --job-name <name> --artifacts-dir <dir> --dli-queue <queue>`");
      lines.push("3. The orchestrator will generate a fresh run_id and validate all downstream results.");
    }
    lines.push("");
  }

  const mdReport = lines.join("\n");

  if (!fs.existsSync(OUT_DIR)) {
    fs.mkdirSync(OUT_DIR, { recursive: true });
  }

  const mdPath = path.join(OUT_DIR, "demo_one_shot_doctor_report.md");
  const jsonPath = path.join(OUT_DIR, "demo_one_shot_doctor_result.json");

  fs.writeFileSync(mdPath, mdReport, "utf-8");
  fs.writeFileSync(jsonPath, JSON.stringify(doctorResult, null, 2), "utf-8");

  console.log("=== Doctor Summary ===\n");
  console.log(`  Healthy:  ${isHealthy ? "YES" : "NO"}`);
  console.log(`  Findings: ${findings.length}`);
  console.log(`  Warnings: ${warnings.length}`);
  if (effectiveInstanceId) {
    console.log(`  Instance ID: ${effectiveInstanceId}`);
  }
  if (effectiveEquivalence) {
    console.log(`  Final Equivalence: ${effectiveEquivalence}`);
  }
  console.log("");

  if (findings.length > 0) {
    console.log("Findings:");
    for (const f of findings) {
      console.log(`  - ${f}`);
    }
    console.log("");
  }

  if (warnings.length > 0) {
    console.log("Warnings:");
    for (const w of warnings) {
      console.log(`  - ${w}`);
    }
    console.log("");
  }

  console.log("Reports saved:");
  console.log(`  ${mdPath}`);
  console.log(`  ${jsonPath}`);

  process.exit(isHealthy ? 0 : 1);
}

main();
