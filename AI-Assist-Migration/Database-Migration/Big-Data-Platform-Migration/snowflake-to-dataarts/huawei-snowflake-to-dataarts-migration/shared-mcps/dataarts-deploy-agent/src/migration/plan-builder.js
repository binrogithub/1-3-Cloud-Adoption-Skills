const { loadMigrationPackage } = require("./package-loader");
const { buildSafetyPolicy } = require("../core/safety-policy");

function buildMigrationPlan(options = {}) {
  const packageDir = options.packageDir;

  if (!packageDir) {
    return {
      status: "INVALID_INPUT",
      valid: false,
      errors: ["packageDir is required"],
      warnings: [],
    };
  }

  const pkg = loadMigrationPackage(packageDir);

  if (!pkg.valid) {
    return {
      status: "INVALID_PACKAGE",
      valid: false,
      package_dir: pkg.package_dir,
      migration_id: pkg.migration_id,
      errors: pkg.errors,
      warnings: pkg.warnings,
    };
  }

  const manifest = pkg.artifact_manifest_result.manifest;
  const nodes = pkg.artifact_manifest_result.nodes;
  const validationChecks = pkg.validation_plan?.checks || [];

  const plannedSteps = [
    {
      step: 1,
      name: "validate-package",
      type: "LOCAL_VALIDATION",
      description: "Validate migration package structure and artifact manifest."
    },
    {
      step: 2,
      name: "validate-runtime-artifacts",
      type: "LOCAL_VALIDATION",
      description: "Validate target SQL files, node dependencies, and single-statement runtime policy."
    },
    {
      step: 3,
      name: "prepare-runtime-data",
      type: "DLI_RUNTIME_PREPARATION",
      description: "Prepare/reset target validation data if execution is confirmed."
    },
    {
      step: 4,
      name: "create-dataarts-job",
      type: "DATAARTS_DEPLOYMENT",
      description: "Create DataArts Factory job from target artifact manifest."
    },
    {
      step: 5,
      name: "verify-dataarts-job",
      type: "DATAARTS_READ_VALIDATION",
      description: "Verify created job structure and exported backend definition."
    },
    {
      step: 6,
      name: "run-immediate",
      type: "CONTROLLED_EXECUTION",
      description: "Execute DataArts job once using run-immediate only."
    },
    {
      step: 7,
      name: "runtime-validate",
      type: "RUNTIME_VALIDATION",
      description: "Validate DLI/DWS output against validation plan."
    },
    {
      step: 8,
      name: "doctor",
      type: "EVIDENCE_VALIDATION",
      description: "Validate run_id, job_name, instance_id and stale result protection."
    },
    {
      step: 9,
      name: "equivalence-summary",
      type: "REPORTING",
      description: "Generate equivalence summary and migration evidence report."
    }
  ];

  return {
    status: "PLAN_READY",
    valid: true,
    migration_id: pkg.migration_id,
    package_dir: pkg.package_dir,
    source: {
      type: "snowflake_task_graph",
      task_graph_path: pkg.paths.source_task_graph,
      task_graph_bytes: Buffer.byteLength(pkg.source.task_graph_sql, "utf-8"),
    },
    target: {
      orchestrator: manifest.target.orchestrator,
      runtime: manifest.target.runtime,
      node_type: manifest.target.node_type,
      node_count: nodes.length,
    },
    runtime_policy: manifest.runtime_policy || {},
    nodes: nodes.map((node, index) => ({
      order: index + 1,
      id: node.id,
      name: node.name,
      type: node.type,
      sql_file: node.sql_file,
      statement_count: node.statement_count,
      depends_on: node.depends_on || [],
    })),
    validation: {
      expected_runtime_status: pkg.validation_plan.expected_runtime_status || null,
      expected_final_equivalence: pkg.validation_plan.expected_final_equivalence || null,
      check_count: validationChecks.length,
      checks: validationChecks,
    },
    planned_steps: plannedSteps,
    safety: buildSafetyPolicy({
      plan_only: true,
      no_api_write_calls: true,
      no_runtime_execution: true,
    }),
    warnings: pkg.warnings,
    errors: [],
  };
}

module.exports = {
  buildMigrationPlan,
};
