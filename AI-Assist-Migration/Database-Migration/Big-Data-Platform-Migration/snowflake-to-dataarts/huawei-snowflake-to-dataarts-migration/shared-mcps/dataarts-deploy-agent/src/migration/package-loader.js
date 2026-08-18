const fs = require("fs");
const path = require("path");
const { loadArtifactManifest } = require("../artifacts/manifest-loader");
const { readJsonSafe } = require("../core/json-file");

function loadMigrationPackage(packageDir) {
  const resolvedDir = path.resolve(packageDir);
  const errors = [];
  const warnings = [];

  if (!fs.existsSync(resolvedDir)) {
    return {
      valid: false,
      package_dir: resolvedDir,
      migration_id: null,
      source: {},
      artifact_manifest_result: { valid: false, manifest: null, nodes: [], errors: [], warnings: [] },
      validation_plan: {},
      paths: {},
      errors: [`Package directory does not exist: ${resolvedDir}`],
      warnings,
    };
  }

  const sourceTaskGraphPath = path.join(resolvedDir, "source", "snowflake_task_graph.sql");
  const manifestPath = path.join(resolvedDir, "target", "artifact_manifest.json");
  const validationPlanPath = path.join(resolvedDir, "validation", "validation_plan.json");

  let taskGraphSql = null;
  if (fs.existsSync(sourceTaskGraphPath)) {
    taskGraphSql = fs.readFileSync(sourceTaskGraphPath, "utf-8");
  } else {
    errors.push("Missing source task graph: source/snowflake_task_graph.sql");
  }

  const artifactManifestResult = loadArtifactManifest(manifestPath);
  if (!artifactManifestResult.valid) {
    errors.push(...artifactManifestResult.errors);
  }

  const validationPlan = readJsonSafe(validationPlanPath);
  if (!validationPlan || validationPlan._parse_error) {
    errors.push(`Validation plan is not valid JSON: ${validationPlanPath}`);
  }

  const manifestMigrationId = artifactManifestResult.manifest?.migration_id || null;
  const validationMigrationId = validationPlan?.migration_id || null;

  if (manifestMigrationId && validationMigrationId && manifestMigrationId !== validationMigrationId) {
    errors.push(`migration_id mismatch: manifest="${manifestMigrationId}", validation="${validationMigrationId}"`);
  }

  if (manifestMigrationId && taskGraphSql && !taskGraphSql.includes(manifestMigrationId)) {
    warnings.push(`Source task graph does not reference migration_id "${manifestMigrationId}"`);
  }

  return {
    valid: errors.length === 0,
    package_dir: resolvedDir,
    migration_id: manifestMigrationId,
    source: {
      task_graph_sql: taskGraphSql,
    },
    artifact_manifest_result: artifactManifestResult,
    validation_plan: validationPlan || {},
    paths: {
      source_task_graph: sourceTaskGraphPath,
      artifact_manifest: manifestPath,
      validation_plan: validationPlanPath,
    },
    errors,
    warnings,
  };
}

module.exports = {
  loadMigrationPackage,
};
