const path = require("path");
const { runRuntimeEngine } = require("../runtime-engine");
const { prepareRuntimeArtifacts } = require("../../migration/runtime-preparer");
const { buildExecutionPlan } = require("../../migration/execution-plan-builder");
const { generateRunId } = require("../../core/run-id");
const { buildSafetyPolicy } = require("../../core/safety-policy");
const { runKooCliDoctor } = require("../../koocli/koocli-doctor");
const { buildKooCliFutureCommandPlan } = require("../../koocli/koocli-client");
const { buildNativeRuntimePlan, flattenNativePlanSteps } = require("../native-runtime-plan");
const { simulateNativeDliExecution } = require("../native-dli-simulator");
const { executeNativeDliPlan } = require("../native-dli-executor");
const { createMockDliClient } = require("../dli/mock-dli-client");
const { loadRuntimePackageArtifacts } = require("../runtime-package-loader");
const { loadMigrationPackage } = require("../../migration/package-loader");

const SUPPORTED_ADAPTERS = ["runtime-engine", "legacy-demo", "koocli", "native-dli"];
const SUPPORTED_MODES = ["DRY_RUN", "CONFIRM", "SIMULATE", "MOCK"];
const CONFIRM_SUPPORTED_ADAPTERS = ["legacy-demo"];
const SIMULATE_SUPPORTED_ADAPTERS = ["native-dli"];
const MOCK_SUPPORTED_ADAPTERS = ["native-dli"];

function resolveRuntimeAdapter(options = {}) {
  const adapter = options.adapter || "runtime-engine";

  if (!SUPPORTED_ADAPTERS.includes(adapter)) {
    return {
      status: "UNSUPPORTED_ADAPTER",
      valid: false,
      adapter,
      mode: options.mode || null,
      errors: [`Unsupported adapter: ${adapter}. Supported: ${SUPPORTED_ADAPTERS.join(", ")}`],
      warnings: [],
    };
  }

  return {
    status: "ADAPTER_RESOLVED",
    valid: true,
    adapter,
    mode: options.mode || null,
    errors: [],
    warnings: [],
  };
}

function buildAdapterSafetyPolicy() {
  return buildSafetyPolicy({
    adapter_layer: true,
    dry_run: true,
    no_commands_executed: true,
    no_api_write_calls: true,
    no_runtime_execution: true,
    local_evidence_only: true,
  });
}

