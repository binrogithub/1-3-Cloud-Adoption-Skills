const test = require("node:test");
const assert = require("node:assert/strict");
const {
  auditDliSubmitJobRequest,
  auditDliTransportPlan,
  classifyStatement,
  isCreateOrDropDatabaseStatement,
  buildAuditSafety,
} = require("../../src/runtime/dli/dli-submit-job-auditor");

test("valid submit-job request passes audit", () => {
  const request = {
    service: "DLI",
    operation: "submitSqlJob",
    method: "POST",
    endpoint: "https://dli.cn-north-7.myhuaweicloud.com",
    path: "/v1.0/proj-123/jobs/submit-job",
    url: "https://dli.cn-north-7.myhuaweicloud.com/v1.0/proj-123/jobs/submit-job",
    region: "cn-north-7",
    project_id: "proj-123",
    queue_name: "default",
    sql_hash: "abc123",
    sql_preview: "SELECT COUNT(*) FROM test",
    body_keys: ["sql", "queue_name", "currentdb"],
    execution_mode: "PLAN_ONLY",
  };
  const result = auditDliSubmitJobRequest(request, { queueName: "default" });
  assert.equal(result.valid, true);
  assert.equal(result.status, "DLI_SUBMIT_JOB_AUDIT_PASS");
  assert.equal(result.findings.length, 0);
});

test("missing sql fails audit", () => {
  const request = {
    method: "POST",
    path: "/v1.0/proj-123/jobs/submit-job",
    queue_name: "default",
    sql_hash: "",
    sql_preview: "",
    body_keys: ["queue_name"],
    project_id: "proj-123",
    region: "cn-north-7",
    url: "https://dli.cn-north-7.myhuaweicloud.com/v1.0/proj-123/jobs/submit-job",
  };
  const result = auditDliSubmitJobRequest(request, { queueName: "default" });
  assert.equal(result.valid, false);
  assert.ok(result.findings.some((f) => f.includes("sql")));
});

test("missing queue_name fails audit", () => {
  const request = {
    method: "POST",
    path: "/v1.0/proj-123/jobs/submit-job",
    sql_hash: "abc",
    sql_preview: "SELECT 1",
    body_keys: ["sql"],
    project_id: "proj-123",
    region: "cn-north-7",
    url: "https://dli.cn-north-7.myhuaweicloud.com/v1.0/proj-123/jobs/submit-job",
  };
  const result = auditDliSubmitJobRequest(request, { queueName: "default" });
  assert.equal(result.valid, false);
  assert.ok(result.findings.some((f) => f.includes("queue_name")));
});

test("invalid path fails audit", () => {
  const request = {
    method: "POST",
    path: "/v1.0/proj-123/wrong-endpoint",
    queue_name: "default",
    sql_hash: "abc",
    sql_preview: "SELECT 1",
    body_keys: ["sql", "queue_name"],
    project_id: "proj-123",
    region: "cn-north-7",
    url: "https://dli.cn-north-7.myhuaweicloud.com/v1.0/proj-123/wrong-endpoint",
  };
  const result = auditDliSubmitJobRequest(request, { queueName: "default" });
  assert.equal(result.valid, false);
  assert.ok(result.findings.some((f) => f.includes("submit-job")));
});

test("CREATE DATABASE does not require currentdb", () => {
  const request = {
    method: "POST",
    path: "/v1.0/proj-123/jobs/submit-job",
    queue_name: "default",
    sql_hash: "abc",
    sql_preview: "CREATE DATABASE IF NOT EXISTS demo_migration;",
    body_keys: ["sql", "queue_name"],
    project_id: "proj-123",
    region: "cn-north-7",
    url: "https://dli.cn-north-7.myhuaweicloud.com/v1.0/proj-123/jobs/submit-job",
  };
  const result = auditDliSubmitJobRequest(request, { queueName: "default" });
  assert.ok(!result.warnings.some((w) => w.includes("currentdb")));
});

test("CREATE TABLE without currentdb warns", () => {
  const request = {
    method: "POST",
    path: "/v1.0/proj-123/jobs/submit-job",
    queue_name: "default",
    sql_hash: "abc",
    sql_preview: "CREATE TABLE demo_migration.test (id INT);",
    body_keys: ["sql", "queue_name"],
    project_id: "proj-123",
    region: "cn-north-7",
    url: "https://dli.cn-north-7.myhuaweicloud.com/v1.0/proj-123/jobs/submit-job",
  };
  const result = auditDliSubmitJobRequest(request, { queueName: "default" });
  assert.ok(result.warnings.some((w) => w.includes("currentdb")));
});

