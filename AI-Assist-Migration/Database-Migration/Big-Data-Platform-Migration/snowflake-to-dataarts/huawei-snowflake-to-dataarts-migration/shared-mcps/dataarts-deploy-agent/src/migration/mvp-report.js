const path = require("path");
const fs = require("fs");
const { readJsonSafe, ensureDir, writeJson } = require("../core/json-file");

const MVP_VERSION = "0.1";

function readTextSafe(filePath) {
  if (!fs.existsSync(filePath)) return null;
  try {
    return fs.readFileSync(filePath, "utf-8");
  } catch {
    return null;
  }
}

function collectEvidence(options) {
  const { migrationRunId, runtimeRunId, jobName, outDir } = options;

  const outDirResolved = outDir || path.resolve(__dirname, "../../..", "out");
  const runsDir = path.join(outDirResolved, "runs");

  const evidence = {
    migration_execute_result: readJsonSafe(path.join(outDirResolved, "migration_execute_result.json")),
    migration_execute_report: readTextSafe(path.join(outDirResolved, "migration_execute_report.md")),
    demo_one_shot_result: readJsonSafe(path.join(outDirResolved, "demo_one_shot_result.json")),
    demo_one_shot_report: readTextSafe(path.join(outDirResolved, "demo_one_shot_report.md")),
    demo_one_shot_doctor_result: readJsonSafe(path.join(outDirResolved, "demo_one_shot_doctor_result.json")),
    equivalence_summary_result: readJsonSafe(path.join(outDirResolved, "equivalence_summary_result.json")),
    equivalence_summary_report: readTextSafe(path.join(outDirResolved, "equivalence_summary_report.md")),
  };

  if (runtimeRunId) {
    const runDir = path.join(runsDir, runtimeRunId);
    evidence.runtime_run_dir = runDir;
    evidence.runtime_demo_one_shot_result = readJsonSafe(path.join(runDir, "demo_one_shot_result.json"));
    evidence.runtime_demo_one_shot_report = readTextSafe(path.join(runDir, "demo_one_shot_report.md"));
    evidence.runtime_current_run = readJsonSafe(path.join(runDir, "current_run.json"));
    evidence.runtime_validate_result = readJsonSafe(path.join(runDir, "runtime_validate_result.json"));
    evidence.runtime_run_immediate_result = readJsonSafe(path.join(runDir, "run_immediate_job_result.json"));
  }

  return evidence;
}

function resolveMvpStatus(evidence) {
  const demoResult = evidence.runtime_demo_one_shot_result || evidence.demo_one_shot_result;
  const doctorResult = evidence.demo_one_shot_doctor_result;

  const runtimeValidateStatus = demoResult?.runtime_validate_status || null;
  const finalEquivalence = demoResult?.final_equivalence || null;
  const staleResultDetected = demoResult?.stale_result_detected ?? null;
  const instanceId = demoResult?.instance_id || null;

  const doctorIsHealthy = doctorResult?.is_healthy ?? doctorResult?.healthy ?? null;
  const doctorFindingsCount = doctorResult?.findings?.length ?? null;
  const doctorWarningsCount = doctorResult?.warnings?.length ?? null;

  const conditions = {
    runtime_validation_pass: runtimeValidateStatus === "PASS",
    equivalence_equivalent: finalEquivalence === "EQUIVALENT",
    doctor_healthy_yes: doctorIsHealthy === true,
    stale_result_false: staleResultDetected === false,
    instance_id_exists: instanceId !== null && instanceId !== undefined,
  };

  const allMet = Object.values(conditions).every(Boolean);
  const status = allMet ? "CONFIRMED" : "NOT_CONFIRMED";

  return {
    status,
    conditions,
    runtime_validate_status: runtimeValidateStatus,
    final_equivalence: finalEquivalence,
    stale_result_detected: staleResultDetected,
    instance_id: instanceId,
    doctor_is_healthy: doctorIsHealthy,
    doctor_findings_count: doctorFindingsCount,
    doctor_warnings_count: doctorWarningsCount,
  };
}

