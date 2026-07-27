const path = require("path");
const fs = require("fs");
const { loadMigrationPackage } = require("./package-loader");
const { runMigrationPackageDoctor } = require("./package-doctor");
const { prepareRuntimeArtifacts } = require("./runtime-preparer");
const { buildSafetyPolicy } = require("../core/safety-policy");

function buildPlannedExecutionSteps() {
  return [
    {
      step_number: 1,
      step_name: "validate-package",
      category: "LOCAL_VALIDATION",
      description: "Validate migration package structure and artifact manifest.",
      execution_required: false,
    },
    {
      step_number: 2,
      step_name: "doctor-package",
      category: "LOCAL_VALIDATION",
      description: "Run migration package doctor to verify health, safety, and runtime policy.",
      execution_required: false,
    },
    {
      step_number: 3,
      step_name: "prepare-runtime-artifacts",
      category: "LOCAL_PREPARATION",
      description: "Prepare runtime artifacts directory and copy SQL files for execution.",
      execution_required: false,
    },
    {
      step_number: 4,
      step_name: "reset-runtime-validation-data",
      category: "DLI_RUNTIME_PREPARATION",
      description: "Reset target validation data in DLI to a clean state before execution.",
      execution_required: true,
    },
    {
      step_number: 5,
      step_name: "create-dataarts-job",
      category: "DATAARTS_DEPLOYMENT",
      description: "Create DataArts Factory job from target artifact manifest.",
      execution_required: true,
    },
    {
      step_number: 6,
      step_name: "verify-dataarts-job",
      category: "DATAARTS_READ_VALIDATION",
      description: "Verify created job structure and exported backend definition.",
      execution_required: true,
    },
    {
      step_number: 7,
      step_name: "export-job-definition",
      category: "DATAARTS_READ_VALIDATION",
      description: "Export job definition for evidence and audit trail.",
      execution_required: true,
    },
    {
      step_number: 8,
      step_name: "run-immediate",
      category: "CONTROLLED_EXECUTION",
      description: "Execute DataArts job once using run-immediate only.",
      execution_required: true,
    },
    {
      step_number: 9,
      step_name: "runtime-validation",
      category: "RUNTIME_VALIDATION",
      description: "Validate DLI output against validation plan checks.",
      execution_required: true,
    },
    {
      step_number: 10,
      step_name: "execution-doctor",
      category: "EVIDENCE_VALIDATION",
      description: "Validate run_id, job_name, instance_id and stale result protection.",
      execution_required: true,
    },
    {
      step_number: 11,
      step_name: "equivalence-summary",
      category: "REPORTING",
      description: "Generate equivalence summary and migration evidence report.",
      execution_required: true,
    },
  ];
}

function buildExecutionPlan(options = {}) {
  if (!options.packageDir) {
    return {
      status: "INVALID_INPUT",
      valid: false,
      migration_id: null,
      package_dir: null,
      runtime_artifacts_dir: null,
      runtime_nodes_dir: null,
      target: null,
      summary: { node_count: 0, validation_check_count: 0 },
      planned_execution_steps: [],
      errors: ["packageDir is required"],
      warnings: [],
      safety: buildSafetyPolicy({
        plan_only: true,
        no_api_write_calls: true,
        no_runtime_execution: true,
      }),
    };
  }

  const packageDir = path.resolve(options.packageDir);

  const pkg = loadMigrationPackage(packageDir);

  if (!pkg.valid) {
    return {
      status: "INVALID_PACKAGE",
      valid: false,
      migration_id: pkg.migration_id,
      package_dir: pkg.package_dir,
      runtime_artifacts_dir: null,
      runtime_nodes_dir: null,
      target: null,
      summary: { node_count: 0, validation_check_count: 0 },
      planned_execution_steps: [],
      errors: pkg.errors,
      warnings: pkg.warnings,
      safety: buildSafetyPolicy({
        plan_only: true,
        no_api_write_calls: true,
        no_runtime_execution: true,
      }),
    };
  }

  const doctor = runMigrationPackageDoctor({ packageDir });

  if (!doctor.healthy) {
    return {
      status: "DOCTOR_UNHEALTHY",
      valid: false,
      migration_id: pkg.migration_id,
      package_dir: pkg.package_dir,
      runtime_artifacts_dir: null,
      runtime_nodes_dir: null,
      target: null,
      summary: {
        node_count: doctor.summary.node_count,
        validation_check_count: doctor.summary.validation_check_count,
      },
      planned_execution_steps: [],
      errors: doctor.findings,
      warnings: doctor.warnings,
      safety: buildSafetyPolicy({
        plan_only: true,
        no_api_write_calls: true,
        no_runtime_execution: true,
      }),
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
      migration_id: pkg.migration_id,
      package_dir: pkg.package_dir,
      runtime_artifacts_dir: prepared.runtime_artifacts_dir,
      runtime_nodes_dir: prepared.runtime_nodes_dir,
      target: null,
      summary: {
        node_count: doctor.summary.node_count,
        validation_check_count: doctor.summary.validation_check_count,
      },
      planned_execution_steps: [],
      errors: prepared.errors,
      warnings: prepared.warnings,
      safety: buildSafetyPolicy({
        plan_only: true,
        no_api_write_calls: true,
        no_runtime_execution: true,
      }),
    };
  }

  const manifest = pkg.artifact_manifest_result.manifest;
  const nodes = pkg.artifact_manifest_result.nodes || [];
  const validationChecks = pkg.validation_plan?.checks || [];

  const plannedExecutionSteps = buildPlannedExecutionSteps();

  return {
    status: "EXECUTION_PLAN_READY",
    valid: true,
    migration_id: pkg.migration_id,
    package_dir: pkg.package_dir,
    runtime_artifacts_dir: prepared.runtime_artifacts_dir,
    runtime_nodes_dir: prepared.runtime_nodes_dir,
    target: {
      orchestrator: manifest.target.orchestrator,
      runtime: manifest.target.runtime,
    },
    summary: {
      node_count: nodes.length,
      validation_check_count: validationChecks.length,
    },
    planned_execution_steps: plannedExecutionSteps,
    errors: [],
    warnings: prepared.warnings,
    safety: buildSafetyPolicy({
      plan_only: true,
      no_api_write_calls: true,
      no_runtime_execution: true,
    }),
  };
}

module.exports = {
  buildExecutionPlan,
  buildPlannedExecutionSteps,
};