function executeWithRuntimeAdapter(options = {}) {
  const adapter = options.adapter || "runtime-engine";
  const mode = options.mode;
  const { packageDir, jobName, outDir } = options;
  const dliQueue = options.dliQueue || "default";

  if (!SUPPORTED_ADAPTERS.includes(adapter)) {
    return {
      status: "UNSUPPORTED_ADAPTER",
      valid: false,
      adapter,
      mode: mode || null,
      run_id: null,
      migration_id: null,
      package_dir: packageDir ? path.resolve(packageDir) : null,
      job_name: jobName || null,
      dli_queue: dliQueue,
      runtime_artifacts_dir: null,
      runtime_nodes_dir: null,
      command_sequence: [],
      planned_legacy_command: null,
      normalized_result: null,
      safety: buildAdapterSafetyPolicy(),
      warnings: [],
      errors: [`Unsupported adapter: ${adapter}. Supported: ${SUPPORTED_ADAPTERS.join(", ")}`],
    };
  }

  if (!SUPPORTED_MODES.includes(mode)) {
    return {
      status: "UNSUPPORTED_MODE",
      valid: false,
      adapter,
      mode: mode || null,
      run_id: null,
      migration_id: null,
      package_dir: packageDir ? path.resolve(packageDir) : null,
      job_name: jobName || null,
      dli_queue: dliQueue,
      runtime_artifacts_dir: null,
      runtime_nodes_dir: null,
      command_sequence: [],
      planned_legacy_command: null,
      normalized_result: null,
      safety: buildAdapterSafetyPolicy(),
      warnings: [],
      errors: [`Unsupported mode: ${mode}. Supported modes: ${SUPPORTED_MODES.join(", ")}`],
    };
  }

  if (mode === "CONFIRM" && !CONFIRM_SUPPORTED_ADAPTERS.includes(adapter)) {
    return {
      status: "UNSUPPORTED_MODE",
      valid: false,
      adapter,
      mode,
      run_id: null,
      migration_id: null,
      package_dir: packageDir ? path.resolve(packageDir) : null,
      job_name: jobName || null,
      dli_queue: dliQueue,
      runtime_artifacts_dir: null,
      runtime_nodes_dir: null,
      command_sequence: [],
      planned_legacy_command: null,
      normalized_result: null,
      safety: buildAdapterSafetyPolicy(),
      warnings: [],
      errors: [`Confirm execution is currently supported only with adapter=legacy-demo.`],
    };
  }

  if (mode === "SIMULATE" && !SIMULATE_SUPPORTED_ADAPTERS.includes(adapter)) {
    return {
      status: "UNSUPPORTED_MODE",
      valid: false,
      adapter,
      mode,
      run_id: null,
      migration_id: null,
      package_dir: packageDir ? path.resolve(packageDir) : null,
      job_name: jobName || null,
      dli_queue: dliQueue,
      runtime_artifacts_dir: null,
      runtime_nodes_dir: null,
      command_sequence: [],
      planned_legacy_command: null,
      normalized_result: null,
      safety: buildAdapterSafetyPolicy(),
      warnings: [],
      errors: [`Simulate mode is currently supported only with adapter=native-dli.`],
    };
  }

  if (mode === "MOCK" && !MOCK_SUPPORTED_ADAPTERS.includes(adapter)) {
    return {
      status: "UNSUPPORTED_MODE",
      valid: false,
      adapter,
      mode,
      run_id: null,
      migration_id: null,
      package_dir: packageDir ? path.resolve(packageDir) : null,
      job_name: jobName || null,
      dli_queue: dliQueue,
      runtime_artifacts_dir: null,
      runtime_nodes_dir: null,
      command_sequence: [],
      planned_legacy_command: null,
      normalized_result: null,
      safety: buildAdapterSafetyPolicy(),
      warnings: [],
      errors: [`Mock mode is currently supported only with adapter=native-dli.`],
    };
  }

  if (adapter === "native-dli" && mode === "MOCK") {
    return executeNativeDliMockAdapter(options);
  }

  if (adapter === "native-dli" && mode === "SIMULATE") {
    return executeNativeDliSimulateAdapter(options);
  }

  if (adapter === "runtime-engine") {
    return executeRuntimeEngineAdapter(options);
  }

  if (adapter === "legacy-demo") {
    if (mode === "CONFIRM") {
      return executeLegacyDemoConfirmAdapter(options);
    }
    return executeLegacyDemoAdapter(options);
  }

  if (adapter === "koocli") {
    return executeKooCliAdapter(options);
  }

  if (adapter === "native-dli") {
    return executeNativeDliAdapter(options);
  }

  return {
    status: "UNSUPPORTED_ADAPTER",
    valid: false,
    adapter,
    mode,
    run_id: null,
    migration_id: null,
    package_dir: packageDir ? path.resolve(packageDir) : null,
    job_name: jobName || null,
    dli_queue: dliQueue,
    runtime_artifacts_dir: null,
    runtime_nodes_dir: null,
    command_sequence: [],
    planned_legacy_command: null,
    normalized_result: null,
    safety: buildAdapterSafetyPolicy(),
    warnings: [],
    errors: [`Unsupported adapter: ${adapter}`],
  };
}

function executeRuntimeEngineAdapter(options = {}) {
  const { packageDir, jobName, outDir } = options;
  const dliQueue = options.dliQueue || "default";

  const engineOpts = {
    packageDir,
    jobName,
    dliQueue,
    mode: "DRY_RUN",
  };

  if (outDir) {
    engineOpts.outDir = outDir;
  }

  const engineResult = runRuntimeEngine(engineOpts);

  if (!engineResult.valid) {
    return {
      status: "RUNTIME_ENGINE_FAILED",
      valid: false,
      adapter: "runtime-engine",
      mode: "DRY_RUN",
      run_id: engineResult.run_id,
      migration_id: engineResult.migration_id,
      package_dir: engineResult.package_dir,
      job_name: engineResult.job_name,
      dli_queue: engineResult.dli_queue,
      runtime_artifacts_dir: engineResult.runtime_artifacts_dir,
      runtime_nodes_dir: engineResult.runtime_nodes_dir,
      command_sequence: engineResult.command_sequence || [],
      planned_legacy_command: null,
      normalized_result: engineResult,
      safety: buildAdapterSafetyPolicy(),
      warnings: engineResult.warnings,
      errors: engineResult.errors,
    };
  }

  return {
    status: "RUNTIME_ADAPTER_DRY_RUN_READY",
    valid: true,
    adapter: "runtime-engine",
    mode: "DRY_RUN",
    run_id: engineResult.run_id,
    migration_id: engineResult.migration_id,
    package_dir: engineResult.package_dir,
    job_name: engineResult.job_name,
    dli_queue: engineResult.dli_queue,
    runtime_artifacts_dir: engineResult.runtime_artifacts_dir,
    runtime_nodes_dir: engineResult.runtime_nodes_dir,
    command_sequence: engineResult.command_sequence,
    planned_legacy_command: null,
    normalized_result: engineResult,
    safety: buildAdapterSafetyPolicy(),
    warnings: engineResult.warnings,
    errors: [],
  };
}

