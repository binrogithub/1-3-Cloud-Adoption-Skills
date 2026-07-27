const fs = require("fs");
const path = require("path");
const { readJsonSafe } = require("../core/json-file");
const { countSqlStatements } = require("../artifacts/manifest-loader");

function loadRuntimeSetup(options = {}) {
  const errors = [];
  const warnings = [];

  if (!options.packageDir) {
    return {
      valid: false,
      setup_sql_files: [],
      errors: ["packageDir is required"],
      warnings,
    };
  }

  const packageDir = path.resolve(options.packageDir);
  const setupDir = path.join(packageDir, "runtime", "setup");

  if (!fs.existsSync(setupDir)) {
    return {
      valid: false,
      setup_sql_files: [],
      errors: [`runtime/setup directory does not exist: ${setupDir}`],
      warnings,
    };
  }

  const sqlFiles = fs
    .readdirSync(setupDir)
    .filter((f) => f.endsWith(".sql"))
    .sort();

  if (sqlFiles.length === 0) {
    errors.push("runtime/setup directory contains no .sql files");
    return {
      valid: false,
      setup_sql_files: [],
      errors,
      warnings,
    };
  }

  const setupSqlFiles = [];

  for (const fileName of sqlFiles) {
    const filePath = path.join(setupDir, fileName);
    const sql = fs.readFileSync(filePath, "utf-8");
    const statementCount = countSqlStatements(sql);

    if (statementCount !== 1) {
      errors.push(`runtime/setup/${fileName} has ${statementCount} SQL statements, expected exactly 1`);
    }

    setupSqlFiles.push({
      file_name: fileName,
      file_path: filePath,
      statement_count: statementCount,
    });
  }

  return {
    valid: errors.length === 0,
    setup_sql_files: setupSqlFiles,
    errors,
    warnings,
  };
}

function loadRuntimeValidationQueries(options = {}) {
  const errors = [];
  const warnings = [];

  if (!options.packageDir) {
    return {
      valid: false,
      validation_queries: null,
      errors: ["packageDir is required"],
      warnings,
    };
  }

  const packageDir = path.resolve(options.packageDir);
  const validationQueriesPath = path.join(packageDir, "runtime", "validation", "validation_queries.json");

  if (!fs.existsSync(validationQueriesPath)) {
    return {
      valid: false,
      validation_queries: null,
      errors: [`runtime/validation/validation_queries.json does not exist: ${validationQueriesPath}`],
      warnings,
    };
  }

  const validationQueries = readJsonSafe(validationQueriesPath);

  if (!validationQueries || validationQueries._parse_error) {
    return {
      valid: false,
      validation_queries: null,
      errors: [`runtime/validation/validation_queries.json is not valid JSON: ${validationQueriesPath}`],
      warnings,
    };
  }

  if (!validationQueries.queries || !Array.isArray(validationQueries.queries) || validationQueries.queries.length === 0) {
    errors.push("validation_queries.json must have a non-empty queries array");
    return {
      valid: false,
      validation_queries: validationQueries,
      errors,
      warnings,
    };
  }

  const requiredFields = ["id", "type", "object_name", "sql", "expected"];

  for (const [index, query] of validationQueries.queries.entries()) {
    for (const field of requiredFields) {
      if (query[field] === undefined || query[field] === null) {
        errors.push(`validation_queries.json queries[${index}] is missing required field: ${field}`);
      }
    }
  }

  if (options.migrationId && validationQueries.migration_id && validationQueries.migration_id !== options.migrationId) {
    errors.push(`validation_queries.json migration_id mismatch: expected "${options.migrationId}", got "${validationQueries.migration_id}"`);
  }

  return {
    valid: errors.length === 0,
    validation_queries: validationQueries,
    errors,
    warnings,
  };
}

function loadRuntimePackageArtifacts(options = {}) {
  const errors = [];
  const warnings = [];

  if (!options.packageDir) {
    return {
      valid: false,
      migration_id: null,
      package_dir: null,
      setup_sql_files: [],
      validation_queries: null,
      errors: ["packageDir is required"],
      warnings,
    };
  }

  const packageDir = path.resolve(options.packageDir);
  const migrationId = options.migrationId || null;

  const setupResult = loadRuntimeSetup({ packageDir });
  if (!setupResult.valid) {
    errors.push(...setupResult.errors);
  }

  const validationResult = loadRuntimeValidationQueries({ packageDir, migrationId });
  if (!validationResult.valid) {
    errors.push(...validationResult.errors);
  }

  const validationQueries = validationResult.validation_queries;

  if (validationQueries && migrationId && validationQueries.migration_id && validationQueries.migration_id !== migrationId) {
    errors.push(`migration_id mismatch: package manifest="${migrationId}", validation_queries="${validationQueries.migration_id}"`);
  }

  return {
    valid: errors.length === 0,
    migration_id: validationQueries?.migration_id || migrationId,
    package_dir: packageDir,
    setup_sql_files: setupResult.setup_sql_files,
    validation_queries: validationQueries,
    errors,
    warnings,
  };
}

module.exports = {
  loadRuntimeSetup,
  loadRuntimeValidationQueries,
  loadRuntimePackageArtifacts,
};
