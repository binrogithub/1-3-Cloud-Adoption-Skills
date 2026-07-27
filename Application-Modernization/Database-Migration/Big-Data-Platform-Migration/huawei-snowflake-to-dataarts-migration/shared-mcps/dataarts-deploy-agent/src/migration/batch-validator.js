const path = require("path");
const { loadMigrationPackage } = require("./package-loader");
const { buildMigrationPlan } = require("./plan-builder");
const { runMigrationPackageDoctor } = require("./package-doctor");
const { prepareRuntimeArtifacts } = require("./runtime-preparer");
const { buildExecutionPlan } = require("./execution-plan-builder");
const { executeMigration } = require("./executor");
const { discoverMigrationPackages } = require("./batch-assessor");

function generateDryRunJobName(migrationId) {
  const safeId = String(migrationId || "unknown")
    .replace(/[^a-zA-Z0-9_-]/g, "_")
    .replace(/_+/g, "_")
    .replace(/^_|_$/g, "");
  return `batch_validate_${safeId}`;
}

function validateMigrationPackage(options = {}) {
  const { packageDir } = options;
  const adapter = options.adapter || "legacy-demo";
  const dliQueue = options.dliQueue || "default";
  const outDir = options.outDir;

  const packageName = packageDir ? path.basename(packageDir) : null;

  const emptyResult = {
    package_name: packageName,
    migration_id: null,
    package_dir: packageDir ? path.resolve(packageDir) : null,
    valid: false,
    validation_status: "INVALID_PACKAGE",
    stages: {
      package_load: { status: "NOT_RUN", valid: false },
      plan: { status: "NOT_RUN", valid: false },
      doctor: { status: "NOT_RUN", healthy: false, findings_count: 0, warnings_count: 0 },
      prepare_runtime: { status: "NOT_RUN", valid: false, runtime_artifacts_dir: null },
      execute_plan: { status: "NOT_RUN", valid: false, steps: 0 },
      execute_dry_run: { status: "NOT_RUN", valid: false, adapter, planned_command: null },
    },
    target_runtime: null,
    node_count: 0,
    validation_check_count: 0,
    warnings: [],
    findings: [],
    errors: [],
  };

  if (!packageDir) {
    emptyResult.errors.push("packageDir is required");
    return emptyResult;
  }

  const errors = [];
  const warnings = [];
  const findings = [];

  // Stage 1: package-load
  let pkg;
  try {
    pkg = loadMigrationPackage(packageDir);
  } catch (err) {
    emptyResult.errors.push(`package_load failed: ${err.message}`);
    emptyResult.stages.package_load = { status: "FAILED", valid: false };
    return emptyResult;
  }

  const packageLoadStage = {
    status: pkg.valid ? "PACKAGE_LOADED" : "INVALID_PACKAGE",
    valid: pkg.valid,
  };

  if (!pkg.valid) {
    return {
      package_name: packageName,
      migration_id: pkg.migration_id || null,
      package_dir: pkg.package_dir || path.resolve(packageDir),
      valid: false,
      validation_status: "INVALID_PACKAGE",
      stages: {
        ...emptyResult.stages,
        package_load: packageLoadStage,
      },
      target_runtime: null,
      node_count: 0,
      validation_check_count: 0,
      warnings: [...(pkg.warnings || [])],
      findings: [],
      errors: [...(pkg.errors || [])],
    };
  }

  const migrationId = pkg.migration_id;
  warnings.push(...(pkg.warnings || []));

  // Stage 2: plan
  let plan;
  try {
    plan = buildMigrationPlan({ packageDir });
  } catch (err) {
    errors.push(`plan failed: ${err.message}`);
    return {
      package_name: packageName,
      migration_id: migrationId,
      package_dir: path.resolve(packageDir),
      valid: false,
      validation_status: "INVALID_PACKAGE",
      stages: {
        ...emptyResult.stages,
        package_load: packageLoadStage,
        plan: { status: "FAILED", valid: false },
      },
      target_runtime: null,
      node_count: 0,
      validation_check_count: 0,
      warnings,
      findings,
      errors,
    };
  }

  const planStage = {
    status: plan.status,
    valid: plan.valid,
  };

  warnings.push(...(plan.warnings || []));

  if (!plan.valid) {
    errors.push(...(plan.errors || []));
    return {
      package_name: packageName,
      migration_id: migrationId,
      package_dir: path.resolve(packageDir),
      valid: false,
      validation_status: "INVALID_PACKAGE",
      stages: {
        ...emptyResult.stages,
        package_load: packageLoadStage,
        plan: planStage,
      },
      target_runtime: plan.target?.runtime || null,
      node_count: plan.target?.node_count || 0,
      validation_check_count: plan.validation?.check_count || 0,
      warnings,
      findings,
      errors,
    };
  }

  // Stage 3: doctor
  let doctor;
  try {
    doctor = runMigrationPackageDoctor({ packageDir });
  } catch (err) {
    errors.push(`doctor failed: ${err.message}`);
    return {
      package_name: packageName,
      migration_id: migrationId,
      package_dir: path.resolve(packageDir),
      valid: false,
      validation_status: "DOCTOR_UNHEALTHY",
      stages: {
        ...emptyResult.stages,
        package_load: packageLoadStage,
        plan: planStage,
        doctor: { status: "FAILED", healthy: false, findings_count: 0, warnings_count: 0 },
      },
      target_runtime: plan.target?.runtime || null,
      node_count: plan.target?.node_count || 0,
      validation_check_count: plan.validation?.check_count || 0,
      warnings,
      findings,
      errors,
    };
  }

  const doctorStage = {
    status: doctor.status,
    healthy: doctor.healthy,
    findings_count: (doctor.findings || []).length,
    warnings_count: (doctor.warnings || []).length,
  };

  warnings.push(...(doctor.warnings || []));
  findings.push(...(doctor.findings || []));

  if (!doctor.healthy) {
    errors.push(...(doctor.findings || []));
    return {
      package_name: packageName,
      migration_id: migrationId,
      package_dir: path.resolve(packageDir),
      valid: false,
      validation_status: "DOCTOR_UNHEALTHY",
      stages: {
        ...emptyResult.stages,
        package_load: packageLoadStage,
        plan: planStage,
        doctor: doctorStage,
      },
      target_runtime: doctor.summary?.target_runtime || plan.target?.runtime || null,
      node_count: doctor.summary?.node_count || plan.target?.node_count || 0,
      validation_check_count: doctor.summary?.validation_check_count || plan.validation?.check_count || 0,
      warnings,
      findings,
      errors,
    };
  }

  // Stage 4: prepare-runtime
  const preparerOpts = { packageDir };
  if (outDir) {
    preparerOpts.outDir = outDir;
  }

  let prepared;
  try {
    prepared = prepareRuntimeArtifacts(preparerOpts);
  } catch (err) {
    errors.push(`prepare_runtime failed: ${err.message}`);
    return {
      package_name: packageName,
      migration_id: migrationId,
      package_dir: path.resolve(packageDir),
      valid: false,
      validation_status: "RUNTIME_PREPARE_FAILED",
      stages: {
        ...emptyResult.stages,
        package_load: packageLoadStage,
        plan: planStage,
        doctor: doctorStage,
        prepare_runtime: { status: "FAILED", valid: false, runtime_artifacts_dir: null },
      },
      target_runtime: doctor.summary?.target_runtime || plan.target?.runtime || null,
      node_count: doctor.summary?.node_count || plan.target?.node_count || 0,
      validation_check_count: doctor.summary?.validation_check_count || plan.validation?.check_count || 0,
      warnings,
      findings,
      errors,
    };
  }

  const prepareRuntimeStage = {
    status: prepared.status,
    valid: prepared.valid,
    runtime_artifacts_dir: prepared.runtime_artifacts_dir || null,
  };

  warnings.push(...(prepared.warnings || []));

  if (!prepared.valid) {
    errors.push(...(prepared.errors || []));
    return {
      package_name: packageName,
      migration_id: migrationId,
      package_dir: path.resolve(packageDir),
      valid: false,
      validation_status: "RUNTIME_PREPARE_FAILED",
      stages: {
        ...emptyResult.stages,
        package_load: packageLoadStage,
        plan: planStage,
        doctor: doctorStage,
        prepare_runtime: prepareRuntimeStage,
      },
      target_runtime: doctor.summary?.target_runtime || plan.target?.runtime || null,
      node_count: doctor.summary?.node_count || plan.target?.node_count || 0,
      validation_check_count: doctor.summary?.validation_check_count || plan.validation?.check_count || 0,
      warnings,
      findings,
      errors,
    };
  }

  // Stage 5: execute-plan
  const execPlanOpts = { packageDir };
  if (outDir) {
    execPlanOpts.outDir = outDir;
  }

  let execPlan;
  try {
    execPlan = buildExecutionPlan(execPlanOpts);
  } catch (err) {
    errors.push(`execute_plan failed: ${err.message}`);
    return {
      package_name: packageName,
      migration_id: migrationId,
      package_dir: path.resolve(packageDir),
      valid: false,
      validation_status: "EXECUTION_PLAN_FAILED",
      stages: {
        ...emptyResult.stages,
        package_load: packageLoadStage,
        plan: planStage,
        doctor: doctorStage,
        prepare_runtime: prepareRuntimeStage,
        execute_plan: { status: "FAILED", valid: false, steps: 0 },
      },
      target_runtime: doctor.summary?.target_runtime || plan.target?.runtime || null,
      node_count: doctor.summary?.node_count || plan.target?.node_count || 0,
      validation_check_count: doctor.summary?.validation_check_count || plan.validation?.check_count || 0,
      warnings,
      findings,
      errors,
    };
  }

  const executePlanStage = {
    status: execPlan.status,
    valid: execPlan.valid,
    steps: (execPlan.planned_execution_steps || []).length,
  };

  warnings.push(...(execPlan.warnings || []));

  if (!execPlan.valid) {
    errors.push(...(execPlan.errors || []));
    return {
      package_name: packageName,
      migration_id: migrationId,
      package_dir: path.resolve(packageDir),
      valid: false,
      validation_status: "EXECUTION_PLAN_FAILED",
      stages: {
        ...emptyResult.stages,
        package_load: packageLoadStage,
        plan: planStage,
        doctor: doctorStage,
        prepare_runtime: prepareRuntimeStage,
        execute_plan: executePlanStage,
      },
      target_runtime: doctor.summary?.target_runtime || plan.target?.runtime || null,
      node_count: doctor.summary?.node_count || plan.target?.node_count || 0,
      validation_check_count: doctor.summary?.validation_check_count || plan.validation?.check_count || 0,
      warnings,
      findings,
      errors,
    };
  }

  // Stage 6: execute dry-run
  const jobName = generateDryRunJobName(migrationId);
  const execOpts = {
    packageDir,
    jobName,
    dryRun: true,
    adapter,
    dliQueue,
  };
  if (outDir) {
    execOpts.outDir = outDir;
  }

  let dryRunResult;
  try {
    dryRunResult = executeMigration(execOpts);
  } catch (err) {
    errors.push(`execute_dry_run failed: ${err.message}`);
    return {
      package_name: packageName,
      migration_id: migrationId,
      package_dir: path.resolve(packageDir),
      valid: false,
      validation_status: "DRY_RUN_FAILED",
      stages: {
        ...emptyResult.stages,
        package_load: packageLoadStage,
        plan: planStage,
        doctor: doctorStage,
        prepare_runtime: prepareRuntimeStage,
        execute_plan: executePlanStage,
        execute_dry_run: { status: "FAILED", valid: false, adapter, planned_command: null },
      },
      target_runtime: doctor.summary?.target_runtime || plan.target?.runtime || null,
      node_count: doctor.summary?.node_count || plan.target?.node_count || 0,
      validation_check_count: doctor.summary?.validation_check_count || plan.validation?.check_count || 0,
      warnings,
      findings,
      errors,
    };
  }

  const executeDryRunStage = {
    status: dryRunResult.status,
    valid: dryRunResult.valid,
    adapter,
    planned_command: dryRunResult.planned_legacy_command || null,
  };

  warnings.push(...(dryRunResult.warnings || []));

  if (!dryRunResult.valid) {
    errors.push(...(dryRunResult.errors || []));
    return {
      package_name: packageName,
      migration_id: migrationId,
      package_dir: path.resolve(packageDir),
      valid: false,
      validation_status: "DRY_RUN_FAILED",
      stages: {
        package_load: packageLoadStage,
        plan: planStage,
        doctor: doctorStage,
        prepare_runtime: prepareRuntimeStage,
        execute_plan: executePlanStage,
        execute_dry_run: executeDryRunStage,
      },
      target_runtime: doctor.summary?.target_runtime || plan.target?.runtime || null,
      node_count: doctor.summary?.node_count || plan.target?.node_count || 0,
      validation_check_count: doctor.summary?.validation_check_count || plan.validation?.check_count || 0,
      warnings,
      findings,
      errors,
    };
  }

  // All stages passed
  return {
    package_name: packageName,
    migration_id: migrationId,
    package_dir: path.resolve(packageDir),
    valid: true,
    validation_status: "BATCH_DRY_RUN_VALIDATED",
    stages: {
      package_load: packageLoadStage,
      plan: planStage,
      doctor: doctorStage,
      prepare_runtime: prepareRuntimeStage,
      execute_plan: executePlanStage,
      execute_dry_run: executeDryRunStage,
    },
    target_runtime: doctor.summary?.target_runtime || plan.target?.runtime || null,
    node_count: doctor.summary?.node_count || plan.target?.node_count || 0,
    validation_check_count: doctor.summary?.validation_check_count || plan.validation?.check_count || 0,
    warnings,
    findings,
    errors,
  };
}

