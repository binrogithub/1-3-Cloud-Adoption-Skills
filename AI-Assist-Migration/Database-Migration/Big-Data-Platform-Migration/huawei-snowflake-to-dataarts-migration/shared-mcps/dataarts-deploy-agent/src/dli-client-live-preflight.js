const fs = require("fs");
const path = require("path");
const { runDliLiveReadOnlyPreflight } = require("./runtime/dli/dli-live-preflight");

function parseArgs(argv) {
  const args = argv.slice(2);
  const result = { dliQueue: "default", readOnly: false };

  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--dli-queue" && i + 1 < args.length) {
      result.dliQueue = args[i + 1];
      i++;
    } else if (args[i] === "--read-only") {
      result.readOnly = true;
    }
  }

  return result;
}

async function main() {
  const { dliQueue, readOnly } = parseArgs(process.argv);

  const result = await runDliLiveReadOnlyPreflight({ dliQueue, readOnly });

  const outDir = path.resolve("out");
  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true });
  }

  const resultJsonPath = path.join(outDir, "dli_live_preflight_result.json");
  const reportMdPath = path.join(outDir, "dli_live_preflight_report.md");

  fs.writeFileSync(resultJsonPath, JSON.stringify(result, null, 2), "utf-8");

  const lines = [];
  lines.push("# DLI Live Read-Only Preflight Report");
  lines.push("");
  lines.push("> **READ-ONLY** — No SQL executed. No runtime execution. No cloud write calls. No confirm.");
  lines.push("");
  lines.push("## Summary");
  lines.push("");
  lines.push(`**Status:** ${result.status}`);
  lines.push(`**Healthy:** ${result.healthy ? "YES" : "NO"}`);
  lines.push(`**Read-only:** ${result.read_only ? "YES" : "NO"}`);
  lines.push(`**Region:** ${result.region || "NOT SET"}`);
  lines.push(`**Project ID:** ${result.project_id || "NOT SET"}`);
  lines.push(`**Queue:** ${result.queue_name || dliQueue}`);
  lines.push(`**Credentials present:** ${result.credentials_present !== undefined ? (result.credentials_present ? "YES" : "NO") : "NOT CHECKED"}`);
  lines.push(`**Queue accessible:** ${result.queue_accessible !== undefined ? (result.queue_accessible ? "YES" : "NO") : "NOT CHECKED"}`);
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

  if (result.live_checks && result.live_checks.length > 0) {
    lines.push("## Live Checks");
    lines.push("");
    lines.push("| Check | Status |");
    lines.push("|-------|--------|");
    for (const c of result.live_checks) {
      lines.push(`| ${c.name} | ${c.status} |`);
    }
    lines.push("");
  }

  if (result.findings && result.findings.length > 0) {
    lines.push("## Findings");
    lines.push("");
    for (const f of result.findings) {
      lines.push(`- ${f}`);
    }
    lines.push("");
  }

  if (result.warnings && result.warnings.length > 0) {
    lines.push("## Warnings");
    lines.push("");
    for (const w of result.warnings) {
      lines.push(`- ${w}`);
    }
    lines.push("");
  }

  lines.push("## Safety");
  lines.push("");
  lines.push("- Read-only only");
  lines.push("- No SQL execution");
  lines.push("- No runtime execution");
  lines.push("- No cloud write calls");
  lines.push("- No confirm");
  lines.push("- Secrets redacted");
  lines.push("");

  fs.writeFileSync(reportMdPath, lines.join("\n"), "utf-8");

  console.log("DLI live read-only preflight complete.");
  console.log(`Healthy: ${result.healthy ? "YES" : "NO"}`);
  console.log(`Region: ${result.region || "NOT SET"}`);
  console.log(`Project ID: ${result.project_id || "NOT SET"}`);
  console.log(`Queue: ${result.queue_name || dliQueue}`);
  console.log(`Queue accessible: ${result.queue_accessible ? "YES" : (result.queue_accessible === false ? "NO" : "NOT CHECKED")}`);
  console.log(`.env.dataarts: ${result.env_file_status || "unknown"}`);
  if (result.source_map) {
    for (const [key, source] of Object.entries(result.source_map)) {
      console.log(`  ${key} from ${source}`);
    }
  }
  console.log("Safety: read-only only, no SQL execution, no runtime execution, no cloud write calls.");

  process.exit(result.healthy ? 0 : 1);
}

main().catch((err) => {
  console.error(`DLI live preflight failed: ${err.message}`);
  process.exit(1);
});
