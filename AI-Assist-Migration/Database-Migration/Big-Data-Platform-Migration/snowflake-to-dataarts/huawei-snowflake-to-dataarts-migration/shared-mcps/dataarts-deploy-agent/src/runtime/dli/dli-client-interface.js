const REQUIRED_DLI_CLIENT_METHODS = [
  "executeSql",
  "querySql",
  "getJobStatus",
  "getJobResult",
];

function assertDliClient(client) {
  if (!client || typeof client !== "object") {
    throw new Error("DLI client must be a non-null object");
  }

  const missing = [];
  for (const method of REQUIRED_DLI_CLIENT_METHODS) {
    if (typeof client[method] !== "function") {
      missing.push(method);
    }
  }

  if (missing.length > 0) {
    throw new Error(
      `DLI client is missing required methods: ${missing.join(", ")}. Required: ${REQUIRED_DLI_CLIENT_METHODS.join(", ")}`
    );
  }

  return true;
}

function createUnsupportedDliClient() {
  const errorMsg = "Real DLI client is not configured. Use mock client or implement real adapter.";

  return {
    executeSql() {
      throw new Error(errorMsg);
    },
    querySql() {
      throw new Error(errorMsg);
    },
    getJobStatus() {
      throw new Error(errorMsg);
    },
    getJobResult() {
      throw new Error(errorMsg);
    },
  };
}

module.exports = {
  REQUIRED_DLI_CLIENT_METHODS,
  assertDliClient,
  createUnsupportedDliClient,
};
