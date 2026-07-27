const crypto = require("crypto");

function hashSql(sql) {
  return crypto.createHash("sha256").update(sql).digest("hex").slice(0, 16);
}

function createMockDliClient(options = {}) {
  const { validationQueries, failStepId, failQueryId } = options;
  const queries = validationQueries || [];
  let jobCounter = 0;

  function nextJobId() {
    jobCounter++;
    return `mock_job_${jobCounter}_${Date.now()}`;
  }

  return {
    executeSql({ sql, queueName, step }) {
      const jobId = nextJobId();
      const sqlHash = hashSql(sql || "");

      if (failStepId && step && step.name === failStepId) {
        return {
          job_id: jobId,
          status: "FAILED",
          statement_type: "EXECUTE_SQL",
          sql_hash: sqlHash,
          simulated: false,
          mocked: true,
          error: `Mock failure for step: ${failStepId}`,
        };
      }

      return {
        job_id: jobId,
        status: "FINISHED",
        statement_type: "EXECUTE_SQL",
        sql_hash: sqlHash,
        simulated: false,
        mocked: true,
      };
    },

    querySql({ sql, queueName, step }) {
      const jobId = nextJobId();
      const sqlHash = hashSql(sql || "");

      if (failQueryId && step && step.name === failQueryId) {
        return {
          job_id: jobId,
          status: "FINISHED",
          statement_type: "QUERY",
          sql_hash: sqlHash,
          mocked: true,
          rows: [{ actual_value: -999 }],
          column_names: ["actual_value"],
        };
      }

      const matchingQuery = queries.find((q) => q.sql === sql) ||
        queries.find((q) => step && q.id === step.name);

      if (!matchingQuery) {
        return {
          job_id: jobId,
          status: "FINISHED",
          statement_type: "QUERY",
          sql_hash: sqlHash,
          mocked: true,
          rows: [],
          column_names: [],
        };
      }

      if (matchingQuery.type === "TABLE_COUNT" || matchingQuery.type === "TASK_AUDIT_SUCCESS") {
        const expectedVal = matchingQuery.expected;
        if (typeof expectedVal === "string" && expectedVal.startsWith(">=")) {
          const minVal = parseInt(expectedVal.slice(2), 10);
          return {
            job_id: jobId,
            status: "FINISHED",
            statement_type: "QUERY",
            sql_hash: sqlHash,
            mocked: true,
            rows: [{ actual_value: minVal }],
            column_names: ["actual_value"],
          };
        }
        return {
          job_id: jobId,
          status: "FINISHED",
          statement_type: "QUERY",
          sql_hash: sqlHash,
          mocked: true,
          rows: [{ actual_value: expectedVal }],
          column_names: ["actual_value"],
        };
      }

      if (matchingQuery.type === "AGGREGATE_CHECK") {
        return {
          job_id: jobId,
          status: "FINISHED",
          statement_type: "QUERY",
          sql_hash: sqlHash,
          mocked: true,
          rows: [matchingQuery.expected],
          column_names: Object.keys(matchingQuery.expected),
        };
      }

      if (matchingQuery.type === "FINAL_EQUIVALENCE") {
        return {
          job_id: jobId,
          status: "FINISHED",
          statement_type: "QUERY",
          sql_hash: sqlHash,
          mocked: true,
          rows: [{ actual_value: matchingQuery.expected }],
          column_names: ["actual_value"],
        };
      }

      return {
        job_id: jobId,
        status: "FINISHED",
        statement_type: "QUERY",
        sql_hash: sqlHash,
        mocked: true,
        rows: [],
        column_names: [],
      };
    },

    getJobStatus({ jobId }) {
      return {
        job_id: jobId,
        status: "FINISHED",
        mocked: true,
      };
    },

    getJobResult({ jobId }) {
      return {
        job_id: jobId,
        status: "FINISHED",
        mocked: true,
        rows: [],
        column_names: [],
      };
    },
  };
}

module.exports = {
  createMockDliClient,
  hashSql,
};