function buildMvpReport(options) {
  const { migrationRunId, runtimeRunId, jobName, outDir } = options;

  const evidence = collectEvidence(options);
  const mvpStatus = resolveMvpStatus(evidence);

  const migrationResult = evidence.migration_execute_result;
  const demoResult = evidence.runtime_demo_one_shot_result || evidence.demo_one_shot_result;

  const dataartsInstanceId = mvpStatus.instance_id;

  const report = {
    mvp_version: MVP_VERSION,
    mvp_status: mvpStatus.status,
    timestamp: new Date().toISOString(),

    executive_summary: mvpStatus.status === "CONFIRMED"
      ? "Migration Framework MVP v0.1 CONFIRMED. All validation conditions met."
      : "Migration Framework MVP v0.1 NOT CONFIRMED. One or more validation conditions not met.",

    architecture: {
      command_path: "migration:execute --confirm --adapter legacy-demo",
      package: "cases/golden/orders_pipeline_simple",
      job_name: jobName || migrationResult?.job_name || null,
      adapter: migrationResult?.adapter || "legacy-demo",
    },

    run_ids: {
      migration_run_id: migrationRunId || migrationResult?.migration_run_id || null,
      runtime_run_id: runtimeRunId || migrationResult?.runtime_run_id || null,
      run_id: migrationResult?.run_id || null,
      dataarts_instance_id: dataartsInstanceId,
    },

    validation: {
      runtime_validate_status: mvpStatus.runtime_validate_status,
      final_equivalence: mvpStatus.final_equivalence,
      stale_result_detected: mvpStatus.stale_result_detected,
      instance_id: mvpStatus.instance_id,
      doctor_is_healthy: mvpStatus.doctor_is_healthy,
      doctor_findings_count: mvpStatus.doctor_findings_count,
      doctor_warnings_count: mvpStatus.doctor_warnings_count,
      conditions: mvpStatus.conditions,
    },

    safety_controls: {
      no_publish: true,
      no_scheduled_start: true,
      no_delete: true,
      no_update: true,
      no_overwrite: true,
      run_immediate_only: true,
    },

    evidence_paths: buildEvidencePaths(outDir, runtimeRunId),

    remaining_limitations: [
      "Only adapter=legacy-demo is supported for confirm execution",
      "KooCLI adapter is dry-run only",
      "Runtime engine adapter is dry-run only",
      "No automated rollback on partial failure",
      "No multi-package migration support",
      "Equivalence validation is row-count and schema-based only",
    ],

    next_roadmap: [
      "v0.2: KooCLI adapter confirm support",
      "v0.2: Runtime engine confirm support",
      "v0.3: Multi-package migration orchestration",
      "v0.3: Automated rollback on partial failure",
      "v0.4: Data-content equivalence validation",
      "v0.4: Incremental migration support",
    ],
  };

  return { report, evidence, mvpStatus };
}

function buildEvidencePaths(outDir, runtimeRunId) {
  const outDirResolved = outDir || path.resolve(__dirname, "../../..", "out");

  const paths = {
    migration_execute_result: path.join(outDirResolved, "migration_execute_result.json"),
    migration_execute_report: path.join(outDirResolved, "migration_execute_report.md"),
    demo_one_shot_result: path.join(outDirResolved, "demo_one_shot_result.json"),
    demo_one_shot_report: path.join(outDirResolved, "demo_one_shot_report.md"),
    demo_one_shot_doctor_result: path.join(outDirResolved, "demo_one_shot_doctor_result.json"),
    equivalence_summary_result: path.join(outDirResolved, "equivalence_summary_result.json"),
    equivalence_summary_report: path.join(outDirResolved, "equivalence_summary_report.md"),
  };

  if (runtimeRunId) {
    paths.runtime_run_dir = path.join(outDirResolved, "runs", runtimeRunId);
  }

  return paths;
}

