const fs = require("fs");
const path = require("path");
const { checkDliQueueHealth, buildDliQueueHealthSafetyPolicy } = require("./runtime/dli/dli-queue-health");

function parseArgs(argv) {
  const args = argv.slice(2);
  const result = { dliQueue: "default", readOnly: false };

  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--dli-queue" && i + 1 < args.length) {
      result.dliQueue = args[i + 1];
      i++;
    } else if (args[i] === "--read-only") {
      result.readOnly = true;
    } else if (args[i] === "--max-launching-jobs" && i + 1 < args.length) {
      result.maxLaunchingJobs = parseInt(args[i + 1], 10);
      i++;
    }
  }

  return result;
}

async function main() {
  const { dliQueue, readOnly, maxLaunchingJobs } = parseArgs(process.argv);

  const result = await checkDliQueueHealth({
    queueName: dliQueue,
    readOnly,
    maxLaunchingJobs,
  });

  const outDir = path.resolve("out");
  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true });
  }

  const resultJsonPath = path.join(outDir, "dli_queue_health_result.json");
  const reportMdPath = path.join(outDir, "dli_queue_health_report.md");

  fs.writeFileSync(resultJsonPath, JSON.stringify(result, null, 2), "utf-8");

  const lines = [];
  lines.push("# DLI Queue Health Report");
  lines.push("");
  lines.push("> **READ-ONLY** — No SQL executed. No job cancel. No cloud write calls. No runtime execution.");
  lines.push("");
  lines.push("## Summary");
  lines.push("");
  lines.push(`**Status:** ${result.status}`);
  lines.push(`**Healthy:** ${result.healthy ? "YES" : "NO"}`);
  lines.push(`**Read-only:** ${result.read_only ? "YES" : "NO"}`);
  lines.push(`**Queue:** ${result.queue_name || dliQueue}`);
  lines.push(`**Congested:** ${result.congested ? "YES" : (result.congested === false ? "NO" : "N/A")}`);
  lines.push(`**Total Jobs:** ${result.total_jobs !== null ? result.total_jobs : "N/A"}`);
  lines.push(`**Credentials Present:** ${result.credentials_present !== undefined ? (result.credentials_present ? "YES" : "NO") : "N/A"}`);
  lines.push("");

  if (result.jobs_by_state) {
    lines.push("## Jobs by State");
    lines.push("");
    lines.push("| State | Count |");
    lines.push("|-------|-------|");
    for (const [state, count] of Object.entries(result.jobs_by_state)) {
      lines.push(`| ${state} | ${count} |`);
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
  lines.push("- No job cancel");
  lines.push("- No cloud write calls");
  lines.push("- No runtime execution");
  lines.push("- No confirm");
  lines.push("- Secrets redacted");
  lines.push("");

  fs.writeFileSync(reportMdPath, lines.join("\n"), "utf-8");

  console.log("DLI queue health check complete.");
  console.log(`Healthy: ${result.healthy ? "YES" : "NO"}`);
  console.log(`Queue: ${result.queue_name || dliQueue}`);
  console.log(`Congested: ${result.congested ? "YES" : (result.congested === false ? "NO" : "N/A")}`);
  if (result.jobs_by_state) {
    for (const [state, count] of Object.entries(result.jobs_by_state)) {
      console.log(`  ${state}: ${count}`);
    }
  }
  console.log(`Total jobs: ${result.total_jobs !== null ? result.total_jobs : "N/A"}`);
  console.log("Safety: read-only, no SQL execution, no job cancel, no cloud write calls.");

  process.exit(result.healthy ? 0 : 1);
}

main().catch((err) => {
  console.error(`DLI queue health check failed: ${err.message}`);
  process.exit(1);
});
