const fs = require("fs");
const path = require("path");
const { loadMigrationPackage } = require("./package-loader");
const { buildMigrationPlan } = require("./plan-builder");
const { runMigrationPackageDoctor } = require("./package-doctor");
const { readJsonSafe } = require("../core/json-file");

function discoverMigrationPackages(options) {
  const { packagesDir } = options;
  const errors = [];

  if (!packagesDir) {
    return { packages: [], errors: ["packagesDir is required"] };
  }

  const resolvedDir = path.resolve(packagesDir);

  if (!fs.existsSync(resolvedDir)) {
    return { packages: [], errors: [`packagesDir does not exist: ${resolvedDir}`] };
  }

  const entries = fs.readdirSync(resolvedDir, { withFileTypes: true });
  const candidates = entries
    .filter((e) => e.isDirectory())
    .map((e) => e.name)
    .sort();

  const packages = [];

  for (const name of candidates) {
    const dir = path.join(resolvedDir, name);
    const hasSource = fs.existsSync(path.join(dir, "source", "snowflake_task_graph.sql"));
    const hasManifest = fs.existsSync(path.join(dir, "target", "artifact_manifest.json"));
    const hasValidation = fs.existsSync(path.join(dir, "validation", "validation_plan.json"));

    if (hasSource && hasManifest && hasValidation) {
      packages.push({ name, dir });
    }
  }

  return { packages, errors };
}

function classifyReadiness({ valid, doctorHealthy, findingsCount, warnings, equivalenceResult }) {
  if (!valid) return "INVALID_PACKAGE";
  if (findingsCount > 0) return "BLOCKED";

  if (equivalenceResult) {
    const confirmed = equivalenceResult.equivalence_confirmed === true;
    const equivalent = equivalenceResult.final_equivalence === "EQUIVALENT" || equivalenceResult.status === "EQUIVALENT";
    if (confirmed || equivalent) return "RUNTIME_CONFIRMED";

    const notExecuted = equivalenceResult.status === "NOT_EXECUTED";
    if (notExecuted && doctorHealthy) return "DRY_RUN_VALIDATED";
  }

  const hasMergeDli = warnings.some((w) => w.includes("MERGE") && w.includes("DLI"));
  const hasFullRefresh = warnings.some((w) => w.toLowerCase().includes("full-refresh") || w.toLowerCase().includes("full refresh"));
  if (hasMergeDli || hasFullRefresh) return "NEEDS_REVIEW";

  if (doctorHealthy) return "READY_FOR_DRY_RUN";

  return "BLOCKED";
}

function assessMigrationPackage(options) {
  const { packageDir } = options;
  const errors = [];
  const warnings = [];

  const pkg = loadMigrationPackage(packageDir);
  const plan = buildMigrationPlan({ packageDir });
  const doctor = runMigrationPackageDoctor({ packageDir });

  const packageName = path.basename(packageDir);

  let equivalenceResult = null;
  let expectedEquivalenceStatus = null;
  let equivalenceConfirmed = null;

  const equivPath = path.join(packageDir, "expected", "equivalence_summary_result.json");
  const equivData = readJsonSafe(equivPath);
  if (equivData && !equivData._parse_error) {
    equivalenceResult = equivData;
    expectedEquivalenceStatus = equivData.status || null;
    equivalenceConfirmed = equivData.equivalence_confirmed === true;
  }

  const allWarnings = [...(pkg.warnings || []), ...(doctor.warnings || []), ...(plan.warnings || [])];
  const allFindings = [...(doctor.findings || [])];
  const allErrors = [...(pkg.errors || []), ...(plan.errors || [])];

  const readinessStatus = classifyReadiness({
    valid: pkg.valid,
    doctorHealthy: doctor.healthy,
    findingsCount: allFindings.length,
    warnings: allWarnings,
    equivalenceResult,
  });

  return {
    package_name: packageName,
    package_dir: packageDir,
    migration_id: pkg.migration_id || doctor.migration_id || null,
    valid: pkg.valid,
    readiness_status: readinessStatus,
    plan_status: plan.status,
    doctor_status: doctor.status,
    doctor_healthy: doctor.healthy,
    findings_count: allFindings.length,
    warnings_count: allWarnings.length,
    target_runtime: doctor.summary?.target_runtime || plan.target?.runtime || null,
    target_orchestrator: doctor.summary?.target_orchestrator || plan.target?.orchestrator || null,
    node_count: doctor.summary?.node_count || plan.target?.node_count || 0,
    validation_check_count: doctor.summary?.validation_check_count || plan.validation?.check_count || 0,
    expected_equivalence_status: expectedEquivalenceStatus,
    equivalence_confirmed: equivalenceConfirmed,
    warnings: allWarnings,
    findings: allFindings,
    errors: allErrors,
  };
}

