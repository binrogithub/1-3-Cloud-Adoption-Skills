import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { spawn } from "node:child_process";
import { readFile, readdir, stat, mkdir, writeFile } from "node:fs/promises";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { existsSync, openSync, createWriteStream } from "node:fs";
import { config } from "dotenv";
import crypto from "node:crypto";

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT_DIR = join(__dirname, "out");
const RUNS_DIR = join(OUT_DIR, "runs");

const SECRET_PATTERNS = [
  /HUAWEI_AK[=:]\s*\S+/gi,
  /HUAWEI_SK[=:]\s*\S+/gi,
  /AK[=:]\s*\S+/gi,
  /SK[=:]\s*\S+/gi,
  /secret[_-]?key[=:]\s*\S+/gi,
  /access[_-]?key[=:]\s*\S+/gi,
  /password[=:]\s*\S+/gi,
  /token[=:]\s*\S+/gi,
];

function scrubSecrets(text) {
  let safe = text;
  for (const pat of SECRET_PATTERNS) {
    safe = safe.replace(pat, (m) => {
      const eqIdx = m.search(/[=:]/);
      if (eqIdx < 0) return "***REDACTED***";
      return m.slice(0, eqIdx + 1) + " ***REDACTED***";
    });
  }
  return safe;
}

