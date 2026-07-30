const fs = require("fs");
const path = require("path");
const { readJsonSafe } = require("../core/json-file");

function countSqlStatements(sql) {
  const trimmed = String(sql ?? "").trim();
  if (!trimmed) return 0;

  const lines = trimmed
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith("--"));

  const joined = lines.join(" ");
  const semicolons = (joined.match(/;/g) || []).length;

  return Math.max(1, semicolons);
}

function loadArtifactManifest(manifestPath) {
  const resolvedManifestPath = path.resolve(manifestPath);
  const manifestDir = path.dirname(resolvedManifestPath);

  const errors = [];
  const warnings = [];

  if (!fs.existsSync(resolvedManifestPath)) {
    return {
      valid: false,
      manifest: null,
      manifest_path: resolvedManifestPath,
      manifest_dir: manifestDir,
      nodes: [],
      errors: [`Manifest file does not exist: ${resolvedManifestPath}`],
      warnings,
    };
  }

  const manifest = readJsonSafe(resolvedManifestPath);

  if (!manifest || manifest._parse_error) {
    return {
      valid: false,
      manifest,
      manifest_path: resolvedManifestPath,
      manifest_dir: manifestDir,
      nodes: [],
      errors: [`Manifest file is not valid JSON: ${resolvedManifestPath}`],
      warnings,
    };
  }

  if (!manifest.manifest_version) errors.push("manifest_version is required");
  if (!manifest.migration_id) errors.push("migration_id is required");
  if (!manifest.target?.runtime) errors.push("target.runtime is required");
  if (!manifest.target?.orchestrator) errors.push("target.orchestrator is required");

  if (!Array.isArray(manifest.nodes) || manifest.nodes.length === 0) {
    errors.push("nodes must be a non-empty array");
  }

  const nodeIds = new Set();
  const nodes = [];

  for (const [index, node] of (manifest.nodes || []).entries()) {
    const nodeErrors = [];

    if (!node.id) nodeErrors.push(`nodes[${index}].id is required`);
    if (!node.name) nodeErrors.push(`nodes[${index}].name is required`);
    if (!node.type) nodeErrors.push(`nodes[${index}].type is required`);
    if (!node.sql_file) nodeErrors.push(`nodes[${index}].sql_file is required`);

    if (node.id) {
      if (nodeIds.has(node.id)) {
        nodeErrors.push(`duplicate node id: ${node.id}`);
      }
      nodeIds.add(node.id);
    }

    const sqlPath = node.sql_file
      ? path.resolve(manifestDir, node.sql_file)
      : null;

    let sqlExists = false;
    let statementCount = 0;

    if (sqlPath && fs.existsSync(sqlPath)) {
      sqlExists = true;
      const sql = fs.readFileSync(sqlPath, "utf-8");
      statementCount = countSqlStatements(sql);

      if (statementCount !== 1) {
        nodeErrors.push(`node "${node.id}" must contain exactly 1 SQL statement, found ${statementCount}`);
      }
    } else if (node.sql_file) {
      nodeErrors.push(`SQL file not found for node "${node.id}": ${sqlPath}`);
    }

    if (nodeErrors.length > 0) {
      errors.push(...nodeErrors);
    }

    nodes.push({
      ...node,
      sql_path: sqlPath,
      sql_exists: sqlExists,
      statement_count: statementCount,
    });
  }

  for (const node of manifest.nodes || []) {
    const dependencies = node.depends_on || [];
    if (!Array.isArray(dependencies)) {
      errors.push(`node "${node.id}" depends_on must be an array`);
      continue;
    }

    for (const dep of dependencies) {
      if (!nodeIds.has(dep)) {
        errors.push(`node "${node.id}" depends on unknown node "${dep}"`);
      }
    }
  }

  return {
    valid: errors.length === 0,
    manifest,
    manifest_path: resolvedManifestPath,
    manifest_dir: manifestDir,
    nodes,
    errors,
    warnings,
  };
}

module.exports = {
  countSqlStatements,
  loadArtifactManifest,
};