test("INSERT without currentdb warns", () => {
  const request = {
    method: "POST",
    path: "/v1.0/proj-123/jobs/submit-job",
    queue_name: "default",
    sql_hash: "abc",
    sql_preview: "INSERT INTO demo_migration.test VALUES (1);",
    body_keys: ["sql", "queue_name"],
    project_id: "proj-123",
    region: "cn-north-7",
    url: "https://dli.cn-north-7.myhuaweicloud.com/v1.0/proj-123/jobs/submit-job",
  };
  const result = auditDliSubmitJobRequest(request, { queueName: "default" });
  assert.ok(result.warnings.some((w) => w.includes("currentdb")));
});

test("SELECT without currentdb warns", () => {
  const request = {
    method: "POST",
    path: "/v1.0/proj-123/jobs/submit-job",
    queue_name: "default",
    sql_hash: "abc",
    sql_preview: "SELECT COUNT(*) FROM demo_migration.test",
    body_keys: ["sql", "queue_name"],
    project_id: "proj-123",
    region: "cn-north-7",
    url: "https://dli.cn-north-7.myhuaweicloud.com/v1.0/proj-123/jobs/submit-job",
  };
  const result = auditDliSubmitJobRequest(request, { queueName: "default" });
  assert.ok(result.warnings.some((w) => w.includes("currentdb")));
});

test("null request fails audit", () => {
  const result = auditDliSubmitJobRequest(null);
  assert.equal(result.valid, false);
  assert.equal(result.status, "DLI_SUBMIT_JOB_AUDIT_FAIL");
});

test("null project_id warns", () => {
  const request = {
    method: "POST",
    path: null,
    queue_name: "default",
    sql_hash: "abc",
    sql_preview: "SELECT 1",
    body_keys: ["sql", "queue_name"],
    project_id: null,
    region: null,
    url: null,
  };
  const result = auditDliSubmitJobRequest(request, { queueName: "default" });
  assert.ok(result.warnings.some((w) => w.includes("project_id")));
});

test("null region warns", () => {
  const request = {
    method: "POST",
    path: null,
    queue_name: "default",
    sql_hash: "abc",
    sql_preview: "SELECT 1",
    body_keys: ["sql", "queue_name"],
    project_id: "proj-123",
    region: null,
    url: null,
  };
  const result = auditDliSubmitJobRequest(request, { queueName: "default" });
  assert.ok(result.warnings.some((w) => w.includes("region")));
});

test("secrets detected in request body", () => {
  const request = {
    method: "POST",
    path: "/v1.0/proj-123/jobs/submit-job",
    queue_name: "default",
    sql_hash: "abc",
    sql_preview: "SELECT 1",
    body_keys: ["sql", "queue_name"],
    project_id: "proj-123",
    region: "cn-north-7",
    url: "https://dli.cn-north-7.myhuaweicloud.com/v1.0/proj-123/jobs/submit-job",
    access_key: "secret_ak_value",
  };
  const result = auditDliSubmitJobRequest(request, { queueName: "default" });
  assert.ok(result.findings.some((f) => f.includes("secrets")));
});

test("request without secrets passes secret check", () => {
  const request = {
    method: "POST",
    path: "/v1.0/proj-123/jobs/submit-job",
    queue_name: "default",
    sql_hash: "abc",
    sql_preview: "SELECT 1",
    body_keys: ["sql", "queue_name"],
    project_id: "proj-123",
    region: "cn-north-7",
    url: "https://dli.cn-north-7.myhuaweicloud.com/v1.0/proj-123/jobs/submit-job",
  };
  const result = auditDliSubmitJobRequest(request, { queueName: "default" });
  assert.ok(!result.findings.some((f) => f.includes("secrets")));
});

test("classifyStatement identifies statement types", () => {
  assert.equal(classifyStatement("CREATE DATABASE IF NOT EXISTS db"), "CREATE_DATABASE");
  assert.equal(classifyStatement("DROP DATABASE db"), "DROP_DATABASE");
  assert.equal(classifyStatement("CREATE TABLE t (id INT)"), "CREATE_TABLE");
  assert.equal(classifyStatement("DROP TABLE t"), "DROP_TABLE");
  assert.equal(classifyStatement("INSERT INTO t VALUES (1)"), "INSERT");
  assert.equal(classifyStatement("SELECT * FROM t"), "SELECT");
  assert.equal(classifyStatement("MERGE INTO t USING s ON 1=1"), "MERGE");
  assert.equal(classifyStatement(null), "UNKNOWN");
  assert.equal(classifyStatement(""), "UNKNOWN");
});

