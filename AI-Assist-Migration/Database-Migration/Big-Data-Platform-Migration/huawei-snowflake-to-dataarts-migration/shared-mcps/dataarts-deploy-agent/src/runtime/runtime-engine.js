const path = require("path");
const fs = require("fs");
const { buildExecutionPlan } = require("../migration/execution-plan-builder");
const { prepareRuntimeArtifacts } = require("../migration/runtime-preparer");
const { generateRunId } = require("../core/run-id");
const { ensureDir, writeJson } = require("../core/json-file");
const { buildSafetyPolicy } = require("../core/safety-policy");

function buildRuntimeCommandSequence(options = {}) {
  const { runId, jobName } = options;

  return [
    {
      step: 1,
      name: "validate-env",
      cmd: "npm run validate-env",
      category: "LOCAL_READ_ONLY",
      executed_in_dry_run: false,
    },
    {
      step: 2,
      name: "dry-run",
      cmd: "npm run dry-run",
      category: "LOCAL_READ_ONLY",
      executed_in_dry_run: false,
    },
    {
      step: 3,
      name: "inspect-request",
      cmd: "npm run inspect-request",
      category: "LOCAL_READ_ONLY",
      executed_in_dry_run: false,
    },
    {
      step: 4,
      name: "audit-payload",
      cmd: "npm run audit-payload",
      category: "LOCAL_READ_ONLY",
      executed_in_dry_run: false,
    },
    {
      step: 5,
      name: "live-validate",
      cmd: "npm run live-validate",
      category: "LOCAL_READ_ONLY",
      executed_in_dry_run: false,
    },
    {
      step: 6,
      name: "deploy-plan",
      cmd: "npm run deploy:plan",
      category: "LOCAL_READ_ONLY",
      executed_in_dry_run: false,
    },
    {
      step: 7,
      name: "reset-runtime-data",
      cmd: "npm run reset-dli-demo-data -- --confirm",
      category: "RUNTIME_CLOUD",
      executed_in_dry_run: false,
    },
    {
      step: 8,
      name: "validate-runtime-data",
      cmd: "npm run dli:validate-demo-data",
      category: "RUNTIME_CLOUD",
      executed_in_dry_run: false,
    },
    {
      step: 9,
      name: "create-job",
      cmd: "npm run create-job -- --confirm",
      category: "RUNTIME_CLOUD",
      executed_in_dry_run: false,
    },
    {
      step: 10,
      name: "verify-job",
      cmd: "npm run verify-job",
      category: "RUNTIME_CLOUD",
      executed_in_dry_run: false,
    },
    {
      step: 11,
      name: "export-job-definition",
      cmd: "npm run export-job-definition",
      category: "RUNTIME_CLOUD",
      executed_in_dry_run: false,
    },
    {
      step: 12,
      name: "run-immediate-plan",
      cmd: "npm run run-immediate:plan",
      category: "LOCAL_READ_ONLY",
      executed_in_dry_run: false,
    },
    {
      step: 13,
      name: "run-immediate",
      cmd: "npm run run-immediate-job -- --confirm",
      category: "RUNTIME_CLOUD",
      executed_in_dry_run: false,
    },
    {
      step: 14,
      name: "runtime-validate",
      cmd: "npm run runtime-validate",
      category: "RUNTIME_CLOUD",
      executed_in_dry_run: false,
    },
    {
      step: 15,
      name: "execution-doctor",
      cmd: `npm run demo:one-shot:doctor -- --run-id ${runId} --job-name ${jobName}`,
      category: "LOCAL_READ_ONLY",
      executed_in_dry_run: false,
    },
    {
      step: 16,
      name: "equivalence-summary",
      cmd: `npm run demo:equivalence-summary -- --run-id ${runId} --job-name ${jobName}`,
      category: "LOCAL_READ_ONLY",
      executed_in_dry_run: false,
    },
  ];
}