function runCommand(cmd, args = [], envOverrides = {}) {
  return new Promise((resolve) => {
    const child = spawn(cmd, args, {
      cwd: __dirname,
      shell: true,
      env: { ...process.env, ...envOverrides },
      stdio: ["ignore", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (d) => { stdout += d.toString(); });
    child.stderr.on("data", (d) => { stderr += d.toString(); });

    child.on("close", (code) => {
      resolve({
        exitCode: code ?? 1,
        stdout: scrubSecrets(stdout),
        stderr: scrubSecrets(stderr),
      });
    });

    child.on("error", (err) => {
      resolve({
        exitCode: 1,
        stdout: "",
        stderr: err.message,
      });
    });
  });
}

function summarizeOutput(stdout, maxLen = 2000) {
  const lines = stdout.trim().split("\n");
  if (lines.length <= 40 && stdout.length <= maxLen) return stdout.trim();
  const head = lines.slice(0, 15).join("\n");
  const tail = lines.slice(-15).join("\n");
  return `${head}\n\n... [${lines.length - 30} lines omitted] ...\n\n${tail}`;
}

async function readJsonFile(relPath) {
  try {
    const raw = await readFile(join(OUT_DIR, relPath), "utf-8");
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

async function readTextFile(relPath) {
  try {
    return await readFile(join(OUT_DIR, relPath), "utf-8");
  } catch {
    return null;
  }
}

async function readJsonFileAbs(absPath) {
  try {
    const raw = await readFile(absPath, "utf-8");
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

async function readTextFileAbs(absPath) {
  try {
    return await readFile(absPath, "utf-8");
  } catch {
    return null;
  }
}

function readEnvSafely() {
  const envPath = join(__dirname, ".env.dataarts");
  if (!existsSync(envPath)) return null;
  try {
    const result = config({ path: envPath });
    return result.parsed || null;
  } catch {
    return null;
  }
}

async function findLatestRunForJob(jobName) {
  if (!existsSync(RUNS_DIR)) return null;
  try {
    const entries = await readdir(RUNS_DIR);
    const runDirs = [];
    for (const entry of entries) {
      const p = join(RUNS_DIR, entry);
      const s = await stat(p);
      if (s.isDirectory()) runDirs.push({ name: entry, mtime: s.mtimeMs });
    }
    runDirs.sort((a, b) => b.mtime - a.mtime);

    for (const rd of runDirs) {
      const resultPath = join(RUNS_DIR, rd.name, "demo_one_shot_result.json");
      if (existsSync(resultPath)) {
        try {
          const raw = await readFile(resultPath, "utf-8");
          const data = JSON.parse(raw);
          if (data.job_name === jobName) return data;
        } catch {}
      }
    }
  } catch {}
  return null;
}

function generateRunId() {
  const ts = new Date().toISOString().replace(/[-:T]/g, "").slice(0, 15);
  const rand = crypto.randomBytes(4).toString("hex");
  return `run_${ts}_${rand}`;
}

async function ensureDir(dir) {
  if (!existsSync(dir)) {
    await mkdir(dir, { recursive: true });
  }
}

const server = new McpServer({
  name: "dataarts-deploy-agent",
  version: "0.2.0",
});

server.tool(
  "snowflake_dataarts_demo_plan",
  "Runs the one-shot plan only (read-only). Accepts dynamic job_name, artifact_dir, and dli_queue. Executes npm run demo:one-shot:plan with --job-name, --artifacts-dir, --dli-queue and returns status, output summary, and paths to the plan report and result files.",
  {
    job_name: z.string().describe("DataArts job name for this migration run"),
    artifact_dir: z.string().describe("Path to the migration artifacts directory"),
    dli_queue: z.string().optional().describe("DLI queue name (defaults to 'default')"),
  },
  async ({ job_name, artifact_dir, dli_queue }) => {
    const cliArgs = ["run", "demo:one-shot:plan", "--", "--job-name", job_name, "--artifacts-dir", artifact_dir];
    if (dli_queue) cliArgs.push("--dli-queue", dli_queue);

    const result = await runCommand("npm", cliArgs);
    const summary = summarizeOutput(result.stdout + "\n" + result.stderr);

    const planResult = await readJsonFile("demo_one_shot_plan_result.json");
    const status = planResult?.status ?? (result.exitCode === 0 ? "PLAN_COMPLETE" : "PLAN_FAILED");

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            status,
            exit_code: result.exitCode,
            command_output_summary: summary,
            plan_report_path: "out/demo_one_shot_plan_report.md",
            plan_result_path: "out/demo_one_shot_plan_result.json",
            job_name: planResult?.job_name ?? job_name,
            artifact_dir: planResult?.artifact_dir ?? artifact_dir,
            dli_queue: planResult?.dli_queue ?? dli_queue ?? "default",
            planned_steps: planResult?.planned_commands?.length ?? null,
            safety: planResult?.safety ?? null,
          }, null, 2),
        },
      ],
    };
  }
);

server.tool(
  "snowflake_dataarts_demo_run",
  "Runs the full one-shot demo flow SYNCHRONOUSLY (may time out for long-running jobs). Requires confirm=true to execute. Accepts dynamic job_name, artifact_dir, and dli_queue. Executes npm run demo:one-shot with --confirm and dynamic args, passing env overrides to child processes. For long-running demos, prefer snowflake_dataarts_demo_start (async) instead.",
  {
    confirm: z.boolean().describe("Must be true to execute the demo. Aborts safely if false or omitted."),
    job_name: z.string().describe("DataArts job name for this migration run"),
    artifact_dir: z.string().describe("Path to the migration artifacts directory"),
    dli_queue: z.string().optional().describe("DLI queue name (defaults to 'default')"),
  },
  async ({ confirm, job_name, artifact_dir, dli_queue }) => {
    if (!confirm) {
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({
              status: "ABORTED",
              reason: "confirm is not true. Pass confirm=true to execute the demo.",
            }, null, 2),
          },
        ],
      };
    }

    const cliArgs = ["run", "demo:one-shot", "--", "--confirm", "--job-name", job_name, "--artifacts-dir", artifact_dir];
    if (dli_queue) cliArgs.push("--dli-queue", dli_queue);

    const envOverrides = {
      DATAARTS_JOB_NAME: job_name,
      DATAARTS_ARTIFACTS_DIR: artifact_dir,
      DLI_QUEUE_NAME: dli_queue || "default",
    };

    const result = await runCommand("npm", cliArgs, envOverrides);
    const summary = summarizeOutput(result.stdout + "\n" + result.stderr);

    if (result.exitCode !== 0) {
      const demoResult = await readJsonFile("demo_one_shot_result.json");
      const failedCommand = demoResult?.failed_command ?? null;
      const staleDetected = demoResult?.stale_result_detected ?? false;

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({
              status: "FAILED",
              exit_code: result.exitCode,
              command_output_summary: summary,
              report_path: "out/demo_one_shot_report.md",
              result_path: "out/demo_one_shot_result.json",
              job_name: demoResult?.job_name ?? job_name,
              failed_command: failedCommand,
              stale_result_detected: staleDetected,
              instance_id: null,
              final_equivalence: "NOT_EVALUATED",
              runtime_validate_status: "NOT_EVALUATED",
              safety: demoResult?.safety ?? null,
              no_secrets_included: true,
            }, null, 2),
          },
        ],
      };
    }

    const demoResult = await readJsonFile("demo_one_shot_result.json");
    const status = demoResult?.status ?? "COMPLETE";

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            status,
            exit_code: result.exitCode,
            command_output_summary: summary,
            report_path: "out/demo_one_shot_report.md",
            result_path: "out/demo_one_shot_result.json",
            job_name: demoResult?.job_name ?? job_name,
            instance_id: demoResult?.instance_id ?? null,
            final_equivalence: demoResult?.final_equivalence ?? null,
            runtime_validate_status: demoResult?.runtime_validate_status ?? null,
            stale_result_detected: demoResult?.stale_result_detected ?? false,
            run_id: demoResult?.run_id ?? null,
            safety: demoResult?.safety ?? null,
            no_secrets_included: demoResult?.no_secrets_included ?? null,
          }, null, 2),
        },
      ],
    };
  }
);

