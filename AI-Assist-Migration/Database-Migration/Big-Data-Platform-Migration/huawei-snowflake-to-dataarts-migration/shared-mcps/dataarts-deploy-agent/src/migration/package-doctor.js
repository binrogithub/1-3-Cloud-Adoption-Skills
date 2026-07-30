const fs = require("fs");
const path = require("path");
const { loadMigrationPackage } = require("./package-loader");
const { buildSafetyPolicy } = require("../core/safety-policy");
const { loadRuntimePackageArtifacts } = require("../runtime/runtime-package-loader");
const { compareValidationPlanToRuntimeQueries } = require("../runtime/runtime-validation-plan-checker");

function runMigrationPackageDoctor(options = {}) {
  const findings = [];
  const warnings = [];
  const info = [];

  if (!options.packageDir) {
    findings.push("packageDir is required");
    return {
      status: "UNHEALTHY",
      healthy: false,
      migration_id: null,
      package_dir: null,
      findings,
      warnings,
      info,
      summary: {
        node_count: 0,
        validation_check_count: 0,
        target_runtime: null,
        target_orchestrator: null,
        all_single_statement: false,
        requires_runtime_validation: false,
      },
      safety: buildSafetyPolicy({ doctor_only: true, no_api_write_calls: true, no_runtime_execution: true }),
    };
  }

  const packageDir = path.resolve(options.packageDir);

  if (!fs.existsSync(packageDir)) {
    findings.push(`Package directory does not exist: ${packageDir}`);
    return {
      status: "UNHEALTHY",
      healthy: false,
      migration_id: null,
      package_dir: packageDir,
      findings,
      warnings,
      info,
      summary: {
        node_count: 0,
        validation_check_count: 0,
        target_runtime: null,
        target_orchestrator: null,
        all_single_statement: false,
        requires_runtime_validation: false,
      },
      safety: buildSafetyPolicy({ doctor_only: true, no_api_write_calls: true, no_runtime_execution: true }),
    };
  }

  const pkg = loadMigrationPackage(packageDir);

  if (!pkg.valid) {
    for (const err of pkg.errors) {
      findings.push(err);
    }
  }

  for (const w of pkg.warnings) {
    warnings.push(w);
  }

  const manifest = pkg.artifact_manifest_result?.manifest;
  const nodes = pkg.artifact_manifest_result?.nodes || [];
  const validationPlan = pkg.validation_plan || {};

  if (!pkg.source.task_graph_sql || pkg.source.task_graph_sql.trim().length === 0) {
    findings.push("source/snowflake_task_graph.sql does not exist or is empty");
  }

  if (!validationPlan || validationPlan._parse_error) {
    findings.push("validation_plan.json is not valid JSON or does not exist");
  } else {
    const checks = validationPlan.checks || [];
    if (!Array.isArray(checks) || checks.length === 0) {
      findings.push("validation_plan has no checks (at least one required)");
    }
  }

  if (manifest) {
    const manifestMigrationId = manifest.migration_id;
    const validationMigrationId = validationPlan?.migration_id;

    if (manifestMigrationId && validationMigrationId && manifestMigrationId !== validationMigrationId) {
      findings.push(`migration_id inconsistent across package files: manifest="${manifestMigrationId}", validation="${validationMigrationId}"`);
    }

    if (manifest.target?.orchestrator !== "DATAARTS_FACTORY") {
      findings.push(`target.orchestrator is "${manifest.target?.orchestrator}", expected DATAARTS_FACTORY`);
    }

    if (manifest.target?.runtime !== "DLI") {
      findings.push(`target.runtime is "${manifest.target?.runtime}", expected DLI for current MVP`);
    }

    const nodeIds = new Set(nodes.map((n) => n.id));

    for (const node of nodes) {
      if (node.type !== "DLISQL") {
        findings.push(`node "${node.id}" has type "${node.type}", expected DLISQL`);
      }

      if (!node.sql_exists) {
        findings.push(`node "${node.id}" sql_file does not exist: ${node.sql_file}`);
      }

      if (node.statement_count !== 1) {
        findings.push(`node "${node.id}" has ${node.statement_count} SQL statements, expected exactly 1`);
      }
    }

    for (const node of manifest.nodes || []) {
      for (const dep of node.depends_on || []) {
        if (!nodeIds.has(dep)) {
          findings.push(`node "${node.id}" depends_on references unknown node "${dep}"`);
        }
      }
    }

    const runtimePolicy = manifest.runtime_policy || {};
    if (runtimePolicy.requires_runtime_validation !== true) {
      findings.push("runtime_policy.requires_runtime_validation must be true");
    }

    if (runtimePolicy.allow_full_refresh === true) {
      warnings.push("Full-refresh strategy is allowed for this package. Confirm this is acceptable outside demo/static datasets.");
    }

    const safety = manifest.safety || {};
    const requiredSafetyKeys = ["no_publish", "no_start", "no_delete", "no_update", "no_overwrite"];
    const missingSafety = requiredSafetyKeys.filter((k) => safety[k] !== true);
    if (missingSafety.length > 0) {
      findings.push(`Safety policy missing or not blocking: ${missingSafety.join(", ")}`);
    }
  }

  if (pkg.source.task_graph_sql && manifest?.target?.runtime === "DLI") {
    const sqlUpper = pkg.source.task_graph_sql.toUpperCase();
    if (sqlUpper.includes("MERGE")) {
      warnings.push("Source contains MERGE while target runtime is DLI. This is acceptable only if assessment approved full-refresh or equivalent rewrite.");
    }
  }

  const migrationId = pkg.migration_id || manifest?.migration_id || null;

  const runtimeSetupDir = path.join(packageDir, "runtime", "setup");
  const runtimeValidationPath = path.join(packageDir, "runtime", "validation", "validation_queries.json");
  const hasRuntimeSetup = fs.existsSync(runtimeSetupDir);
  const hasRuntimeValidation = fs.existsSync(runtimeValidationPath);

  if (hasRuntimeSetup || hasRuntimeValidation) {
    const runtimeResult = loadRuntimePackageArtifacts({ packageDir, migrationId });

    if (!runtimeResult.valid) {
      for (const err of runtimeResult.errors) {
        findings.push(err);
      }
    }

    if (hasRuntimeSetup && hasRuntimeValidation) {
      const planCheckResult = compareValidationPlanToRuntimeQueries({
        packageDir,
        validationPlan,
        runtimeQueries: runtimeResult.validation_queries,
      });

      for (const f of planCheckResult.findings) {
        findings.push(f);
      }

      for (const w of planCheckResult.warnings) {
        warnings.push(w);
      }
    }
  } else {
    warnings.push("Runtime setup/validation artifacts are missing. Package can be planned/dry-run validated but cannot be generically runtime-confirmed.");
  }

  const allSingleStatement = nodes.length > 0 && nodes.every((n) => n.statement_count === 1);
  const requiresRuntimeValidation = manifest?.runtime_policy?.requires_runtime_validation === true;
  const validationCheckCount = Array.isArray(validationPlan?.checks) ? validationPlan.checks.length : 0;

  const healthy = findings.length === 0;

  info.push(`Package directory: ${packageDir}`);
  info.push(`Nodes: ${nodes.length}`);
  info.push(`Validation checks: ${validationCheckCount}`);
  info.push(`Runtime setup: ${hasRuntimeSetup ? "present" : "missing"}`);
  info.push(`Runtime validation: ${hasRuntimeValidation ? "present" : "missing"}`);

  const safetyPolicy = buildSafetyPolicy({
    doctor_only: true,
    no_api_write_calls: true,
    no_runtime_execution: true,
    package_safety: manifest?.safety || null,
  });

  return {
    status: healthy ? "HEALTHY" : "UNHEALTHY",
    healthy,
    migration_id: migrationId,
    package_dir: packageDir,
    findings,
    warnings,
    info,
    summary: {
      node_count: nodes.length,
      validation_check_count: validationCheckCount,
      target_runtime: manifest?.target?.runtime || null,
      target_orchestrator: manifest?.target?.orchestrator || null,
      all_single_statement: allSingleStatement,
      requires_runtime_validation: requiresRuntimeValidation,
      has_runtime_setup: hasRuntimeSetup,
      has_runtime_validation: hasRuntimeValidation,
    },
    safety: safetyPolicy,
  };
}

module.exports = {
  runMigrationPackageDoctor,
};
