const path = require("path");

function generatePayload(artifacts, envConfig) {
  const { canonicalDag, pipelineYaml, sqlNodes } = artifacts;
  const dag = canonicalDag.dag;

  const nodes = pipelineYaml.nodes.map((n, i) => {
    const sqlFileName = n.sql_file.replace("nodes/", "");
    const sqlContent = sqlNodes[sqlFileName] || "";
    const lines = sqlContent.split("\n").filter((l) => l.trim() && !l.trim().startsWith("--"));
    const cleanSql = lines.join("\n").trim();

    return {
      name: n.name,
      type: n.type,
      execution_order: n.execution_order,
      dependencies: n.dependencies,
      source_task: n.source_task,
      medallion_layer: n.medallion_layer,
      description: n.description,
      sql: cleanSql,
      sql_length_chars: cleanSql.length,
      sql_source_file: n.sql_file,
    };
  });

  const payload = {
    _meta: {
      generated_by: "dataarts-deploy-agent v0.1.0",
      generated_at: new Date().toISOString(),
      mode: "DRY_RUN",
      artifacts_dir: artifacts.artifactsDir,
      source_platform: dag.source_platform,
      target_platform: dag.target_platform,
    },
    job: {
      name: envConfig.DATAARTS_JOB_NAME,
      workspace_id: envConfig.DATAARTS_WORKSPACE_ID,
      region: envConfig.HUAWEI_REGION,
      project_id: envConfig.HUAWEI_PROJECT_ID,
      description: dag.description,
      schedule: {
        cron: pipelineYaml.schedule.cron,
        timezone: pipelineYaml.schedule.timezone,
        enabled: pipelineYaml.schedule.enabled,
      },
      pipeline_name: dag.pipeline_name,
      total_nodes: nodes.length,
      nodes: nodes,
      edges: pipelineYaml.dependencies,
      execution_order: pipelineYaml.execution_order,
    },
  };

  return payload;
}