test("isCreateOrDropDatabaseStatement works", () => {
  assert.equal(isCreateOrDropDatabaseStatement("CREATE DATABASE db"), true);
  assert.equal(isCreateOrDropDatabaseStatement("DROP DATABASE db"), true);
  assert.equal(isCreateOrDropDatabaseStatement("CREATE TABLE t (id INT)"), false);
  assert.equal(isCreateOrDropDatabaseStatement("SELECT 1"), false);
});

test("auditDliTransportPlan with invalid plan fails", () => {
  const result = auditDliTransportPlan({ transportPlan: { valid: false } });
  assert.equal(result.valid, false);
  assert.equal(result.status, "DLI_SUBMIT_JOB_AUDIT_FAIL");
  assert.equal(result.requests_audited, 0);
});

test("auditDliTransportPlan audits 15 requests for customer package", () => {
  const transportRequests = [];
  const steps = [
    { phase: "runtime_setup", step_name: "01_create_schema.sql", step_type: "DLI_SQL", sql_preview: "CREATE DATABASE IF NOT EXISTS demo_migration;" },
    { phase: "runtime_setup", step_name: "02_create_raw_tables.sql", step_type: "DLI_SQL", sql_preview: "CREATE TABLE IF NOT EXISTS demo_migration.raw_customers (id INT);" },
    { phase: "runtime_setup", step_name: "03_insert_seed_data.sql", step_type: "DLI_SQL", sql_preview: "INSERT INTO demo_migration.raw_customers VALUES (1, 'Alice');" },
    { phase: "target_transform", step_name: "drop_silver", step_type: "DLI_SQL", sql_preview: "DROP TABLE IF EXISTS demo_migration.silver_customers;" },
    { phase: "target_transform", step_name: "create_silver", step_type: "DLI_SQL", sql_preview: "CREATE TABLE demo_migration.silver_customers AS SELECT * FROM demo_migration.raw_customers;" },
    { phase: "target_transform", step_name: "drop_gold", step_type: "DLI_SQL", sql_preview: "DROP TABLE IF EXISTS demo_migration.gold_customer_status;" },
    { phase: "target_transform", step_name: "create_gold", step_type: "DLI_SQL", sql_preview: "CREATE TABLE demo_migration.gold_customer_status AS SELECT * FROM demo_migration.silver_customers;" },
    { phase: "target_transform", step_name: "audit", step_type: "DLI_SQL", sql_preview: "INSERT INTO demo_migration.task_audit VALUES ('x', 'y', 'SUCCESS', '', NOW());" },
    { phase: "runtime_validation", step_name: "v1", step_type: "DLI_QUERY", sql_preview: "SELECT COUNT(*) AS actual_value FROM demo_migration.raw_customers" },
    { phase: "runtime_validation", step_name: "v2", step_type: "DLI_QUERY", sql_preview: "SELECT COUNT(*) AS actual_value FROM demo_migration.silver_customers" },
    { phase: "runtime_validation", step_name: "v3", step_type: "DLI_QUERY", sql_preview: "SELECT COUNT(*) AS actual_value FROM demo_migration.gold_customer_status" },
    { phase: "runtime_validation", step_name: "v4", step_type: "DLI_QUERY", sql_preview: "SELECT COUNT(*) AS actual_value FROM demo_migration.task_audit WHERE status = 'SUCCESS'" },
    { phase: "runtime_validation", step_name: "v5", step_type: "DLI_QUERY", sql_preview: "SELECT customer_count FROM demo_migration.gold_customer_status WHERE customer_status = 'ACTIVE'" },
    { phase: "runtime_validation", step_name: "v6", step_type: "DLI_QUERY", sql_preview: "SELECT customer_count FROM demo_migration.gold_customer_status WHERE customer_status = 'INACTIVE'" },
    { phase: "runtime_validation", step_name: "v7", step_type: "DLI_QUERY", sql_preview: "SELECT 'EQUIVALENT' AS actual_value" },
  ];

  for (const s of steps) {
    transportRequests.push({
      phase: s.phase,
      step_name: s.step_name,
      step_type: s.step_type,
      transport_request: {
        service: "DLI",
        operation: "submitSqlJob",
        method: "POST",
        path: "/v1.0/proj-123/jobs/submit-job",
        url: "https://dli.cn-north-7.myhuaweicloud.com/v1.0/proj-123/jobs/submit-job",
        region: "cn-north-7",
        project_id: "proj-123",
        queue_name: "default",
        sql_hash: "abc",
        sql_preview: s.sql_preview,
        body_keys: ["sql", "queue_name"],
        execution_mode: "PLAN_ONLY",
      },
    });
  }

  const transportPlan = {
    status: "DLI_TRANSPORT_PLAN_READY",
    valid: true,
    migration_id: "customer_status_pipeline_simple",
    dli_queue: "default",
    total_transport_requests: 15,
    transport_requests: transportRequests,
  };

  const result = auditDliTransportPlan({ transportPlan, queueName: "default" });
  assert.equal(result.requests_audited, 15);
  assert.ok(result.request_audits.length === 15);
});

