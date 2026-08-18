const path = require("path");
const { executeWithRuntimeAdapter } = require("../runtime/adapters/runtime-adapter");
const { buildSafetyPolicy } = require("../core/safety-policy");
const { generateRunId } = require("../core/run-id");

function normalizeRunIds(adapterResult, migrationRunId) {
  const runtimeRunId = adapterResult.run_id || null;
  return {
    run_id: migrationRunId || runtimeRunId,
    migration_run_id: migrationRunId || null,
    runtime_run_id: runtimeRunId,
  };
}

function normalizeInstanceId(instanceId) {
  return instanceId || null;
}

function executeMigration(options = {}) {
  const { packageDir, jobName, dryRun, confirm, simulate, mock } = options;
  const dliQueue = options.dliQueue || "default";
  const adapter = options.adapter || "runtime-engine";

  if (!dryRun && !confirm && !simulate && !mock) {
    return {
      status: "INVALID_INPUT",
      valid: false,
      mode: null,
      run_id: null,
      migration_run_id: null,
      runtime_run_id: null,
      migration_id: null,
      package_dir: packageDir ? path.resolve(packageDir) : null,
      job_name: jobName || null,
      dli_queue: dliQueue,
      runtime_artifacts_dir: null,
      command_sequence: [],
      adapter,
      adapter_status: null,
      instance_id: null,
      dataarts_instance_id: null,
      safety: buildSafetyPolicy({
        dry_run: false,
        no_commands_executed: true,
        no_api_write_calls: true,
        no_runtime_execution: true,
      }),
      warnings: [],
      errors: ["Either --dry-run, --confirm, --simulate, or --mock is required"],
    };
  }

  if (mock) {
    if (adapter !== "native-dli") {
      return {
        status: "UNSUPPORTED_MODE",
        valid: false,
        mode: "MOCK",
        run_id: null,
        migration_run_id: null,
        runtime_run_id: null,
        migration_id: null,
        package_dir: packageDir ? path.resolve(packageDir) : null,
        job_name: jobName || null,
        dli_queue: dliQueue,
        runtime_artifacts_dir: null,
        command_sequence: [],
        adapter,
        adapter_status: null,
        instance_id: null,
        dataarts_instance_id: null,
        runtime_validate_status: null,
        final_equivalence: null,
        stale_result_detected: null,
        command: null,
        exit_code: null,
        real_runtime_confirmed: false,
        safety: buildSafetyPolicy({
          mock_execution_only: true,
          no_commands_executed: true,
          no_api_write_calls: true,
          no_runtime_execution: true,
          no_sql_execution: true,
          no_cloud_api_calls: true,
        }),
        warnings: [],
        errors: ["Mock mode is currently supported only with adapter=native-dli."],
      };
    }

    const adapterOpts = {
      adapter: "native-dli",
      packageDir,
      jobName,
      dliQueue,
      mode: "MOCK",
    };

    if (options.outDir) {
      adapterOpts.outDir = options.outDir;
    }

    const adapterResult = executeWithRuntimeAdapter(adapterOpts);

    const migrationRunId = generateRunId();
    const normalizedIds = normalizeRunIds(adapterResult, migrationRunId);

    if (!adapterResult.valid) {
      return {
        status: adapterResult.status || "MIGRATION_MOCK_FAILED",
        valid: false,
        mode: "MOCK",
        adapter: "native-dli",
        run_id: normalizedIds.run_id,
        migration_run_id: normalizedIds.migration_run_id,
        runtime_run_id: normalizedIds.runtime_run_id,
        migration_id: adapterResult.migration_id,
        package_dir: adapterResult.package_dir,
        job_name: adapterResult.job_name,
        dli_queue: adapterResult.dli_queue,
        runtime_artifacts_dir: null,
        command_sequence: [],
        adapter_status: adapterResult.status,
        instance_id: null,
        dataarts_instance_id: null,
        runtime_validate_status: null,
        final_equivalence: null,
        stale_result_detected: null,
        mock_execution: true,
        real_runtime_confirmed: false,
        safety: adapterResult.safety,
        warnings: adapterResult.warnings,
        errors: adapterResult.errors,
      };
    }

    return {
      status: "MIGRATION_EXECUTE_MOCK_COMPLETE",
      valid: true,
      mode: "MOCK",
      adapter: "native-dli",
      run_id: normalizedIds.run_id,
      migration_run_id: normalizedIds.migration_run_id,
      runtime_run_id: normalizedIds.runtime_run_id,
      migration_id: adapterResult.migration_id,
      package_dir: adapterResult.package_dir,
      job_name: adapterResult.job_name,
      dli_queue: adapterResult.dli_queue,
      runtime_artifacts_dir: null,
      command_sequence: [],
      adapter_status: adapterResult.status,
      instance_id: null,
      dataarts_instance_id: null,
      runtime_validate_status: null,
      final_equivalence: "MOCK_EQUIVALENT",
      stale_result_detected: null,
      mock_execution: true,
      equivalence_confirmed: false,
      real_runtime_confirmed: false,
      native_mock_execution_result: adapterResult.native_mock_execution_result,
      safety: adapterResult.safety,
      warnings: adapterResult.warnings,
      errors: [],
    };
  }

  if (simulate) {
    if (adapter !== "native-dli") {
      return {
        status: "UNSUPPORTED_MODE",
        valid: false,
        mode: "SIMULATE",
        run_id: null,
        migration_run_id: null,
        runtime_run_id: null,
        migration_id: null,
        package_dir: packageDir ? path.resolve(packageDir) : null,
        job_name: jobName || null,
        dli_queue: dliQueue,
        runtime_artifacts_dir: null,
        command_sequence: [],
        adapter,
        adapter_status: null,
        instance_id: null,
        dataarts_instance_id: null,
        runtime_validate_status: null,
        final_equivalence: null,
        stale_result_detected: null,
        command: null,
        exit_code: null,
        safety: buildSafetyPolicy({
          simulation_only: true,
          no_commands_executed: true,
          no_api_write_calls: true,
          no_runtime_execution: true,
          no_sql_execution: true,
        }),
        warnings: [],
        errors: ["Simulate mode is currently supported only with adapter=native-dli."],
      };
    }

    const adapterOpts = {
      adapter: "native-dli",
      packageDir,
      jobName,
      dliQueue,
      mode: "SIMULATE",
    };

    if (options.outDir) {
      adapterOpts.outDir = options.outDir;
    }

    const adapterResult = executeWithRuntimeAdapter(adapterOpts);

    const migrationRunId = generateRunId();
    const normalizedIds = normalizeRunIds(adapterResult, migrationRunId);

    if (!adapterResult.valid) {
      return {
        status: adapterResult.status || "MIGRATION_SIMULATION_FAILED",
        valid: false,
        mode: "SIMULATE",
        adapter: "native-dli",
        run_id: normalizedIds.run_id,
        migration_run_id: normalizedIds.migration_run_id,
        runtime_run_id: normalizedIds.runtime_run_id,
        migration_id: adapterResult.migration_id,
        package_dir: adapterResult.package_dir,
        job_name: adapterResult.job_name,
        dli_queue: adapterResult.dli_queue,
        runtime_artifacts_dir: null,
        command_sequence: [],
        adapter_status: adapterResult.status,
        instance_id: null,
        dataarts_instance_id: null,
        runtime_validate_status: null,
        final_equivalence: null,
        stale_result_detected: null,
        simulation_only: true,
        safety: adapterResult.safety,
        warnings: adapterResult.warnings,
        errors: adapterResult.errors,
      };
    }

    return {
      status: "MIGRATION_EXECUTE_SIMULATION_COMPLETE",
      valid: true,
      mode: "SIMULATE",
      adapter: "native-dli",
      run_id: normalizedIds.run_id,
      migration_run_id: normalizedIds.migration_run_id,
      runtime_run_id: normalizedIds.runtime_run_id,
      migration_id: adapterResult.migration_id,
      package_dir: adapterResult.package_dir,
      job_name: adapterResult.job_name,
      dli_queue: adapterResult.dli_queue,
      runtime_artifacts_dir: null,
      command_sequence: [],
      adapter_status: adapterResult.status,
      instance_id: null,
      dataarts_instance_id: null,
      runtime_validate_status: null,
      final_equivalence: "SIMULATED_EQUIVALENT",
      stale_result_detected: null,
      simulation_only: true,
      equivalence_confirmed: false,
      native_simulation_result: adapterResult.native_simulation_result,
      safety: adapterResult.safety,
      warnings: adapterResult.warnings,
      errors: [],
    };
  }

  if (confirm && !dryRun) {
    if (adapter !== "legacy-demo") {
      return {
        status: "UNSUPPORTED_MODE",
        valid: false,
        mode: "CONFIRM",
        run_id: null,
        migration_run_id: null,
        runtime_run_id: null,
        migration_id: null,
        package_dir: packageDir ? path.resolve(packageDir) : null,
        job_name: jobName || null,
        dli_queue: dliQueue,
        runtime_artifacts_dir: null,
        command_sequence: [],
        adapter,
        adapter_status: null,
        instance_id: null,
        dataarts_instance_id: null,
        runtime_validate_status: null,
        final_equivalence: null,
        stale_result_detected: null,
        command: null,
        exit_code: null,
        safety: buildSafetyPolicy({
          confirm_required: true,
          dry_run: false,
          no_commands_executed: true,
          no_api_write_calls: true,
          no_runtime_execution: true,
        }),
        warnings: [],
        errors: ["Confirm execution is currently supported only with adapter=legacy-demo."],
      };
    }

    const adapterOpts = {
      adapter: "legacy-demo",
      packageDir,
      jobName,
      dliQueue,
      mode: "CONFIRM",
    };

    if (options.outDir) {
      adapterOpts.outDir = options.outDir;
    }

    if (options.commandRunner) {
      adapterOpts.commandRunner = options.commandRunner;
    }

    const adapterResult = executeWithRuntimeAdapter(adapterOpts);

    const migrationRunId = generateRunId();
    const normalizedIds = normalizeRunIds(adapterResult, migrationRunId);

    if (!adapterResult.valid) {
      return {
        status: adapterResult.status === "LEGACY_DEMO_EXECUTION_FAILED"
          ? "MIGRATION_EXECUTION_FAILED"
          : adapterResult.status,
        valid: false,
        mode: "CONFIRM",
        adapter: "legacy-demo",
        run_id: normalizedIds.run_id,
        migration_run_id: normalizedIds.migration_run_id,
        runtime_run_id: normalizedIds.runtime_run_id,
        migration_id: adapterResult.migration_id,
        package_dir: adapterResult.package_dir,
        job_name: adapterResult.job_name,
        dli_queue: adapterResult.dli_queue,
        runtime_artifacts_dir: adapterResult.runtime_artifacts_dir,
        instance_id: adapterResult.instance_id || null,
        dataarts_instance_id: normalizeInstanceId(adapterResult.instance_id),
        runtime_validate_status: adapterResult.runtime_validate_status || null,
        final_equivalence: adapterResult.final_equivalence || null,
        stale_result_detected: adapterResult.stale_result_detected || null,
        command: adapterResult.command || null,
        exit_code: adapterResult.exit_code != null ? adapterResult.exit_code : null,
        command_sequence: adapterResult.command_sequence || [],
        adapter_status: adapterResult.status,
        safety: adapterResult.safety,
        warnings: adapterResult.warnings,
        errors: adapterResult.errors,
      };
    }

    return {
      status: "MIGRATION_EXECUTION_COMPLETE",
      valid: true,
      mode: "CONFIRM",
      adapter: "legacy-demo",
      run_id: normalizedIds.run_id,
      migration_run_id: normalizedIds.migration_run_id,
      runtime_run_id: normalizedIds.runtime_run_id,
      migration_id: adapterResult.migration_id,
      package_dir: adapterResult.package_dir,
      job_name: adapterResult.job_name,
      dli_queue: adapterResult.dli_queue,
      runtime_artifacts_dir: adapterResult.runtime_artifacts_dir,
      instance_id: adapterResult.instance_id || null,
      dataarts_instance_id: normalizeInstanceId(adapterResult.instance_id),
      runtime_validate_status: adapterResult.runtime_validate_status || null,
      final_equivalence: adapterResult.final_equivalence || null,
      stale_result_detected: adapterResult.stale_result_detected || null,
      command: adapterResult.command,
      exit_code: adapterResult.exit_code,
      command_sequence: adapterResult.command_sequence || [],
      adapter_status: adapterResult.status,
      safety: adapterResult.safety,
      warnings: adapterResult.warnings,
      errors: adapterResult.errors,
    };
  }

  const adapterOpts = {
    adapter,
    packageDir,
    jobName,
    dliQueue,
    mode: "DRY_RUN",
  };

  if (options.outDir) {
    adapterOpts.outDir = options.outDir;
  }

  const adapterResult = executeWithRuntimeAdapter(adapterOpts);

  const migrationRunId = generateRunId();
  const normalizedIds = normalizeRunIds(adapterResult, migrationRunId);

  if (!adapterResult.valid) {
    const statusMap = {
      RUNTIME_ENGINE_FAILED: "RUNTIME_ENGINE_FAILED",
      KOOCLI_ADAPTER_UNAVAILABLE: "KOOCLI_ADAPTER_UNAVAILABLE",
    };

    return {
      status: statusMap[adapterResult.status] || adapterResult.status,
      valid: false,
      mode: "DRY_RUN",
      run_id: normalizedIds.run_id,
      migration_run_id: normalizedIds.migration_run_id,
      runtime_run_id: normalizedIds.runtime_run_id,
      migration_id: adapterResult.migration_id,
      package_dir: adapterResult.package_dir,
      job_name: adapterResult.job_name,
      dli_queue: adapterResult.dli_queue,
      runtime_artifacts_dir: adapterResult.runtime_artifacts_dir,
      command_sequence: adapterResult.command_sequence || [],
      adapter: adapterResult.adapter,
      adapter_status: adapterResult.status,
      instance_id: adapterResult.instance_id || null,
      dataarts_instance_id: normalizeInstanceId(adapterResult.instance_id),
      safety: adapterResult.safety,
      warnings: adapterResult.warnings,
      errors: adapterResult.errors,
    };
  }

  return {
    status: "MIGRATION_EXECUTE_DRY_RUN_READY",
    valid: true,
    mode: "DRY_RUN",
    run_id: normalizedIds.run_id,
    migration_run_id: normalizedIds.migration_run_id,
    runtime_run_id: normalizedIds.runtime_run_id,
    migration_id: adapterResult.migration_id,
    package_dir: adapterResult.package_dir,
    job_name: adapterResult.job_name,
    dli_queue: adapterResult.dli_queue,
    runtime_artifacts_dir: adapterResult.runtime_artifacts_dir,
    command_sequence: adapterResult.command_sequence || [],
    planned_legacy_command: adapterResult.planned_legacy_command || null,
    adapter: adapterResult.adapter,
    adapter_status: adapterResult.status,
    instance_id: adapterResult.instance_id || null,
    dataarts_instance_id: normalizeInstanceId(adapterResult.instance_id),
    safety: adapterResult.safety,
    warnings: adapterResult.warnings,
    errors: adapterResult.errors,
  };
}

module.exports = {
  executeMigration,
  normalizeRunIds,
  normalizeInstanceId,
};
