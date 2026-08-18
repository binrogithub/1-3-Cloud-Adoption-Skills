import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { access, readFile, writeFile, mkdir } from "node:fs/promises";
import { join } from "node:path";

const execFileAsync = promisify(execFile);

const FORBIDDEN_COMMANDS = ["apply", "destroy"];
const TERRAFORM_TIMEOUT_MS = 120_000;

const SENSITIVE_ENV_VARS = [
  "HW_ACCESS_KEY", "HW_SECRET_KEY",
  "OS_ACCESS_KEY", "OS_SECRET_KEY",
  "TF_VAR_ecs_admin_password", "TF_VAR_rds_password"
];

function sanitizeCommandArgs(args) {
  for (const arg of args) {
    if (FORBIDDEN_COMMANDS.includes(arg)) {
      throw new Error(
        `BLOCKED: "terraform ${arg}" is forbidden in phase 2. ` +
        `This is a safety restriction. No cloud resources will be created, modified, or deleted.`
      );
    }
  }
}

function sanitizeEnvironment(env) {
  const clean = { ...env };
  for (const key of SENSITIVE_ENV_VARS) {
    if (clean[key]) {
      clean[key] = "***REDACTED***";
    }
  }
  return clean;
}

export async function runTerraformCommand(args, workdir, options = {}) {
  const timeout = options.timeout || TERRAFORM_TIMEOUT_MS;
  const commandArgs = Array.isArray(args) ? args : [args];

  sanitizeCommandArgs(commandArgs);

  const auditEntry = {
    timestamp: new Date().toISOString(),
    command: `terraform ${commandArgs.join(" ")}`,
    workdir,
    status: "started"
  };

  try {
    const result = await execFileAsync("terraform", commandArgs, {
      cwd: workdir,
      timeout,
      maxBuffer: 10 * 1024 * 1024,
      env: { ...process.env, TF_DATA_DIR: join(workdir, ".terraform") }
    });

    auditEntry.status = "completed";
    auditEntry.exitCode = 0;

    return {
      success: true,
      exitCode: 0,
      stdout: result.stdout,
      stderr: result.stderr,
      command: auditEntry.command,
      audit: auditEntry
    };
  } catch (error) {
    auditEntry.status = "failed";
    auditEntry.exitCode = error.code || 1;

    return {
      success: false,
      exitCode: error.code || 1,
      stdout: error.stdout || "",
      stderr: error.stderr || error.message,
      command: auditEntry.command,
      audit: auditEntry
    };
  }
}

export async function ensureWorkdir(baseDir, architectureId) {
  const workdir = join(baseDir, sanitizeDirName(architectureId));
  await mkdir(workdir, { recursive: true });
  return workdir;
}

export async function writeTerraformFiles(workdir, files) {
  const written = [];
  for (const [filename, content] of Object.entries(files)) {
    const filepath = join(workdir, filename);
    await writeFile(filepath, content, "utf-8");
    written.push(filepath);
  }
  return written;
}

export async function readTerraformPlan(workdir) {
  const planFile = join(workdir, "tfplan");
  try {
    await access(planFile);
  } catch {
    return null;
  }

  const jsonPlanFile = join(workdir, "tfplan.json");
  try {
    const content = await readFile(jsonPlanFile, "utf-8");
    return JSON.parse(content);
  } catch {
    const result = await runTerraformCommand(
      ["show", "-json", "tfplan"],
      workdir
    );
    if (result.success) {
      try {
        return JSON.parse(result.stdout);
      } catch {
        return null;
      }
    }
    return null;
  }
}

function sanitizeDirName(name) {
  return name.replace(/[^a-zA-Z0-9_-]/g, "_").replace(/_+/g, "_");
}

export { sanitizeCommandArgs, sanitizeEnvironment, FORBIDDEN_COMMANDS };