function batchAssessMigrationPackages(options) {
  const { packagesDir, outDir } = options;
  const warnings = [];
  const errors = [];

  if (!packagesDir) {
    return {
      status: "INVALID_INPUT",
      valid: false,
      packages_dir: null,
      package_count: 0,
      summary: {
        runtime_confirmed: 0,
        dry_run_validated: 0,
        ready_for_dry_run: 0,
        blocked: 0,
        invalid: 0,
        needs_review: 0,
      },
      packages: [],
      safety: {
        batch_assessment_only: true,
        no_cloud_api_calls: true,
        no_runtime_execution: true,
        no_sql_execution: true,
      },
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
      package_count: 0,
      summary: {
        runtime_confirmed: 0,
        dry_run_validated: 0,
        ready_for_dry_run: 0,
        blocked: 0,
        invalid: 0,
        needs_review: 0,
      },
      packages: [],
      safety: {
        batch_assessment_only: true,
        no_cloud_api_calls: true,
        no_runtime_execution: true,
        no_sql_execution: true,
      },
      warnings,
      errors,
    };
  }

  const assessed = [];

  for (const pkg of discovery.packages) {
    try {
      const result = assessMigrationPackage({ packageDir: pkg.dir });
      assessed.push(result);
    } catch (err) {
      errors.push(`Failed to assess package ${pkg.name}: ${err.message}`);
      assessed.push({
        package_name: pkg.name,
        package_dir: pkg.dir,
        migration_id: null,
        valid: false,
        readiness_status: "INVALID_PACKAGE",
        plan_status: null,
        doctor_status: null,
        doctor_healthy: false,
        findings_count: 0,
        warnings_count: 0,
        target_runtime: null,
        target_orchestrator: null,
        node_count: 0,
        validation_check_count: 0,
        expected_equivalence_status: null,
        equivalence_confirmed: null,
        warnings: [],
        findings: [],
        errors: [err.message],
      });
    }
  }

  const summary = {
    runtime_confirmed: assessed.filter((p) => p.readiness_status === "RUNTIME_CONFIRMED").length,
    dry_run_validated: assessed.filter((p) => p.readiness_status === "DRY_RUN_VALIDATED").length,
    ready_for_dry_run: assessed.filter((p) => p.readiness_status === "READY_FOR_DRY_RUN").length,
    blocked: assessed.filter((p) => p.readiness_status === "BLOCKED").length,
    invalid: assessed.filter((p) => p.readiness_status === "INVALID_PACKAGE").length,
    needs_review: assessed.filter((p) => p.readiness_status === "NEEDS_REVIEW").length,
  };

  const valid = assessed.every((p) => p.valid);

  return {
    status: "BATCH_ASSESS_COMPLETE",
    valid,
    packages_dir: path.resolve(packagesDir),
    package_count: assessed.length,
    summary,
    packages: assessed,
    safety: {
      batch_assessment_only: true,
      no_cloud_api_calls: true,
      no_runtime_execution: true,
      no_sql_execution: true,
    },
    warnings,
    errors,
  };
}

module.exports = {
  discoverMigrationPackages,
  assessMigrationPackage,
  batchAssessMigrationPackages,
};