function executeLegacyDemoAdapter(options = {}) {
  const { packageDir, jobName, outDir } = options;
  const dliQueue = options.dliQueue || "default";
  const errors = [];
  const warnings = [];

  if (!packageDir) {
    return {
      status: "INVALID_INPUT",
      valid: false,
      adapter: "legacy-demo",
      mode: "DRY_RUN",
      run_id: null,
      migration_id: null,
      package_dir: null,
      job_name: jobName || null,
      dli_queue: dliQueue,
      runtime_artifacts_dir: null,
      runtime_nodes_dir: null,
      command_sequence: [],
      planned_legacy_command: null,
      normalized_result: null,
      safety: buildAdapterSafetyPolicy(),
      warnings: [],
      errors: ["packageDir is required"],
    };
  }

  if (!jobName) {
    return {
      status: "INVALID_INPUT",
      valid: false,
      adapter: "legacy-demo",
      mode: "DRY_RUN",
      run_id: null,
      migration_id: null,
      package_dir: path.resolve(packageDir),
      job_name: null,
      dli_queue: dliQueue,
      runtime_artifacts_dir: null,
      runtime_nodes_dir: null,
      command_sequence: [],
      planned_legacy_command: null,
      normalized_result: null,
      safety: buildAdapterSafetyPolicy(),
      warnings: [],
      errors: ["jobName is required"],
    };
  }

  const execPlanOpts = { packageDir };
  if (outDir) {
    execPlanOpts.outDir = outDir;
  }

  const execPlan = buildExecutionPlan(execPlanOpts);

  if (!execPlan.valid) {
    return {
      status: "INVALID_INPUT",
      valid: false,
      adapter: "legacy-demo",
      mode: "DRY_RUN",
      run_id: null,
      migration_id: execPlan.migration_id,
      package_dir: execPlan.package_dir,
      job_name: jobName,
      dli_queue: dliQueue,
      runtime_artifacts_dir: null,
      runtime_nodes_dir: null,
      command_sequence: [],
      planned_legacy_command: null,
      normalized_result: null,
      safety: buildAdapterSafetyPolicy(),
      warnings: execPlan.warnings,
      errors: execPlan.errors,
    };
  }

  const preparerOpts = { packageDir };
  if (outDir) {
    preparerOpts.outDir = outDir;
  }

  const prepared = prepareRuntimeArtifacts(preparerOpts);

  if (!prepared.valid) {
    return {
      status: "PREPARATION_FAILED",
      valid: false,
      adapter: "legacy-demo",
      mode: "DRY_RUN",
      run_id: null,
      migration_id: prepared.migration_id,
      package_dir: prepared.package_dir,
      job_name: jobName,
      dli_queue: dliQueue,
      runtime_artifacts_dir: prepared.runtime_artifacts_dir,
      runtime_nodes_dir: prepared.runtime_nodes_dir,
      command_sequence: [],
      planned_legacy_command: null,
      normalized_result: null,
      safety: buildAdapterSafetyPolicy(),
      warnings: prepared.warnings,
      errors: prepared.errors,
    };
  }

  const runId = generateRunId();
  const migrationId = execPlan.migration_id;
  const runtimeArtifactsDir = prepared.runtime_artifacts_dir;

  const plannedLegacyCommand =
    `npm run demo:one-shot -- --confirm --job-name ${jobName} --artifacts-dir ${runtimeArtifactsDir} --dli-queue ${dliQueue}`;

  return {
    status: "LEGACY_DEMO_ADAPTER_DRY_RUN_READY",
    valid: true,
    adapter: "legacy-demo",
    mode: "DRY_RUN",
    run_id: runId,
    migration_id: migrationId,
    package_dir: execPlan.package_dir,
    job_name: jobName,
    dli_queue: dliQueue,
    runtime_artifacts_dir: runtimeArtifactsDir,
    runtime_nodes_dir: prepared.runtime_nodes_dir,
    command_sequence: [],
    planned_legacy_command: plannedLegacyCommand,
    normalized_result: {
      executed: false,
      dry_run_only: true,
      adapter: "legacy-demo",
      planned_command: plannedLegacyCommand,
    },
    safety: buildAdapterSafetyPolicy(),
    warnings: execPlan.warnings.concat(prepared.warnings),
    errors: [],
  };
}