server.tool(
  "snowflake_dataarts_demo_start",
  "Starts the one-shot demo ASYNCHRONOUSLY in the background. Returns immediately with status=STARTED, run_id, and instructions to poll snowflake_dataarts_demo_status. Requires confirm=true. Use this instead of snowflake_dataarts_demo_run for long-running demos that may exceed MCP timeout.",
  {
    confirm: z.boolean().describe("Must be true to start the demo. Aborts safely if false or omitted."),
    job_name: z.string().describe("DataArts job name for this migration run"),
    artifact_dir: z.string().describe("Path to the migration artifacts directory"),
    dli_queue: z.string().optional().describe("DLI queue name (defaults to 'default')"),
  },
  async ({ confirm, job_name, artifact_dir, dli_queue }) => {
    if (!confirm) {
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({
              status: "ABORTED",
              reason: "confirm is not true. Pass confirm=true to start the demo.",
            }, null, 2),
          },
        ],
      };
    }

    const runId = generateRunId();
    const runDir = join(RUNS_DIR, runId);
    await ensureDir(runDir);

    const currentRun = {
      run_id: runId,
      job_name,
      artifact_dir,
      dli_queue: dli_queue || "default",
      started_at: new Date().toISOString(),
      status: "STARTED",
      current_step: 0,
      current_step_name: "spawning",
      completed_steps: [],
      failed_step: null,
      failed_step_name: null,
    };

    await writeFile(join(runDir, "current_run.json"), JSON.stringify(currentRun, null, 2), "utf-8");
    await ensureDir(OUT_DIR);
    await writeFile(join(OUT_DIR, "current_run.json"), JSON.stringify(currentRun, null, 2), "utf-8");

    const cliArgs = ["run", "demo:one-shot", "--", "--confirm", "--job-name", job_name, "--artifacts-dir", artifact_dir];
    if (dli_queue) cliArgs.push("--dli-queue", dli_queue);

    const envOverrides = {
      DATAARTS_JOB_NAME: job_name,
      DATAARTS_ARTIFACTS_DIR: artifact_dir,
      DLI_QUEUE_NAME: dli_queue || "default",
    };

    const stdoutPath = join(runDir, "mcp_async_stdout.log");
    const stderrPath = join(runDir, "mcp_async_stderr.log");

    const stdoutFd = openSync(stdoutPath, "a");
    const stderrFd = openSync(stderrPath, "a");

    const child = spawn("npm", cliArgs, {
      cwd: __dirname,
      shell: true,
      env: { ...process.env, ...envOverrides },
      stdio: ["ignore", stdoutFd, stderrFd],
      detached: true,
    });

    child.unref();

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            status: "STARTED",
            run_id: runId,
            job_name,
            artifact_dir,
            dli_queue: dli_queue || "default",
            current_run_path: "out/current_run.json",
            run_dir: `out/runs/${runId}/`,
            stdout_log: `out/runs/${runId}/mcp_async_stdout.log`,
            stderr_log: `out/runs/${runId}/mcp_async_stderr.log`,
            next_step: "Call snowflake_dataarts_demo_status with run_id or job_name to poll progress.",
            polling_example: { tool: "snowflake_dataarts_demo_status", args: { run_id: runId } },
            safety: {
              no_secrets_included: true,
              background_process: true,
              detached: true,
            },
          }, null, 2),
        },
      ],
    };
  }
);

