const { detectKooCli } = require("./koocli-client");
const { buildSafetyPolicy } = require("../core/safety-policy");

function runKooCliDoctor(options = {}) {
  const findings = [];
  const warnings = [];
  const info = [];

  const diagnostics = detectKooCli(options);

  diagnostics.warnings.forEach((w) => warnings.push(w));
  diagnostics.errors.forEach((e) => findings.push(e));

  if (!diagnostics.installed) {
    findings.push("KooCLI executable hcloud not found");
  } else {
    info.push("KooCLI executable hcloud found");

    if (diagnostics.version) {
      info.push(`KooCLI version: ${diagnostics.version}`);
    }

    if (diagnostics.configure_test.attempted && !diagnostics.configure_test.success) {
      warnings.push("hcloud configure test failed - configuration may be incomplete");
    }

    if (diagnostics.configure_list.attempted && !diagnostics.configure_list.success) {
      warnings.push("hcloud configure list failed - configuration may be incomplete");
    }
  }

  let status;
  let healthy;

  if (!diagnostics.installed) {
    status = "KOOCLI_UNAVAILABLE";
    healthy = false;
  } else if (warnings.length > 0) {
    status = "KOOCLI_CONFIG_WARNING";
    healthy = true;
  } else {
    status = "KOOCLI_HEALTHY";
    healthy = true;
  }

  const safety = buildSafetyPolicy({
    koocli_diagnostic_only: true,
    no_service_api_calls: true,
    no_api_write_calls: true,
    no_runtime_execution: true,
    no_sql_execution: true,
    no_commands_outside_allowlist: true,
  });

  return {
    status,
    healthy,
    installed: diagnostics.installed,
    findings,
    warnings,
    info,
    diagnostics,
    safety,
  };
}

module.exports = {
  runKooCliDoctor,
};