function executeKooCliAdapter(options = {}) {
  const { packageDir, jobName, outDir } = options;
  const dliQueue = options.dliQueue || "default";
  const warnings = [];
  const errors = [];

  const koocliDoctor = runKooCliDoctor();

  if (!koocliDoctor.installed) {
    return {
      status: "KOOCLI_ADAPTER_UNAVAILABLE",
      valid: false,
      adapter: "koocli",
      mode: "DRY_RUN",
      run_id: null,
      migration_id: null,
      package_dir: packageDir ? path.resolve(packageDir) : null,
      job_name: jobName || null,
      dli_queue: dliQueue,
      runtime_artifacts_dir: null,
      runtime_nodes_dir: null,
      command_sequence: [],
      planned_legacy_command: null,
      normalized_result: null,
      koocli_diagnostics: koocliDoctor.diagnostics,
      future_command_plan: null,
      safety: buildAdapterSafetyPolicy(),
      warnings: koocliDoctor.warnings,
      errors: ["KooCLI executable hcloud not found or not configured"],
    };
  }

  if (!packageDir) {
    return {
      status: "INVALID_INPUT",
      valid: false,
      adapter: "koocli",
      mode: "DRY_RUN",
      run_id: null,
      migration_id: null,
      package_dir: null,
      job_name: jobName || null,
      dli_queue: dliQueue,
      runtime_artifacts_dir: null,
      runtime_nodes_dir: null,
      command_sequence: [],
      planned_legacy_command: null,
      normalized_result: null,
      koocli_diagnostics: koocliDoctor.diagnostics,
      future_command_plan: null,
      safety: buildAdapterSafetyPolicy(),
      warnings: koocliDoctor.warnings,
      errors: ["packageDir is required"],
    };
  }

  if (!jobName) {
    return {
      status: "INVALID_INPUT",
      valid: false,
      adapter: "koocli",
      mode: "DRY_RUN",
      run_id: null,
      migration_id: null,
      package_dir: path.resolve(packageDir),
      job_name: null,
      dli_queue: dliQueue,
      runtime_artifacts_dir: null,
      runtime_nodes_dir: null,
      command_sequence: [],
      planned_legacy_command: null,
      normalized_result: null,
      koocli_diagnostics: koocliDoctor.diagnostics,
      future_command_plan: null,
      safety: buildAdapterSafetyPolicy(),
      warnings: koocliDoctor.warnings,
      errors: ["jobName is required"],
    };
  }

  const execPlanOpts = { packageDir };
  if (outDir) {
    execPlanOpts.outDir = outDir;
  }

  const execPlan = buildExecutionPlan(execPlanOpts);

  if (!execPlan.valid) {
    return {
      status: "INVALID_INPUT",
      valid: false,
      adapter: "koocli",
      mode: "DRY_RUN",
      run_id: null,
      migration_id: execPlan.migration_id,
      package_dir: execPlan.package_dir,
      job_name: jobName,
      dli_queue: dliQueue,
      runtime_artifacts_dir: null,
      runtime_nodes_dir: null,
      command_sequence: [],
      planned_legacy_command: null,
      normalized_result: null,
      koocli_diagnostics: koocliDoctor.diagnostics,
      future_command_plan: null,
      safety: buildAdapterSafetyPolicy(),
      warnings: koocliDoctor.warnings.concat(execPlan.warnings),
      errors: execPlan.errors,
    };
  }

  const preparerOpts = { packageDir };
  if (outDir) {
    preparerOpts.outDir = outDir;
  }

  const prepared = prepareRuntimeArtifacts(preparerOpts);

  if (!prepared.valid) {
    return {
      status: "PREPARATION_FAILED",
      valid: false,
      adapter: "koocli",
      mode: "DRY_RUN",
      run_id: null,
      migration_id: prepared.migration_id,
      package_dir: prepared.package_dir,
      job_name: jobName,
      dli_queue: dliQueue,
      runtime_artifacts_dir: prepared.runtime_artifacts_dir,
      runtime_nodes_dir: prepared.runtime_nodes_dir,
      command_sequence: [],
      planned_legacy_command: null,
      normalized_result: null,
      koocli_diagnostics: koocliDoctor.diagnostics,
      future_command_plan: null,
      safety: buildAdapterSafetyPolicy(),
      warnings: koocliDoctor.warnings.concat(prepared.warnings),
      errors: prepared.errors,
    };
  }

  const migrationId = execPlan.migration_id;
  const runtimeArtifactsDir = prepared.runtime_artifacts_dir;

  const futureCommandPlan = buildKooCliFutureCommandPlan({
    migrationId,
    jobName,
    dliQueue,
    runtimeArtifactsDir,
  });

  const runId = generateRunId();

  koocliDoctor.warnings.forEach((w) => warnings.push(w));
  execPlan.warnings.forEach((w) => warnings.push(w));
  prepared.warnings.forEach((w) => warnings.push(w));

  return {
    status: "KOOCLI_ADAPTER_DRY_RUN_READY",
    valid: true,
    adapter: "koocli",
    mode: "DRY_RUN",
    run_id: runId,
    migration_id: migrationId,
    package_dir: execPlan.package_dir,
    job_name: jobName,
    dli_queue: dliQueue,
    runtime_artifacts_dir: runtimeArtifactsDir,
    runtime_nodes_dir: prepared.runtime_nodes_dir,
    command_sequence: [],
    planned_legacy_command: null,
    normalized_result: {
      executed: false,
      dry_run_only: true,
      adapter: "koocli",
      koocli_status: koocliDoctor.status,
    },
    koocli_diagnostics: koocliDoctor.diagnostics,
    future_command_plan: futureCommandPlan,
    safety: buildAdapterSafetyPolicy(),
    warnings,
    errors: [],
  };
}