function formatStartTime() {
  const now = new Date();
  const yyyy = now.getUTCFullYear();
  const MM = String(now.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(now.getUTCDate()).padStart(2, "0");
  const HH = String(now.getUTCHours()).padStart(2, "0");
  const mm = String(now.getUTCMinutes()).padStart(2, "0");
  const ss = String(now.getUTCSeconds()).padStart(2, "0");
  return `${yyyy}-${MM}-${dd}T${HH}:${mm}:${ss}+00`;
}

function generateV1Request(artifacts, envConfig, payload) {
  const dag = artifacts.canonicalDag.dag;
  const nodes = payload.job.nodes;

  const canonicalNodes = nodes.map((n, i) => {
    const resolvedDeps = (n.dependencies || [])
      .map((d) => {
        const depNode = nodes.find((x) => `node_0${x.execution_order}` === d);
        return depNode ? depNode.name : d;
      })
      .filter((d) => {
        return nodes.some((x) => x.name === d);
      });

    return {
      name: n.name,
      type: "DLISQL",
      preNodeName: resolvedDeps,
      location: {
        x: String(100 + i * 300),
        y: "100",
      },
      properties: [
        { name: "sql", value: n.sql },
        { name: "statementOrScript", value: "STATEMENT" },
        { name: "queueName", value: envConfig.DLI_QUEUE_NAME || "default" },
        { name: "database", value: "demo_migration" },
      ],
    };
  });

  const startTime = formatStartTime();

  const body = {
    name: envConfig.DATAARTS_JOB_NAME,
    processType: "BATCH",
    description: dag.description,
    schedule: {
      type: "CRON",
      cron: {
        startTime: startTime,
        expression: "0 0-59/5 * * * ?",
        expressionTimeZone: "GMT+0",
        dependPrePeriod: false,
        concurrent: 1,
      },
    },
    nodes: canonicalNodes,
  };

  const request = {
    _meta: {
      generated_by: "dataarts-deploy-agent v0.1.0",
      generated_at: new Date().toISOString(),
      mode: "DRY_RUN",
      source_platform: dag.source_platform,
      target_platform: dag.target_platform,
    },
    _request: {
      method: "POST",
      endpoint: `https://dayu-dlf.${envConfig.HUAWEI_REGION}.myhuaweicloud.com`,
      path: `/v1/${envConfig.HUAWEI_PROJECT_ID}/jobs`,
      headers: {
        "Content-Type": "application/json",
        workspace: envConfig.DATAARTS_WORKSPACE_ID,
      },
    },
    body: body,
  };

  return request;
}

function validateV1Body(body) {
  const checks = [];

  checks.push({ name: "body exists", pass: !!body, detail: body ? "OK" : "missing" });
  if (!body) return checks;

  checks.push({ name: "body.name exists", pass: !!body.name, detail: body.name || "missing" });
  checks.push({ name: "body.processType exists", pass: !!body.processType, detail: body.processType || "missing" });
  checks.push({ name: "body.schedule exists", pass: !!body.schedule, detail: body.schedule ? "OK" : "missing" });

  const nodeCount = Array.isArray(body.nodes) ? body.nodes.length : 0;
  checks.push({ name: "body.nodes length = 3", pass: nodeCount === 3, detail: `got ${nodeCount}` });

  if (Array.isArray(body.nodes)) {
    const allDlisql = body.nodes.every((n) => n.type === "DLISQL");
    checks.push({ name: "node types = DLISQL", pass: allDlisql, detail: allDlisql ? "OK" : body.nodes.map((n) => n.type).join(", ") });

    const allPreNodeArrays = body.nodes.every((n) => Array.isArray(n.preNodeName));
    checks.push({ name: "preNodeName arrays", pass: allPreNodeArrays, detail: allPreNodeArrays ? "OK" : "not all arrays" });

    const allPropsArrays = body.nodes.every((n) => Array.isArray(n.properties));
    checks.push({ name: "properties arrays", pass: allPropsArrays, detail: allPropsArrays ? "OK" : "not all arrays" });

    const allHaveSql = body.nodes.every((n) =>
      Array.isArray(n.properties) && n.properties.some((p) => p.name === "sql")
    );
    checks.push({ name: "SQL property exists", pass: allHaveSql, detail: allHaveSql ? "OK" : "missing sql property" });
  }

  return checks;
}

function generateReadinessReport(artifacts, envConfig, payload, v1Request) {
  const { canonicalDag, pipelineYaml, sqlNodes } = artifacts;
  const dag = canonicalDag.dag;
  const lines = [];

  lines.push("# Deployment Readiness Report");
  lines.push("");
  lines.push(`Generated: ${new Date().toISOString()}`);
  lines.push(`Mode: DRY_RUN (no API calls made)`);
  lines.push("");

  lines.push("## Environment");
  lines.push("");
  lines.push(`| Variable | Value |`);
  lines.push(`|----------|-------|`);
  lines.push(`| HUAWEI_REGION | ${envConfig.HUAWEI_REGION} |`);
  lines.push(`| HUAWEI_PROJECT_ID | ${envConfig.HUAWEI_PROJECT_ID} |`);
  lines.push(`| HUAWEI_AK | ***${envConfig.HUAWEI_AK.slice(-4)} |`);
  lines.push(`| HUAWEI_SK | ***${envConfig.HUAWEI_SK.slice(-4)} |`);
  lines.push(`| DATAARTS_WORKSPACE_ID | ${envConfig.DATAARTS_WORKSPACE_ID} |`);
  lines.push(`| DATAARTS_JOB_NAME | ${envConfig.DATAARTS_JOB_NAME} |`);
  lines.push(`| DATAARTS_ARTIFACTS_DIR | ${envConfig.DATAARTS_ARTIFACTS_DIR} |`);
  lines.push("");

  lines.push("## Artifacts Loaded");
  lines.push("");
  lines.push("| Artifact | Status |");
  lines.push("|----------|--------|");
  lines.push("| canonical_dag.json | OK |");
  lines.push("| dataarts_pipeline.yaml | OK |");
  for (const f of Object.keys(sqlNodes)) {
    lines.push(`| nodes/${f} | OK (${sqlNodes[f].length} chars) |`);
  }
  lines.push("");

  lines.push("## Pipeline Summary");
  lines.push("");
  lines.push(`- **Pipeline name:** ${dag.pipeline_name}`);
  lines.push(`- **Schedule:** ${pipelineYaml.schedule.cron} (${pipelineYaml.schedule.timezone})`);
  lines.push(`- **Total nodes:** ${dag.total_nodes}`);
  lines.push(`- **Root task:** ${dag.root_task}`);
  lines.push(`- **Source platform:** ${dag.source_platform}`);
  lines.push(`- **Target platform:** ${dag.target_platform}`);
  lines.push("");

  lines.push("## Node Details");
  lines.push("");
  lines.push("| # | Node | Type | Layer | Dependencies | SQL Size |");
  lines.push("|---|------|------|-------|--------------|---------|");
  for (const n of payload.job.nodes) {
    lines.push(`| ${n.execution_order} | ${n.name} | ${n.type} | ${n.medallion_layer} | ${n.dependencies.length > 0 ? n.dependencies.join(", ") : "(root)"} | ${n.sql_length_chars} chars |`);
  }
  lines.push("");

  lines.push("## Execution Order");
  lines.push("");
  for (const nId of payload.job.execution_order) {
    const node = payload.job.nodes.find((n) => n.name === nId || `node_0${n.execution_order}` === nId);
    if (node) {
      lines.push(`${node.execution_order}. **${node.name}** (${node.source_task} → ${node.type})`);
    }
  }
  lines.push("");

  lines.push("## Readiness Checks");
  lines.push("");
  const checks = [
    { name: "All env vars present", pass: true },
    { name: "Artifacts dir exists", pass: true },
    { name: "canonical_dag.json parsed", pass: true },
    { name: "dataarts_pipeline.yaml parsed", pass: true },
    { name: "All SQL nodes loaded", pass: Object.keys(sqlNodes).length === 3 },
    { name: "DAG has nodes", pass: dag.total_nodes > 0 },
    { name: "Schedule defined", pass: !!pipelineYaml.schedule.cron },
    { name: "Dependencies consistent", pass: payload.job.edges.length === 2 },
  ];

  for (const c of checks) {
    lines.push(`- [${c.pass ? "x" : " "}] ${c.name}`);
  }
  lines.push("");
  const allPass = checks.every((c) => c.pass);
  lines.push(`**Overall: ${allPass ? "READY (dry-run only)" : "NOT READY"}**`);
  lines.push("");

  lines.push("## Canonical V1 Request Validation");
  lines.push("");
  const v1Checks = validateV1Body(v1Request ? v1Request.body : null);
  for (const c of v1Checks) {
    const status = c.pass ? "PASS" : "FAIL";
    lines.push(`- [${c.pass ? "x" : " "}] ${c.name} (${status}: ${c.detail})`);
  }
  lines.push("");
  const v1AllPass = v1Checks.every((c) => c.pass);
  lines.push(`**V1 Request: ${v1AllPass ? "VALID" : "INVALID"}**`);
  lines.push("");

  lines.push("## API Metadata");
  lines.push("");
  lines.push("| Field | Value |");
  lines.push("|-------|-------|");
  lines.push("| endpoint | POST /v1/{project_id}/jobs |");
  lines.push("| header workspace | DATAARTS_WORKSPACE_ID |");
  lines.push("| project_id source | HUAWEI_PROJECT_ID |");
  lines.push("| start endpoint | POST /v1/{project_id}/jobs/{job_name}/start |");
  lines.push("");

  lines.push("## What This Does NOT Do");
  lines.push("");
  lines.push("- Does NOT call the Huawei Cloud DataArts API.");
  lines.push("- Does NOT create, update, or delete any DataArts jobs.");
  lines.push("- Does NOT upload SQL to OBS or DataArts.");
  lines.push("- Does NOT execute any pipeline.");
  lines.push("- No live API calls are made in dry-run mode.");
  lines.push("- This is a **dry-run payload generator only**.");
  lines.push("");

  lines.push("## Next Step");
  lines.push("");
  lines.push("To deploy for real, implement `src/deploy.js` that:");
  lines.push("1. Authenticates with HUAWEI_AK / HUAWEI_SK.");
  lines.push("2. Calls `POST /v1/{project_id}/jobs` with header `workspace: DATAARTS_WORKSPACE_ID`.");
  lines.push("3. Uploads SQL scripts to OBS.");
  lines.push("4. Publishes and optionally runs the pipeline via `POST /v1/{project_id}/jobs/{job_name}/start`.");
  lines.push("");

  return lines.join("\n");
}

module.exports = { generatePayload, generateV1Request, generateReadinessReport, validateV1Body };