function renderMarkdown(report) {
  const lines = [];

  lines.push("# Migration Framework MVP v0.1 Report");
  lines.push("");
  lines.push(`**MVP Status:** ${report.mvp_status}`);
  lines.push(`**Timestamp:** ${report.timestamp}`);
  lines.push(`**MVP Version:** ${report.mvp_version}`);
  lines.push("");

  lines.push("## Executive Summary");
  lines.push("");
  lines.push(report.executive_summary);
  lines.push("");

  lines.push("## Architecture");
  lines.push("");
  lines.push(`- **Command Path:** \`${report.architecture.command_path}\``);
  lines.push(`- **Package:** \`${report.architecture.package}\``);
  lines.push(`- **Job Name:** ${report.architecture.job_name || "N/A"}`);
  lines.push(`- **Adapter:** ${report.architecture.adapter || "N/A"}`);
  lines.push("");

  lines.push("## Run IDs");
  lines.push("");
  lines.push("| Field | Value |");
  lines.push("|-------|-------|");
  lines.push(`| migration_run_id | ${report.run_ids.migration_run_id || "N/A"} |`);
  lines.push(`| runtime_run_id | ${report.run_ids.runtime_run_id || "N/A"} |`);
  lines.push(`| run_id (legacy) | ${report.run_ids.run_id || "N/A"} |`);
  lines.push(`| dataarts_instance_id | ${report.run_ids.dataarts_instance_id || "N/A"} |`);
  lines.push("");

  lines.push("## Validation Summary");
  lines.push("");
  lines.push("| Condition | Met |");
  lines.push("|-----------|-----|");
  for (const [key, value] of Object.entries(report.validation.conditions)) {
    lines.push(`| ${key} | ${value ? "YES" : "NO"} |`);
  }
  lines.push("");
  lines.push("| Field | Value |");
  lines.push("|-------|-------|");
  lines.push(`| runtime_validate_status | ${report.validation.runtime_validate_status || "N/A"} |`);
  lines.push(`| final_equivalence | ${report.validation.final_equivalence || "N/A"} |`);
  lines.push(`| stale_result_detected | ${report.validation.stale_result_detected ?? "N/A"} |`);
  lines.push(`| instance_id | ${report.validation.instance_id || "N/A"} |`);
  lines.push(`| doctor_is_healthy | ${report.validation.doctor_is_healthy ?? "N/A"} |`);
  lines.push(`| doctor_findings_count | ${report.validation.doctor_findings_count ?? "N/A"} |`);
  lines.push(`| doctor_warnings_count | ${report.validation.doctor_warnings_count ?? "N/A"} |`);
  lines.push("");

  lines.push("## Safety Controls");
  lines.push("");
  for (const [key, value] of Object.entries(report.safety_controls)) {
    lines.push(`- ${key}: ${value ? "YES" : "NO"}`);
  }
  lines.push("");

  lines.push("## Evidence Paths");
  lines.push("");
  for (const [key, value] of Object.entries(report.evidence_paths)) {
    lines.push(`- **${key}:** \`${value}\``);
  }
  lines.push("");

  lines.push("## MVP Completion Statement");
  lines.push("");
  if (report.mvp_status === "CONFIRMED") {
    lines.push("**Migration Framework MVP v0.1 is CONFIRMED.**");
    lines.push("");
    lines.push("All validation conditions are met:");
    lines.push("- Runtime validation: PASS");
    lines.push("- Equivalence: EQUIVALENT");
    lines.push("- Doctor: Healthy");
    lines.push("- Stale result: No");
    lines.push("- Instance ID: Present");
    lines.push("");
    lines.push("The Snowflake-to-Huawei DataArts migration pipeline is functionally equivalent.");
  } else {
    lines.push("**Migration Framework MVP v0.1 is NOT CONFIRMED.**");
    lines.push("");
    lines.push("One or more validation conditions are not met. See the Validation Summary table above.");
  }
  lines.push("");

  lines.push("## Remaining Limitations");
  lines.push("");
  for (const lim of report.remaining_limitations) {
    lines.push(`- ${lim}`);
  }
  lines.push("");

  lines.push("## Next Roadmap");
  lines.push("");
  for (const item of report.next_roadmap) {
    lines.push(`- ${item}`);
  }
  lines.push("");

  return lines.join("\n");
}

function writeMvpReport(report, outDir) {
  const mvpDir = path.join(outDir || path.resolve(__dirname, "../../..", "out"), "mvp");
  ensureDir(mvpDir);

  const resultPath = path.join(mvpDir, "migration_framework_mvp_v0_1_result.json");
  const reportPath = path.join(mvpDir, "migration_framework_mvp_v0_1_report.md");

  writeJson(resultPath, report);
  const md = renderMarkdown(report);
  fs.writeFileSync(reportPath, md, "utf-8");

  return { resultPath, reportPath };
}

module.exports = {
  buildMvpReport,
  resolveMvpStatus,
  collectEvidence,
  renderMarkdown,
  writeMvpReport,
  MVP_VERSION,
};
