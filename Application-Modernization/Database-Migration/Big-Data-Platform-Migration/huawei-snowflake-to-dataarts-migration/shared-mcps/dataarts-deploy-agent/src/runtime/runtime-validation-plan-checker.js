const fs = require("fs");
const path = require("path");
const { readJsonSafe } = require("../core/json-file");

function compareValidationPlanToRuntimeQueries(options = {}) {
  const errors = [];
  const warnings = [];
  const findings = [];

  if (!options.packageDir && !options.validationPlan && !options.runtimeQueries) {
    return {
      valid: false,
      errors: ["packageDir is required"],
      warnings,
      findings,
      matched: [],
      unmatched: [],
    };
  }

  const packageDir = options.packageDir ? path.resolve(options.packageDir) : null;
  const validationPlanPath = packageDir ? path.join(packageDir, "validation", "validation_plan.json") : null;
  const runtimeQueriesPath = packageDir ? path.join(packageDir, "runtime", "validation", "validation_queries.json") : null;

  const validationPlan = options.validationPlan || (validationPlanPath ? readJsonSafe(validationPlanPath) : null);
  const runtimeQueries = options.runtimeQueries || (runtimeQueriesPath ? readJsonSafe(runtimeQueriesPath) : null);

  if (!validationPlan || validationPlan._parse_error) {
    errors.push("validation_plan.json is not valid or does not exist");
    return {
      valid: false,
      errors,
      warnings,
      findings,
      matched: [],
      unmatched: [],
    };
  }

  if (!runtimeQueries || runtimeQueries._parse_error) {
    warnings.push("runtime/validation/validation_queries.json does not exist or is invalid; skipping validation plan comparison");
    return {
      valid: true,
      errors,
      warnings,
      findings,
      matched: [],
      unmatched: [],
    };
  }

  const planChecks = validationPlan.checks || [];
  const runtimeQueryList = runtimeQueries.queries || [];

  const skipTypes = ["PIPELINE_READY", "FINAL_EQUIVALENCE"];

  const matched = [];
  const unmatched = [];

  for (const check of planChecks) {
    if (skipTypes.includes(check.type)) {
      continue;
    }

    const matchingQuery = runtimeQueryList.find(
      (q) => q.type === check.type && q.object_name === check.object_name
    );

    if (matchingQuery) {
      matched.push({
        plan_check: { type: check.type, object_name: check.object_name },
        runtime_query: { id: matchingQuery.id, type: matchingQuery.type, object_name: matchingQuery.object_name },
      });
    } else {
      unmatched.push({
        type: check.type,
        object_name: check.object_name,
        expected: check.expected,
      });
      findings.push(`No runtime query found for validation plan check: type="${check.type}", object_name="${check.object_name}"`);
    }
  }

  return {
    valid: findings.length === 0,
    errors,
    warnings,
    findings,
    matched,
    unmatched,
  };
}

module.exports = {
  compareValidationPlanToRuntimeQueries,
};
