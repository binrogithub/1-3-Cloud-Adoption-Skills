const path = require("path");
const fs = require("fs");
const { runKooCliDoctor } = require("./koocli/koocli-doctor");
const { ensureDir, writeJson } = require("./core/json-file");

const ROOT = path.resolve(__dirname, "..");
const OUT_DIR = path.join(ROOT, "out");

function renderMarkdown(result) {
  const lines = [];

  lines.push("# KooCLI Doctor Report");
  lines.push("");
  lines.push(`**Status:** ${result.status}`);
  lines.push(`**Healthy:** ${result.healthy ? "YES" : "NO"}`);
  lines.push(`**Installed:** ${result.installed ? "YES" : "NO"}`);
  lines.push("");

  if (result.info.length > 0) {
    lines.push("## Info");
    lines.push("");
    for (const i of result.info) {
      lines.push(`- ${i}`);
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

  if (result.diagnostics) {
    lines.push("## Diagnostics Detail");
    lines.push("");
    lines.push(`- Executable: \`${result.diagnostics.executable}\``);
    lines.push(`- Version: ${result.diagnostics.version || "N/A"}`);
    lines.push("");

    lines.push("### Configure Test");
    lines.push("");
    lines.push(`- Attempted: ${result.diagnostics.configure_test.attempted ? "YES" : "NO"}`);
    lines.push(`- Success: ${result.diagnostics.configure_test.success ? "YES" : "NO"}`);
    lines.push(`- Exit Code: ${result.diagnostics.configure_test.exit_code ?? "N/A"}`);
    if (result.diagnostics.configure_test.output_summary) {
      lines.push(`- Output Summary: \`${result.diagnostics.configure_test.output_summary}\``);
    }
    lines.push("");

    lines.push("### Configure List");
    lines.push("");
    lines.push(`- Attempted: ${result.diagnostics.configure_list.attempted ? "YES" : "NO"}`);
    lines.push(`- Success: ${result.diagnostics.configure_list.success ? "YES" : "NO"}`);
    lines.push(`- Exit Code: ${result.diagnostics.configure_list.exit_code ?? "N/A"}`);
    if (result.diagnostics.configure_list.output_summary) {
      lines.push(`- Output Summary: \`${result.diagnostics.configure_list.output_summary}\``);
    }
    lines.push("");
  }

  lines.push("## Safety");
  lines.push("");
  if (result.safety) {
    for (const [key, value] of Object.entries(result.safety)) {
      lines.push(`- ${key}: ${value}`);
    }
  } else {
    lines.push("- No safety policy loaded.");
  }
  lines.push("");

  return lines.join("\n");
}

function main() {
  console.log("=== KooCLI Doctor ===\n");

  const result = runKooCliDoctor();

  ensureDir(OUT_DIR);

  const resultPath = path.join(OUT_DIR, "koocli_doctor_result.json");
  const reportPath = path.join(OUT_DIR, "koocli_doctor_report.md");

  writeJson(resultPath, result);
  fs.writeFileSync(reportPath, renderMarkdown(result), "utf-8");

  console.log("KooCLI doctor complete.");
  console.log(`  Healthy:   ${result.healthy ? "YES" : "NO"}`);
  console.log(`  Installed: ${result.installed ? "YES" : "NO"}`);
  console.log(`  Findings:  ${result.findings.length}`);
  console.log(`  Warnings:  ${result.warnings.length}`);
  console.log("  Safety: diagnostic only, no service API calls, no runtime execution.");

  process.exit(result.healthy ? 0 : 1);
}

main();