test("safety flags present in audit result", () => {
  const result = auditDliSubmitJobRequest({
    method: "POST",
    path: "/v1.0/proj-123/jobs/submit-job",
    queue_name: "default",
    sql_hash: "abc",
    sql_preview: "SELECT 1",
    body_keys: ["sql", "queue_name"],
    project_id: "proj-123",
    region: "cn-north-7",
    url: "https://dli.cn-north-7.myhuaweicloud.com/v1.0/proj-123/jobs/submit-job",
  });
  assert.equal(result.safety.local_audit_only, true);
  assert.equal(result.safety.no_cloud_api_calls, true);
  assert.equal(result.safety.no_sql_execution, true);
  assert.equal(result.safety.no_runtime_execution, true);
  assert.equal(result.safety.secrets_redacted, true);
});

test("buildAuditSafety returns correct flags", () => {
  const safety = buildAuditSafety();
  assert.equal(safety.local_audit_only, true);
  assert.equal(safety.no_cloud_api_calls, true);
  assert.equal(safety.no_sql_execution, true);
  assert.equal(safety.no_runtime_execution, true);
  assert.equal(safety.secrets_redacted, true);
});

test("CREATE DATABASE with currentdb warns about DDL conflict", () => {
  const request = {
    method: "POST",
    path: "/v1.0/proj-123/jobs/submit-job",
    queue_name: "default",
    sql_hash: "abc",
    sql_preview: "CREATE DATABASE IF NOT EXISTS demo_migration;",
    body_keys: ["sql", "queue_name", "currentdb"],
    project_id: "proj-123",
    region: "cn-north-7",
    url: "https://dli.cn-north-7.myhuaweicloud.com/v1.0/proj-123/jobs/submit-job",
  };
  const result = auditDliSubmitJobRequest(request, { queueName: "default" });
  assert.ok(result.warnings.some((w) => w.includes("currentdb")));
});

test("queue_name mismatch warns", () => {
  const request = {
    method: "POST",
    path: "/v1.0/proj-123/jobs/submit-job",
    queue_name: "other_queue",
    sql_hash: "abc",
    sql_preview: "SELECT 1",
    body_keys: ["sql", "queue_name"],
    project_id: "proj-123",
    region: "cn-north-7",
    url: "https://dli.cn-north-7.myhuaweicloud.com/v1.0/proj-123/jobs/submit-job",
  };
  const result = auditDliSubmitJobRequest(request, { queueName: "default" });
  assert.ok(result.warnings.some((w) => w.includes("queue_name")));
});

test("invalid method fails audit", () => {
  const request = {
    method: "GET",
    path: "/v1.0/proj-123/jobs/submit-job",
    queue_name: "default",
    sql_hash: "abc",
    sql_preview: "SELECT 1",
    body_keys: ["sql", "queue_name"],
    project_id: "proj-123",
    region: "cn-north-7",
    url: "https://dli.cn-north-7.myhuaweicloud.com/v1.0/proj-123/jobs/submit-job",
  };
  const result = auditDliSubmitJobRequest(request, { queueName: "default" });
  assert.equal(result.valid, false);
  assert.ok(result.findings.some((f) => f.includes("POST")));
});

test("isCreateOrDropDatabaseStatement used for currentdb resolution", () => {
  assert.equal(isCreateOrDropDatabaseStatement("CREATE DATABASE IF NOT EXISTS demo_migration;"), true);
  assert.equal(isCreateOrDropDatabaseStatement("  CREATE DATABASE demo_migration;"), true);
  assert.equal(isCreateOrDropDatabaseStatement("DROP DATABASE IF EXISTS demo_migration;"), true);
  assert.equal(isCreateOrDropDatabaseStatement("CREATE TABLE demo_migration.t (id INT);"), false);
  assert.equal(isCreateOrDropDatabaseStatement("INSERT INTO demo_migration.t VALUES (1);"), false);
  assert.equal(isCreateOrDropDatabaseStatement("SELECT * FROM demo_migration.t"), false);
});