function runRuntimeEngine(options = {}) {
  const errors = [];
  const warnings = [];

  const { packageDir, jobName, mode } = options;
  const dliQueue = options.dliQueue || "default";

  if (!packageDir) {
    return {
      status: "INVALID_INPUT",
      valid: false,
      mode: mode || null,
      run_id: null,
      migration_id: null,
      package_dir: null,
      job_name: jobName || null,
      dli_queue: dliQueue,
      runtime_artifacts_dir: null,
      runtime_nodes_dir: null,
      command_sequence: [],
      env_overrides: {},
      safety: buildSafetyPolicy({
        dry_run: true,
        no_commands_executed: true,
        no_api_write_calls: true,
        no_runtime_execution: true,
        local_evidence_only: true,
      }),
      warnings: [],
      errors: ["packageDir is required"],
    };
  }

  if (!jobName) {
    return {
      status: "INVALID_INPUT",
      valid: false,
      mode: mode || null,
      run_id: null,
      migration_id: null,
      package_dir: path.resolve(packageDir),
      job_name: null,
      dli_queue: dliQueue,
      runtime_artifacts_dir: null,
      runtime_nodes_dir: null,
      command_sequence: [],
      env_overrides: {},
      safety: buildSafetyPolicy({
        dry_run: true,
        no_commands_executed: true,
        no_api_write_calls: true,
        no_runtime_execution: true,
        local_evidence_only: true,
      }),
      warnings: [],
      errors: ["jobName is required"],
    };
  }

  if (mode !== "DRY_RUN") {
    return {
      status: "UNSUPPORTED_MODE",
      valid: false,
      mode: mode || null,
      run_id: null,
      migration_id: null,
      package_dir: path.resolve(packageDir),
      job_name: jobName,
      dli_queue: dliQueue,
      runtime_artifacts_dir: null,
      runtime_nodes_dir: null,
      command_sequence: [],
      env_overrides: {},
      safety: buildSafetyPolicy({
        dry_run: true,
        no_commands_executed: true,
        no_api_write_calls: true,
        no_runtime_execution: true,
        local_evidence_only: true,
      }),
      warnings: [],
      errors: [`Unsupported mode: ${mode}. Only DRY_RUN is supported.`],
    };
  }

  const execPlanOpts = { packageDir };
  if (options.outDir) {
    execPlanOpts.outDir = options.outDir;
  }

  const execPlan = buildExecutionPlan(execPlanOpts);

  if (!execPlan.valid) {
    return {
      status: "EXECUTION_PLAN_INVALID",
      valid: false,
      mode,
      run_id: null,
      migration_id: execPlan.migration_id,
      package_dir: execPlan.package_dir,
      job_name: jobName,
      dli_queue: dliQueue,
      runtime_artifacts_dir: execPlan.runtime_artifacts_dir,
      runtime_nodes_dir: execPlan.runtime_nodes_dir,
      command_sequence: [],
      env_overrides: {},
      safety: buildSafetyPolicy({
        dry_run: true,
        no_commands_executed: true,
        no_api_write_calls: true,
        no_runtime_execution: true,
        local_evidence_only: true,
      }),
      warnings: execPlan.warnings,
      errors: execPlan.errors,
    };
  }

  const preparerOpts = { packageDir };
  if (options.outDir) {
    preparerOpts.outDir = options.outDir;
  }

  const prepared = prepareRuntimeArtifacts(preparerOpts);

  if (!prepared.valid) {
    return {
      status: "PREPARATION_FAILED",
      valid: false,
      mode,
      run_id: null,
      migration_id: prepared.migration_id,
      package_dir: prepared.package_dir,
      job_name: jobName,
      dli_queue: dliQueue,
      runtime_artifacts_dir: prepared.runtime_artifacts_dir,
      runtime_nodes_dir: prepared.runtime_nodes_dir,
      command_sequence: [],
      env_overrides: {},
      safety: buildSafetyPolicy({
        dry_run: true,
        no_commands_executed: true,
        no_api_write_calls: true,
        no_runtime_execution: true,
        local_evidence_only: true,
      }),
      warnings: prepared.warnings,
      errors: prepared.errors,
    };
  }

  const runId = generateRunId();

  const runtimeArtifactsDir = prepared.runtime_artifacts_dir;
  const runtimeNodesDir = prepared.runtime_nodes_dir;
  const migrationId = execPlan.migration_id;

  const envOverrides = {
    DATAARTS_JOB_NAME: jobName,
    DATAARTS_ARTIFACTS_DIR: runtimeArtifactsDir,
    DLI_QUEUE_NAME: dliQueue,
  };

  const commandSequence = buildRuntimeCommandSequence({
    runId,
    jobName,
  });

  const safety = buildSafetyPolicy({
    dry_run: true,
    no_commands_executed: true,
    no_api_write_calls: true,
    no_runtime_execution: true,
    local_evidence_only: true,
  });

  const result = {
    status: "RUNTIME_ENGINE_DRY_RUN_READY",
    valid: true,
    mode,
    run_id: runId,
    migration_id: migrationId,
    package_dir: execPlan.package_dir,
    job_name: jobName,
    dli_queue: dliQueue,
    runtime_artifacts_dir: runtimeArtifactsDir,
    runtime_nodes_dir: runtimeNodesDir,
    command_sequence: commandSequence,
    env_overrides: envOverrides,
    safety,
    warnings: execPlan.warnings.concat(prepared.warnings),
    errors: [],
  };

  writeEvidenceFiles(result, options);

  return result;
}