server.tool(
  "snowflake_dataarts_demo_status",
  "Reads demo run status. Accepts optional run_id and/or job_name. If run_id is provided, reads from out/runs/<run_id>/. Otherwise reads from out/current_run.json and out/demo_one_shot_result.json. Returns status, current_step, failed_command, instance_id, final_equivalence, and safety flags. Detects stale results.",
  {
    run_id: z.string().optional().describe("Optional run_id to check a specific run's status."),
    job_name: z.string().optional().describe("Optional job name to check result against. If provided, detects stale results for a different job."),
  },
  async ({ run_id, job_name }) => {
    let currentRun = null;
    let demoResult = null;
    let runDir = null;

    if (run_id) {
      runDir = join(RUNS_DIR, run_id);
      currentRun = await readJsonFileAbs(join(runDir, "current_run.json"));
      demoResult = await readJsonFileAbs(join(runDir, "demo_one_shot_result.json"));
    }

    if (!currentRun) {
      currentRun = await readJsonFile("current_run.json");
    }
    if (!demoResult) {
      demoResult = await readJsonFile("demo_one_shot_result.json");
    }

    const responseBase = {
      run_id: currentRun?.run_id ?? demoResult?.run_id ?? run_id ?? null,
      job_name: currentRun?.job_name ?? demoResult?.job_name ?? job_name ?? null,
      status: null,
      current_step: null,
      current_step_name: null,
      completed_steps: null,
      failed_step: null,
      failed_step_name: null,
      instance_id: null,
      runtime_validate_status: null,
      final_equivalence: null,
      stale_result_detected: false,
      failed_command: null,
      safety: null,
      no_secrets_included: null,
      timestamp: null,
    };

    if (!currentRun && !demoResult) {
      return {
        content: [
          { type: "text", text: JSON.stringify({ ...responseBase, status: "NO_RUN_FOUND" }, null, 2) },
        ],
      };
    }

    if (currentRun) {
      responseBase.current_step = currentRun.current_step ?? null;
      responseBase.current_step_name = currentRun.current_step_name ?? null;
      responseBase.completed_steps = currentRun.completed_steps ?? null;
      responseBase.failed_step = currentRun.failed_step ?? null;
      responseBase.failed_step_name = currentRun.failed_step_name ?? null;
      responseBase.run_id = currentRun.run_id ?? responseBase.run_id;
      responseBase.job_name = currentRun.job_name ?? responseBase.job_name;
    }

    const requestedJobName = job_name || null;
    const resultJobName = demoResult?.job_name || currentRun?.job_name || null;

    if (requestedJobName && resultJobName && requestedJobName !== resultJobName) {
      responseBase.status = "STATUS_STALE_FOR_REQUESTED_JOB";
      responseBase.requested_job_name = requestedJobName;
      responseBase.result_job_name = resultJobName;
      responseBase.message = "Result does not belong to the requested job.";
      if (demoResult) {
        responseBase.instance_id = demoResult.instance_id;
        responseBase.runtime_validate_status = demoResult.runtime_validate_status;
        responseBase.final_equivalence = demoResult.final_equivalence;
        responseBase.stale_result_detected = demoResult.stale_result_detected ?? false;
        responseBase.timestamp = demoResult.timestamp;
      }
      return {
        content: [
          { type: "text", text: JSON.stringify(responseBase, null, 2) },
        ],
      };
    }

    if (!requestedJobName && !run_id) {
      const envParsed = readEnvSafely();
      const envJobName = envParsed?.DATAARTS_JOB_NAME ?? null;
      if (envJobName && resultJobName && envJobName !== resultJobName) {
        responseBase.status = "STATUS_STALE_FOR_CURRENT_ENV";
        responseBase.current_job_name = envJobName;
        responseBase.result_job_name = resultJobName;
        responseBase.message = "Result does not belong to current .env.dataarts job.";
        if (demoResult) {
          responseBase.instance_id = demoResult.instance_id;
          responseBase.runtime_validate_status = demoResult.runtime_validate_status;
          responseBase.final_equivalence = demoResult.final_equivalence;
          responseBase.stale_result_detected = demoResult.stale_result_detected ?? false;
          responseBase.timestamp = demoResult.timestamp;
        }
        return {
          content: [
            { type: "text", text: JSON.stringify(responseBase, null, 2) },
          ],
        };
      }
    }

    if (demoResult) {
      responseBase.status = demoResult.status;
      responseBase.instance_id = demoResult.instance_id ?? null;
      responseBase.runtime_validate_status = demoResult.runtime_validate_status ?? null;
      responseBase.final_equivalence = demoResult.final_equivalence ?? null;
      responseBase.stale_result_detected = demoResult.stale_result_detected ?? false;
      responseBase.failed_command = demoResult.failed_command || null;
      responseBase.safety = demoResult.safety;
      responseBase.no_secrets_included = demoResult.no_secrets_included;
      responseBase.timestamp = demoResult.timestamp;
    } else if (currentRun) {
      responseBase.status = currentRun.status;
    }

    return {
      content: [
        { type: "text", text: JSON.stringify(responseBase, null, 2) },
      ],
    };
  }
);