function executeNativeDliAdapter(options = {}) {
  const { packageDir, jobName, outDir } = options;
  const dliQueue = options.dliQueue || "default";
  const errors = [];
  const warnings = [];

  if (!packageDir) {
    return {
      status: "INVALID_INPUT",
      valid: false,
      adapter: "native-dli",
      mode: "DRY_RUN",
      run_id: null,
      migration_id: null,
      package_dir: null,
      job_name: jobName || null,
      dli_queue: dliQueue,
      runtime_artifacts_dir: null,
      runtime_nodes_dir: null,
      command_sequence: [],
      planned_legacy_command: null,
      normalized_result: null,
      native_runtime_plan: null,
      safety: buildAdapterSafetyPolicy(),
      warnings: [],
      errors: ["packageDir is required"],
    };
  }

  const planOpts = { packageDir, dliQueue };
  if (outDir) {
    planOpts.outDir = outDir;
  }

  const nativePlan = buildNativeRuntimePlan(planOpts);

  if (!nativePlan.valid) {
    return {
      status: nativePlan.status,
      valid: false,
      adapter: "native-dli",
      mode: "DRY_RUN",
      run_id: null,
      migration_id: nativePlan.migration_id,
      package_dir: nativePlan.package_dir,
      job_name: jobName || null,
      dli_queue: dliQueue,
      runtime_artifacts_dir: null,
      runtime_nodes_dir: null,
      command_sequence: [],
      planned_legacy_command: null,
      normalized_result: null,
      native_runtime_plan: nativePlan,
      safety: buildAdapterSafetyPolicy(),
      warnings: nativePlan.warnings,
      errors: nativePlan.errors,
    };
  }

  const commandSequence = flattenNativePlanSteps(nativePlan);

  return {
    status: "NATIVE_DLI_ADAPTER_DRY_RUN_READY",
    valid: true,
    adapter: "native-dli",
    mode: "DRY_RUN",
    run_id: null,
    migration_id: nativePlan.migration_id,
    package_dir: nativePlan.package_dir,
    job_name: jobName || null,
    dli_queue: dliQueue,
    runtime_artifacts_dir: null,
    runtime_nodes_dir: null,
    command_sequence: commandSequence,
    planned_legacy_command: null,
    normalized_result: {
      executed: false,
      dry_run_only: true,
      adapter: "native-dli",
      native_runtime_plan: nativePlan,
    },
    native_runtime_plan: nativePlan,
    safety: buildAdapterSafetyPolicy(),
    warnings: nativePlan.warnings,
    errors: [],
  };
}

