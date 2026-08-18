const path = require("path");
const { loadMigrationPackage } = require("../migration/package-loader");
const { loadRuntimePackageArtifacts } = require("./runtime-package-loader");
const { compareValidationPlanToRuntimeQueries } = require("./runtime-validation-plan-checker");
const { buildSafetyPolicy } = require("../core/safety-policy");

function buildNativeRuntimeSafetyPolicy() {
  return buildSafetyPolicy({
    native_runtime_plan_only: true,
    no_cloud_api_calls: true,
    no_runtime_execution: true,
    no_sql_execution: true,
    no_confirm: true,
    no_commands_executed: true,
  });
}

function buildNativeRuntimePlan(options = {}) {
  const errors = [];
  const warnings = [];

  const packageDir = options.packageDir;
  const dliQueue = options.dliQueue || "default";
  const outDir = options.outDir || "./out";

  if (!packageDir) {
    return {
      status: "INVALID_INPUT",
      valid: false,
      migration_id: null,
      package_dir: null,
      dli_queue: dliQueue,
      summary: {
        setup_sql_count: 0,
        target_sql_count: 0,
        validation_query_count: 0,
        total_steps: 0,
      },
      phases: {
        runtime_setup: [],
        target_transform: [],
        runtime_validation: [],
        equivalence_summary: [],
      },
      safety: buildNativeRuntimeSafetyPolicy(),
      warnings,
      errors: ["packageDir is required"],
    };
  }

  const resolvedPackageDir = path.resolve(packageDir);

  const pkg = loadMigrationPackage(resolvedPackageDir);

  if (!pkg.valid) {
    return {
      status: "INVALID_PACKAGE",
      valid: false,
      migration_id: pkg.migration_id,
      package_dir: pkg.package_dir,
      dli_queue: dliQueue,
      summary: {
        setup_sql_count: 0,
        target_sql_count: 0,
        validation_query_count: 0,
        total_steps: 0,
      },
      phases: {
        runtime_setup: [],
        target_transform: [],
        runtime_validation: [],
        equivalence_summary: [],
      },
      safety: buildNativeRuntimeSafetyPolicy(),
      warnings: pkg.warnings,
      errors: pkg.errors,
    };
  }

  const migrationId = pkg.migration_id;

  const runtimeArtifacts = loadRuntimePackageArtifacts({
    packageDir: resolvedPackageDir,
    migrationId,
  });

  if (!runtimeArtifacts.valid) {
    return {
      status: "INVALID_RUNTIME_ARTIFACTS",
      valid: false,
      migration_id: migrationId,
      package_dir: resolvedPackageDir,
      dli_queue: dliQueue,
      summary: {
        setup_sql_count: 0,
        target_sql_count: 0,
        validation_query_count: 0,
        total_steps: 0,
      },
      phases: {
        runtime_setup: [],
        target_transform: [],
        runtime_validation: [],
        equivalence_summary: [],
      },
      safety: buildNativeRuntimeSafetyPolicy(),
      warnings: runtimeArtifacts.warnings,
      errors: runtimeArtifacts.errors,
    };
  }

  const planComparison = compareValidationPlanToRuntimeQueries({
    packageDir: resolvedPackageDir,
    validationPlan: pkg.validation_plan,
    runtimeQueries: runtimeArtifacts.validation_queries,
  });

  if (!planComparison.valid) {
    return {
      status: "VALIDATION_PLAN_MISMATCH",
      valid: false,
      migration_id: migrationId,
      package_dir: resolvedPackageDir,
      dli_queue: dliQueue,
      summary: {
        setup_sql_count: 0,
        target_sql_count: 0,
        validation_query_count: 0,
        total_steps: 0,
      },
      phases: {
        runtime_setup: [],
        target_transform: [],
        runtime_validation: [],
        equivalence_summary: [],
      },
      safety: buildNativeRuntimeSafetyPolicy(),
      warnings: [...warnings, ...planComparison.warnings],
      errors: [...errors, ...planComparison.findings, ...planComparison.errors],
    };
  }

  planComparison.warnings.forEach((w) => warnings.push(w));

  const setupSqlFiles = runtimeArtifacts.setup_sql_files;
  const manifestNodes = pkg.artifact_manifest_result.nodes || [];
  const validationQueries = runtimeArtifacts.validation_queries.queries || [];

  const runtimeSetupPhase = [];
  let executionOrder = 1;

  for (const setupFile of setupSqlFiles) {
    runtimeSetupPhase.push({
      execution_order: executionOrder,
      phase: "runtime_setup",
      type: "DLI_SQL",
      name: setupFile.file_name,
      file_path: setupFile.file_path,
      statement_count: setupFile.statement_count,
      execution_required: true,
      executed: false,
    });
    executionOrder++;
  }

  const targetTransformPhase = [];

  for (const node of manifestNodes) {
    targetTransformPhase.push({
      execution_order: executionOrder,
      phase: "target_transform",
      type: "DLI_SQL",
      name: node.name,
      node_id: node.id,
      sql_file: node.sql_file,
      sql_path: node.sql_path,
      depends_on: node.depends_on || [],
      execution_required: true,
      executed: false,
    });
    executionOrder++;
  }

  const runtimeValidationPhase = [];

  for (const query of validationQueries) {
    runtimeValidationPhase.push({
      execution_order: executionOrder,
      phase: "runtime_validation",
      type: "DLI_QUERY",
      name: query.id,
      query_type: query.type,
      object_name: query.object_name,
      sql: query.sql,
      expected: query.expected,
      execution_required: true,
      executed: false,
    });
    executionOrder++;
  }

  const equivalenceSummaryPhase = [
    {
      execution_order: executionOrder,
      phase: "equivalence_summary",
      type: "LOCAL_COMPARISON",
      name: "equivalence_summary",
      description: "Compare DLI validation query results against Snowflake expected results.",
      execution_required: true,
      executed: false,
    },
  ];
  executionOrder++;

  const setupSqlCount = runtimeSetupPhase.length;
  const targetSqlCount = targetTransformPhase.length;
  const validationQueryCount = runtimeValidationPhase.length;
  const totalSteps = setupSqlCount + targetSqlCount + validationQueryCount + equivalenceSummaryPhase.length;

  return {
    status: "NATIVE_RUNTIME_PLAN_READY",
    valid: true,
    migration_id: migrationId,
    package_dir: resolvedPackageDir,
    dli_queue: dliQueue,
    out_dir: outDir,
    summary: {
      setup_sql_count: setupSqlCount,
      target_sql_count: targetSqlCount,
      validation_query_count: validationQueryCount,
      total_steps: totalSteps,
    },
    phases: {
      runtime_setup: runtimeSetupPhase,
      target_transform: targetTransformPhase,
      runtime_validation: runtimeValidationPhase,
      equivalence_summary: equivalenceSummaryPhase,
    },
    safety: buildNativeRuntimeSafetyPolicy(),
    warnings,
    errors: [],
  };
}

function flattenNativePlanSteps(plan) {
  const steps = [];
  for (const step of plan.phases.runtime_setup) {
    steps.push(step);
  }
  for (const step of plan.phases.target_transform) {
    steps.push(step);
  }
  for (const step of plan.phases.runtime_validation) {
    steps.push(step);
  }
  for (const step of plan.phases.equivalence_summary) {
    steps.push(step);
  }
  return steps;
}

module.exports = {
  buildNativeRuntimePlan,
  buildNativeRuntimeSafetyPolicy,
  flattenNativePlanSteps,
};