server.tool(
  "snowflake_dataarts_demo_last_report",
  "Reads the demo report markdown. If run_id is provided, reads from out/runs/<run_id>/demo_one_shot_report.md. If job_name is provided, finds the latest run for that job. Falls back to out/demo_one_shot_report.md. Returns the report content with secrets scrubbed.",
  {
    run_id: z.string().optional().describe("Optional run_id to find a specific run report."),
    job_name: z.string().optional().describe("Optional job_name to find the latest report for that job."),
  },
  async ({ run_id, job_name }) => {
    if (run_id) {
      const runReportPath = join(RUNS_DIR, run_id, "demo_one_shot_report.md");
      if (existsSync(runReportPath)) {
        try {
          const raw = await readFile(runReportPath, "utf-8");
          return {
            content: [
              { type: "text", text: scrubSecrets(raw) },
            ],
          };
        } catch {}
      }
    }

    if (job_name) {
      const jobResult = await findLatestRunForJob(job_name);
      if (jobResult?.run_id) {
        const runReportPath = join(RUNS_DIR, jobResult.run_id, "demo_one_shot_report.md");
        if (existsSync(runReportPath)) {
          try {
            const raw = await readFile(runReportPath, "utf-8");
            return {
              content: [
                { type: "text", text: scrubSecrets(raw) },
              ],
            };
          } catch {}
        }
      }
    }

    const raw = await readTextFile("demo_one_shot_report.md");

    if (!raw) {
      return {
        content: [
          { type: "text", text: "NO_REPORT_FOUND" },
        ],
      };
    }

    return {
      content: [
        { type: "text", text: scrubSecrets(raw) },
      ],
    };
  }
);

server.tool(
  "snowflake_dataarts_demo_equivalence_summary",
  "Generates an equivalence summary table comparing Snowflake expected results vs DataArts/DLI actual results from local runtime validation files. Read-only: no Huawei Cloud APIs, no DLI SQL, no job execution. Accepts optional run_id and job_name.",
  {
    run_id: z.string().optional().describe("Optional run_id to read results from a specific run."),
    job_name: z.string().optional().describe("Optional job_name to validate result belongs to this job."),
  },
  async ({ run_id, job_name }) => {
    const cliArgs = ["run", "demo:equivalence-summary", "--"];
    if (run_id) cliArgs.push("--run-id", run_id);
    if (job_name) cliArgs.push("--job-name", job_name);

    const result = await runCommand("npm", cliArgs);
    const summary = summarizeOutput(result.stdout + "\n" + result.stderr);

    let reportPath = "out/equivalence_summary_report.md";
    let resultPath = "out/equivalence_summary_result.json";

    if (run_id) {
      const runReportPath = join(RUNS_DIR, run_id, "equivalence_summary_report.md");
      const runResultPath = join(RUNS_DIR, run_id, "equivalence_summary_result.json");
      if (existsSync(runReportPath)) reportPath = `out/runs/${run_id}/equivalence_summary_report.md`;
      if (existsSync(runResultPath)) resultPath = `out/runs/${run_id}/equivalence_summary_result.json`;
    }

    const equivResult = await readJsonFileAbs(join(OUT_DIR, "equivalence_summary_result.json"));
    if (run_id) {
      const runEquivResult = await readJsonFileAbs(join(RUNS_DIR, run_id, "equivalence_summary_result.json"));
      if (runEquivResult) Object.assign(equivResult, runEquivResult);
    }

    const markdownTable = await readTextFileAbs(join(OUT_DIR, "equivalence_summary_report.md"));

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            status: equivResult?.status ?? (result.exitCode === 0 ? "EQUIVALENT" : "NOT_EQUIVALENT"),
            job_name: equivResult?.job_name ?? job_name ?? null,
            run_id: equivResult?.run_id ?? run_id ?? null,
            instance_id: equivResult?.instance_id ?? null,
            final_equivalence: equivResult?.final_equivalence ?? null,
            markdown_table: markdownTable ? scrubSecrets(markdownTable) : null,
            report_path: reportPath,
            result_path: resultPath,
            safety: {
              no_publish: true,
              no_start: true,
              no_delete: true,
              no_update: true,
              no_overwrite: true,
              no_huawei_cloud_apis: true,
              no_dli_sql: true,
              no_secrets_printed: true,
              only_local_result_files_read: true,
            },
            no_secrets_included: true,
          }, null, 2),
        },
      ],
    };
  }
);

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((err) => {
  process.stderr.write(`MCP server error: ${err.message}\n`);
  process.exit(1);
});