function writeEvidenceFiles(result, options = {}) {
  const baseOutDir = options.outDir
    ? path.resolve(options.outDir)
    : path.resolve("out");

  ensureDir(baseOutDir);

  writeJson(
    path.join(baseOutDir, "runtime_engine_dry_run_result.json"),
    result
  );

  const report = renderMarkdownReport(result);
  fs.writeFileSync(
    path.join(baseOutDir, "runtime_engine_dry_run_report.md"),
    report,
    "utf-8"
  );

  const runDir = path.join(baseOutDir, "runs", result.run_id);
  ensureDir(runDir);

  writeJson(
    path.join(runDir, "runtime_engine_dry_run_result.json"),
    result
  );

  fs.writeFileSync(
    path.join(runDir, "runtime_engine_dry_run_report.md"),
    report,
    "utf-8"
  );

  const currentRun = {
    run_id: result.run_id,
    migration_id: result.migration_id,
    job_name: result.job_name,
    artifact_dir: result.runtime_artifacts_dir,
    dli_queue: result.dli_queue,
    status: "DRY_RUN_READY",
    current_step: 0,
    current_step_name: "dry-run",
    completed_steps: [],
    failed_step: null,
    failed_step_name: null,
  };

  writeJson(path.join(runDir, "current_run.json"), currentRun);
}

function renderMarkdownReport(result) {
  const lines = [];

  lines.push("# Runtime Engine Dry-Run Report");
  lines.push("");
  lines.push(`**Status:** ${result.status}`);
  lines.push(`**Valid:** ${result.valid ? "YES" : "NO"}`);
  lines.push(`**Mode:** ${result.mode || "N/A"}`);
  lines.push(`**Run ID:** ${result.run_id || "N/A"}`);
  lines.push(`**Migration ID:** ${result.migration_id || "N/A"}`);
  lines.push(`**Job Name:** ${result.job_name || "N/A"}`);
  lines.push(`**DLI Queue:** ${result.dli_queue || "N/A"}`);
  lines.push("");

  lines.push("## Runtime Directories");
  lines.push("");
  lines.push(`- Artifacts: \`${result.runtime_artifacts_dir || "N/A"}\``);
  lines.push(`- Nodes: \`${result.runtime_nodes_dir || "N/A"}\``);
  lines.push("");

  lines.push("## Environment Overrides");
  lines.push("");
  for (const [key, value] of Object.entries(result.env_overrides || {})) {
    lines.push(`- ${key}=${value}`);
  }
  lines.push("");

  lines.push("## Command Sequence");
  lines.push("");
  lines.push("| Step | Name | Category | Command | Executed in Dry-Run |");
  lines.push("|------|------|----------|---------|---------------------|");
  for (const cmd of result.command_sequence) {
    lines.push(
      `| ${cmd.step} | ${cmd.name} | ${cmd.category} | \`${cmd.cmd}\` | ${cmd.executed_in_dry_run ? "YES" : "NO"} |`
    );
  }
  lines.push("");

  if (result.warnings.length > 0) {
    lines.push("## Warnings");
    lines.push("");
    for (const w of result.warnings) {
      lines.push(`- ${w}`);
    }
    lines.push("");
  }

  if (result.errors.length > 0) {
    lines.push("## Errors");
    lines.push("");
    for (const e of result.errors) {
      lines.push(`- ${e}`);
    }
    lines.push("");
  }

  lines.push("## Safety");
  lines.push("");
  lines.push("- Dry-run only");
  lines.push("- No commands executed");
  lines.push("- No API write calls");
  lines.push("- No runtime execution");
  lines.push("- Local evidence only");
  lines.push("");

  return lines.join("\n");
}

module.exports = {
  buildRuntimeCommandSequence,
  runRuntimeEngine,
  renderMarkdownReport,
};