function buildConfirmSafetyPolicy() {
  return buildSafetyPolicy({
    confirm_required: true,
    adapter_layer: true,
    legacy_demo_runtime: true,
    no_publish: true,
    no_scheduled_start: true,
    no_delete: true,
    no_update: true,
    no_overwrite: true,
    only_run_immediate_for_execution: true,
    stop_on_critical_failure: true,
    abort_if_job_exists: true,
    no_secrets_printed: true,
  });
}

function executeLegacyDemoConfirmAdapter(options = {}) {
  const { packageDir, jobName, outDir, commandRunner } = options;
  const dliQueue = options.dliQueue || "default";
  const warnings = [];

  if (!packageDir) {
    return {
      status: "LEGACY_DEMO_EXECUTION_FAILED",
      valid: false,
      adapter: "legacy-demo",
      mode: "CONFIRM",
      executed: false,
      migration_id: null,
      package_dir: null,
      job_name: jobName || null,
      dli_queue: dliQueue,
      runtime_artifacts_dir: null,
      command: null,
      exit_code: null,
      run_id: null,
      instance_id: null,
      runtime_validate_status: null,
      final_equivalence: null,
      stale_result_detected: null,
      result_paths: null,
      safety: buildConfirmSafetyPolicy(),
      warnings: [],
      errors: ["packageDir is required"],
    };
  }

  if (!jobName) {
    return {
      status: "LEGACY_DEMO_EXECUTION_FAILED",
      valid: false,
      adapter: "legacy-demo",
      mode: "CONFIRM",
      executed: false,
      migration_id: null,
      package_dir: path.resolve(packageDir),
      job_name: null,
      dli_queue: dliQueue,
      runtime_artifacts_dir: null,
      command: null,
      exit_code: null,
      run_id: null,
      instance_id: null,
      runtime_validate_status: null,
      final_equivalence: null,
      stale_result_detected: null,
      result_paths: null,
      safety: buildConfirmSafetyPolicy(),
      warnings: [],
      errors: ["jobName is required"],
    };
  }

  const execPlanOpts = { packageDir };
  if (outDir) {
    execPlanOpts.outDir = outDir;
  }

  const execPlan = buildExecutionPlan(execPlanOpts);

  if (!execPlan.valid) {
    return {
      status: "LEGACY_DEMO_EXECUTION_FAILED",
      valid: false,
      adapter: "legacy-demo",
      mode: "CONFIRM",
      executed: false,
      migration_id: execPlan.migration_id,
      package_dir: execPlan.package_dir,
      job_name: jobName,
      dli_queue: dliQueue,
      runtime_artifacts_dir: null,
      command: null,
      exit_code: null,
      run_id: null,
      instance_id: null,
      runtime_validate_status: null,
      final_equivalence: null,
      stale_result_detected: null,
      result_paths: null,
      safety: buildConfirmSafetyPolicy(),
      warnings: execPlan.warnings,
      errors: execPlan.errors,
    };
  }

  const preparerOpts = { packageDir };
  if (outDir) {
    preparerOpts.outDir = outDir;
  }

  const prepared = prepareRuntimeArtifacts(preparerOpts);

  if (!prepared.valid) {
    return {
      status: "LEGACY_DEMO_EXECUTION_FAILED",
      valid: false,
      adapter: "legacy-demo",
      mode: "CONFIRM",
      executed: false,
      migration_id: prepared.migration_id,
      package_dir: prepared.package_dir,
      job_name: jobName,
      dli_queue: dliQueue,
      runtime_artifacts_dir: prepared.runtime_artifacts_dir,
      command: null,
      exit_code: null,
      run_id: null,
      instance_id: null,
      runtime_validate_status: null,
      final_equivalence: null,
      stale_result_detected: null,
      result_paths: null,
      safety: buildConfirmSafetyPolicy(),
      warnings: prepared.warnings,
      errors: prepared.errors,
    };
  }

  const runId = generateRunId();
  const migrationId = execPlan.migration_id;
  const runtimeArtifactsDir = prepared.runtime_artifacts_dir;

  const command =
    `npm run demo:one-shot -- --confirm --job-name ${jobName} --artifacts-dir ${runtimeArtifactsDir} --dli-queue ${dliQueue}`;

  const envOverrides = {
    ...process.env,
    DATAARTS_JOB_NAME: jobName,
    DATAARTS_ARTIFACTS_DIR: runtimeArtifactsDir,
    DLI_QUEUE_NAME: dliQueue,
  };

  const runner = commandRunner || require("../../core/command-runner").runShellCommand;

  const cmdResult = runner(
    { step: 1, name: "demo:one-shot", cmd: command },
    { env: envOverrides }
  );

  const exitCode = cmdResult.exit_code;
  execPlan.warnings.forEach((w) => warnings.push(w));
  prepared.warnings.forEach((w) => warnings.push(w));

  if (exitCode !== 0) {
    return {
      status: "LEGACY_DEMO_EXECUTION_FAILED",
      valid: false,
      adapter: "legacy-demo",
      mode: "CONFIRM",
      executed: true,
      command,
      exit_code: exitCode,
      run_id: runId,
      instance_id: null,
      runtime_validate_status: null,
      final_equivalence: null,
      stale_result_detected: null,
      result_paths: null,
      migration_id: migrationId,
      package_dir: execPlan.package_dir,
      job_name: jobName,
      dli_queue: dliQueue,
      runtime_artifacts_dir: runtimeArtifactsDir,
      safety: buildConfirmSafetyPolicy(),
      warnings,
      errors: [`demo:one-shot exited with code ${exitCode}`],
    };
  }

  const resultPaths = {
    result_json: path.resolve("out/demo_one_shot_result.json"),
    report_md: path.resolve("out/demo_one_shot_report.md"),
  };

  let instanceId = null;
  let runtimeValidateStatus = null;
  let finalEquivalence = null;
  let staleResultDetected = null;

  const resultJson = require("../../core/json-file").readJsonSafe(resultPaths.result_json);
  if (resultJson && !resultJson._parse_error) {
    instanceId = resultJson.instance_id || null;
    runtimeValidateStatus = resultJson.runtime_validate_status || null;
    finalEquivalence = resultJson.final_equivalence || null;
    staleResultDetected = resultJson.stale_result_detected || null;
    if (resultJson.run_id) {
      resultPaths.run_result_json = path.resolve("out/runs", resultJson.run_id, "demo_one_shot_result.json");
      resultPaths.run_report_md = path.resolve("out/runs", resultJson.run_id, "demo_one_shot_report.md");
    }
  }

  return {
    status: "LEGACY_DEMO_EXECUTION_COMPLETE",
    valid: true,
    adapter: "legacy-demo",
    mode: "CONFIRM",
    executed: true,
    migration_id: migrationId,
    package_dir: execPlan.package_dir,
    job_name: jobName,
    dli_queue: dliQueue,
    runtime_artifacts_dir: runtimeArtifactsDir,
    command,
    exit_code: exitCode,
    run_id: runId,
    instance_id: instanceId,
    runtime_validate_status: runtimeValidateStatus,
    final_equivalence: finalEquivalence,
    stale_result_detected: staleResultDetected,
    result_paths: resultPaths,
    safety: buildConfirmSafetyPolicy(),
    warnings,
    errors: [],
  };
}

