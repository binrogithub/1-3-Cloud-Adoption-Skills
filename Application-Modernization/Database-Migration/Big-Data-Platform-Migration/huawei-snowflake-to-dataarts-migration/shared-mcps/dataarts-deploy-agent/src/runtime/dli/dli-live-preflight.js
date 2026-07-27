const {
  runReadOnlyDliPreflight,
  createDliLivePreflightSafetyPolicy,
} = require("./real-dli-client");

function runDliLiveReadOnlyPreflight(options = {}) {
  const { dliQueue, readOnly, client, config, envFilePath } = options;

  if (readOnly !== true) {
    const safety = createDliLivePreflightSafetyPolicy();
    return {
      status: "READ_ONLY_FLAG_REQUIRED",
      healthy: false,
      read_only: true,
      queue_name: dliQueue || "default",
      findings: ["--read-only is required for live DLI preflight"],
      warnings: [],
      live_checks: [],
      safety,
    };
  }

  const queueName = dliQueue || "default";

  return runReadOnlyDliPreflight({ queueName, config, client, envFilePath });
}

module.exports = {
  runDliLiveReadOnlyPreflight,
};
