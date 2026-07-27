const { execSync } = require("child_process");
const { scrubSecrets } = require("./secret-scrubber");

function tailNonEmptyLines(text, maxLines = 5) {
  return String(text ?? "")
    .split("\n")
    .filter((line) => line.trim())
    .slice(-maxLines);
}

function runShellCommand(commandSpec, options = {}) {
  const {
    cwd = process.cwd(),
    env = process.env,
    timeoutMs = 600000,
    outputTailBytes = 500,
  } = options;

  const startedAt = new Date().toISOString();
  let stdout = "";
  let exitCode = 0;

  try {
    stdout = execSync(commandSpec.cmd, {
      cwd,
      encoding: "utf-8",
      timeout: timeoutMs,
      stdio: ["pipe", "pipe", "pipe"],
      env,
    });
    exitCode = 0;
  } catch (error) {
    stdout = `${error.stdout || ""}${error.stderr || ""}`;
    exitCode = error.status != null ? error.status : 1;
  }

  const endedAt = new Date().toISOString();
  const scrubbedOutput = scrubSecrets(stdout);

  return {
    step: commandSpec.step ?? null,
    name: commandSpec.name ?? commandSpec.cmd,
    command: commandSpec.cmd,
    exit_code: exitCode,
    started_at: startedAt,
    ended_at: endedAt,
    success: exitCode === 0,
    outputTail: scrubbedOutput.slice(-outputTailBytes),
    lastLines: tailNonEmptyLines(scrubbedOutput),
  };
}

module.exports = {
  runShellCommand,
  tailNonEmptyLines,
};