function executeNativeDliSimulateAdapter(options = {}) {
  const { packageDir, jobName, outDir } = options;
  const dliQueue = options.dliQueue || "default";

  const simOpts = { packageDir, dliQueue };
  if (outDir) {
    simOpts.outDir = outDir;
  }

  const simResult = simulateNativeDliExecution(simOpts);

  if (!simResult.valid) {
    return {
      status: "NATIVE_DLI_ADAPTER_SIMULATION_FAILED",
      valid: false,
      adapter: "native-dli",
      mode: "SIMULATE",
      run_id: simResult.run_id,
      migration_id: simResult.migration_id,
      package_dir: simResult.package_dir,
      job_name: jobName || null,
      dli_queue: dliQueue,
      simulation_only: true,
      final_equivalence: simResult.final_equivalence,
      equivalence_confirmed: false,
      native_simulation_result: simResult,
      safety: buildAdapterSafetyPolicy(),
      warnings: simResult.warnings,
      errors: simResult.errors,
    };
  }

  return {
    status: "NATIVE_DLI_ADAPTER_SIMULATION_COMPLETE",
    valid: true,
    adapter: "native-dli",
    mode: "SIMULATE",
    run_id: simResult.run_id,
    migration_id: simResult.migration_id,
    package_dir: simResult.package_dir,
    job_name: jobName || null,
    dli_queue: dliQueue,
    simulation_only: true,
    final_equivalence: "SIMULATED_EQUIVALENT",
    equivalence_confirmed: false,
    native_simulation_result: simResult,
    safety: buildAdapterSafetyPolicy(),
    warnings: simResult.warnings,
    errors: [],
  };
}

