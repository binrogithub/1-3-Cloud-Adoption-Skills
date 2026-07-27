const crypto = require("crypto");

function generateRunId(now = new Date()) {
  const timestamp = now.toISOString().replace(/[-:T]/g, "").slice(0, 15);
  const randomSuffix = crypto.randomBytes(4).toString("hex");
  return `run_${timestamp}_${randomSuffix}`;
}

function isValidRunId(runId) {
  return /^run_\d{14}\._[a-f0-9]{8}$/.test(String(runId ?? ""));
}

module.exports = {
  generateRunId,
  isValidRunId,
};
