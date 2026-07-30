const fs = require("fs");
const path = require("path");
const { runDliClientDoctor } = require("./runtime/dli/dli-client-doctor");

const result = runDliClientDoctor();

const outDir = path.resolve("out");
if (!fs.existsSync(outDir)) {
  fs.mkdirSync(outDir, { recursive: true });
}

const resultJsonPath = path.join(outDir, "dli_client_doctor_result.json");
const reportMdPath = path.join(outDir, "dli_client_doctor_report.md");

fs.writeFileSync(resultJsonPath, JSON.stringify(result, null, 2), "utf-8");

const lines = [];
lines.push("# DLI Client Doctor Report");
lines.push("");
lines.push("> **PREFLIGHT ONLY** — No cloud APIs called. No SQL executed. No runtime execution.");
lines.push("");
lines.push("## Summary");
lines.push("");
lines.push(`**Status:** ${result.status}`);
lines.push(`**Healthy:** ${result.healthy ? "YES" : "NO"}`);
lines.push(`**Client Interface:** ${result.client_interface_valid ? "VALID" : "INVALID"}`);
lines.push(`**Region:** ${result.config.region || "NOT SET"}`);
lines.push(`**Project ID:** ${result.config.project_id || "NOT SET"}`);
lines.push(`**DLI Queue:** ${result.config.dli_queue || "default"}`);
lines.push(`**Has AK:** ${result.config.has_ak ? "YES" : "NO"}`);
lines.push(`**Has SK:** ${result.config.has_sk ? "YES" : "NO"}`);
lines.push(`**.env.dataarts:** ${result.env_file_status || "unknown"}`);
lines.push("");

if (result.source_map && Object.keys(result.source_map).length > 0) {
  lines.push("## Config Source Summary");
  lines.push("");
  lines.push("| Variable | Source |");
  lines.push("|----------|--------|");
  for (const [key, source] of Object.entries(result.source_map)) {
    lines.push(`| ${key} | ${source} |`);
  }
  lines.push("");
}

if (result.findings.length > 0) {
  lines.push("## Findings");
  lines.push("");
  for (const f of result.findings) {
    lines.push(`- ${f}`);
  }
  lines.push("");
}

if (result.warnings.length > 0) {
  lines.push("## Warnings");
  lines.push("");
  for (const w of result.warnings) {
    lines.push(`- ${w}`);
  }
  lines.push("");
}

lines.push("## Safety");
lines.push("");
lines.push("- Config validation only");
lines.push("- No cloud APIs");
lines.push("- No SQL execution");
lines.push("");

fs.writeFileSync(reportMdPath, lines.join("\n"), "utf-8");

console.log("DLI client doctor complete.");
console.log(`Healthy: ${result.healthy ? "YES" : "NO"}`);
console.log(`Client Interface: ${result.client_interface_valid ? "VALID" : "INVALID"}`);
console.log(`Region: ${result.config.region || "NOT SET"}`);
console.log(`Project ID: ${result.config.project_id || "NOT SET"}`);
console.log(`DLI Queue: ${result.config.dli_queue || "default"}`);
console.log(`.env.dataarts: ${result.env_file_status || "unknown"}`);
if (result.source_map) {
  for (const [key, source] of Object.entries(result.source_map)) {
    console.log(`  ${key} from ${source}`);
  }
}
console.log("Safety: config validation only, no cloud APIs, no SQL execution.");

process.exit(result.healthy ? 0 : 1);