function executeNativeDliMockAdapter(options = {}) {
  const { packageDir, jobName, outDir } = options;
  const dliQueue = options.dliQueue || "default";

  if (!packageDir) {
    return {
      status: "INVALID_INPUT",
      valid: false,
      adapter: "native-dli",
      mode: "MOCK",
      run_id: null,
      migration_id: null,
      package_dir: null,
      job_name: jobName || null,
      dli_queue: dliQueue,
      runtime_artifacts_dir: null,
      runtime_nodes_dir: null,
      command_sequence: [],
      planned_legacy_command: null,
      normalized_result: null,
      native_mock_execution_result: null,
      safety: buildAdapterSafetyPolicy(),
      warnings: [],
      errors: ["packageDir is required"],
    };
  }

  const resolvedPackageDir = path.resolve(packageDir);
  const pkg = loadMigrationPackage(resolvedPackageDir);
  const runtimeArtifacts = loadRuntimePackageArtifacts({
    packageDir: resolvedPackageDir,
    migrationId: pkg.migration_id,
  });

  const validationQueries = runtimeArtifacts.valid
    ? (runtimeArtifacts.validation_queries.queries || [])
    : [];

  const mockClient = createMockDliClient({ validationQueries });

  const execOpts = { packageDir: resolvedPackageDir, dliQueue, mode: "MOCK", dliClient: mockClient };
  if (outDir) {
    execOpts.outDir = outDir;
  }

  const execResult = executeNativeDliPlan(execOpts);

  if (!execResult.valid) {
    return {
      status: "NATIVE_DLI_ADAPTER_MOCK_EXECUTION_FAILED",
      valid: false,
      adapter: "native-dli",
      mode: "MOCK",
      run_id: execResult.run_id,
      migration_id: execResult.migration_id,
      package_dir: execResult.package_dir,
      job_name: jobName || null,
      dli_queue: dliQueue,
      final_equivalence: execResult.final_equivalence,
      equivalence_confirmed: false,
      real_runtime_confirmed: false,
      native_mock_execution_result: execResult,
      safety: buildAdapterSafetyPolicy(),
      warnings: execResult.warnings,
      errors: execResult.errors,
    };
  }

  return {
    status: "NATIVE_DLI_ADAPTER_MOCK_EXECUTION_COMPLETE",
    valid: true,
    adapter: "native-dli",
    mode: "MOCK",
    run_id: execResult.run_id,
    migration_id: execResult.migration_id,
    package_dir: execResult.package_dir,
    job_name: jobName || null,
    dli_queue: dliQueue,
    final_equivalence: "MOCK_EQUIVALENT",
    equivalence_confirmed: false,
    real_runtime_confirmed: false,
    native_mock_execution_result: execResult,
    safety: buildAdapterSafetyPolicy(),
    warnings: execResult.warnings,
    errors: [],
  };
}

module.exports = {
  resolveRuntimeAdapter,
  executeWithRuntimeAdapter,
  buildConfirmSafetyPolicy,
  SUPPORTED_ADAPTERS,
  SUPPORTED_MODES,
  CONFIRM_SUPPORTED_ADAPTERS,
  SIMULATE_SUPPORTED_ADAPTERS,
  MOCK_SUPPORTED_ADAPTERS,
};