function batchValidateMigrationPackages(options = {}) {
  const { packagesDir } = options;
  const adapter = options.adapter || "legacy-demo";
  const dliQueue = options.dliQueue || "default";
  const outDir = options.outDir;
  const warnings = [];
  const errors = [];

  const emptySummary = {
    dry_run_validated: 0,
    invalid: 0,
    blocked: 0,
    failed: 0,
    warnings: 0,
  };

  const safety = {
    batch_validation_only: true,
    dry_run_only: true,
    no_cloud_api_calls: true,
    no_runtime_execution: true,
    no_sql_execution: true,
    no_confirm: true,
  };

  if (!packagesDir) {
    return {
      status: "INVALID_INPUT",
      valid: false,
      packages_dir: null,
      adapter,
      dli_queue: dliQueue,
      package_count: 0,
      summary: emptySummary,
      packages: [],
      safety,
      warnings,
      errors: ["packagesDir is required"],
    };
  }

  const discovery = discoverMigrationPackages({ packagesDir });

  if (discovery.errors.length > 0) {
    errors.push(...discovery.errors);
  }

  if (discovery.packages.length === 0) {
    return {
      status: errors.length > 0 ? "INVALID_INPUT" : "NO_PACKAGES_FOUND",
      valid: false,
      packages_dir: path.resolve(packagesDir),
      adapter,
      dli_queue: dliQueue,
      package_count: 0,
      summary: emptySummary,
      packages: [],
      safety,
      warnings,
      errors,
    };
  }

  const validated = [];

  for (const pkg of discovery.packages) {
    try {
      const result = validateMigrationPackage({
        packageDir: pkg.dir,
        adapter,
        dliQueue,
        outDir,
      });
      validated.push(result);
    } catch (err) {
      errors.push(`Failed to validate package ${pkg.name}: ${err.message}`);
      validated.push({
        package_name: pkg.name,
        migration_id: null,
        package_dir: pkg.dir,
        valid: false,
        validation_status: "INVALID_PACKAGE",
        stages: {
          package_load: { status: "FAILED", valid: false },
          plan: { status: "NOT_RUN", valid: false },
          doctor: { status: "NOT_RUN", healthy: false, findings_count: 0, warnings_count: 0 },
          prepare_runtime: { status: "NOT_RUN", valid: false, runtime_artifacts_dir: null },
          execute_plan: { status: "NOT_RUN", valid: false, steps: 0 },
          execute_dry_run: { status: "NOT_RUN", valid: false, adapter, planned_command: null },
        },
        target_runtime: null,
        node_count: 0,
        validation_check_count: 0,
        warnings: [],
        findings: [],
        errors: [err.message],
      });
    }
  }

  const summary = {
    dry_run_validated: validated.filter((p) => p.validation_status === "BATCH_DRY_RUN_VALIDATED").length,
    invalid: validated.filter((p) => p.validation_status === "INVALID_PACKAGE").length,
    blocked: validated.filter((p) => p.validation_status === "DOCTOR_UNHEALTHY").length,
    failed: validated.filter(
      (p) =>
        p.validation_status === "RUNTIME_PREPARE_FAILED" ||
        p.validation_status === "EXECUTION_PLAN_FAILED" ||
        p.validation_status === "DRY_RUN_FAILED"
    ).length,
    warnings: validated.reduce((sum, p) => sum + (p.warnings || []).length, 0),
  };

  const valid = validated.every((p) => p.valid);

  return {
    status: "BATCH_VALIDATE_COMPLETE",
    valid,
    packages_dir: path.resolve(packagesDir),
    adapter,
    dli_queue: dliQueue,
    package_count: validated.length,
    summary,
    packages: validated,
    safety,
    warnings,
    errors,
  };
}

module.exports = {
  validateMigrationPackage,
  batchValidateMigrationPackages,
  generateDryRunJobName,
};
