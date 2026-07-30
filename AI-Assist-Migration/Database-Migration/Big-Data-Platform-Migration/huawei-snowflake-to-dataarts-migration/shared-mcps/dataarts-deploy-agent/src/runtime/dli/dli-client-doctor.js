const { assertDliClient } = require("./dli-client-interface");
const { createRealDliClient, validateRealDliClientConfig, createRealDliSafetyPolicy } = require("./real-dli-client");

function runDliClientDoctor(options = {}) {
  const findings = [];
  const warnings = [];

  const configResult = validateRealDliClientConfig(options);

  if (!configResult.valid) {
    for (const err of configResult.errors) {
      findings.push(err);
    }
  }

  for (const w of configResult.warnings) {
    warnings.push(w);
  }

  let clientInterfaceValid = false;
  try {
    const client = createRealDliClient(options);
    assertDliClient(client);
    clientInterfaceValid = true;
  } catch (err) {
    findings.push(`DLI client interface validation failed: ${err.message}`);
  }

  const safety = createRealDliSafetyPolicy();

  if (!safety.no_real_sql_execution) {
    findings.push("Safety policy missing no_real_sql_execution");
  }
  if (!safety.no_cloud_write_calls) {
    findings.push("Safety policy missing no_cloud_write_calls");
  }

  const healthy = findings.length === 0;

  const sourceMap = configResult.source_map || {};
  const envFileStatus = configResult.env_file_status || "unknown";

  return {
    status: healthy ? "DLI_CLIENT_DOCTOR_HEALTHY" : "DLI_CLIENT_DOCTOR_UNHEALTHY",
    healthy,
    config: configResult,
    client_interface_valid: clientInterfaceValid,
    source_map: sourceMap,
    env_file_status: envFileStatus,
    findings,
    warnings,
    safety,
  };
}

module.exports = {
  runDliClientDoctor,
};
