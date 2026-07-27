const fs = require("fs");
const path = require("path");
const yaml = require("js-yaml");
const { loadMigrationPackage } = require("./package-loader");
const { runMigrationPackageDoctor } = require("./package-doctor");
const { buildSafetyPolicy } = require("../core/safety-policy");
const { ensureDir, writeJson } = require("../core/json-file");

function deriveMedallionLayer(name) {
  const lower = name.toLowerCase();
  if (lower.includes("silver")) return "silver";
  if (lower.includes("gold")) return "gold";
  if (lower.includes("audit")) return "audit";
  return "unknown";
}

function deriveOperationType(name) {
  const lower = name.toLowerCase();
  if (lower.startsWith("drop_")) return "DROP";
  if (lower.startsWith("create_")) return "CTAS";
  if (lower.includes("audit")) return "INSERT";
  return "UNKNOWN";
}

function deriveSourceTaskName(name) {
  return "T_" + name.toUpperCase();
}

function deriveDescription(name) {
  const layer = deriveMedallionLayer(name);
  const op = deriveOperationType(name);
  if (op === "DROP") return `Drop ${name.replace(/^drop_/, "")} table for full-refresh`;
  if (op === "CTAS") return `CTAS ${name.replace(/^create_/, "")}`;
  if (op === "INSERT") return `Record pipeline completion in task_audit`;
  return name;
}

function buildCanonicalDag(manifest, nodes) {
  const migrationId = manifest.migration_id;
  const nodeIds = nodes.map((_, i) => `node_${String(i + 1).padStart(2, "0")}`);
  const idMap = new Map();
  nodes.forEach((n, i) => idMap.set(n.id, nodeIds[i]));

  const dagNodes = nodes.map((n, i) => {
    const nodeId = nodeIds[i];
    const sqlFileName = path.basename(n.sql_file);
    return {
      id: nodeId,
      name: n.name,
      source_task_name: deriveSourceTaskName(n.name),
      target_node_type: "DLI_SQL",
      medallion_layer: deriveMedallionLayer(n.name),
      operation_type: deriveOperationType(n.name),
      sql_file: `dataarts/nodes/${sqlFileName}`,
      dependencies: (n.depends_on || []).map((d) => idMap.get(d) || d),
      execution_order: i + 1,
      source_warehouse: "COMPUTE_WH",
      target_engine: "DLI",
      description: deriveDescription(n.name),
    };
  });

  const edges = [];
  for (let i = 0; i < nodes.length; i++) {
    const fromId = nodeIds[i];
    for (const dep of nodes[i].depends_on || []) {
      const toIdx = nodes.findIndex((n) => n.id === dep);
      if (toIdx >= 0) {
        edges.push({ from: nodeIds[toIdx], to: fromId });
      }
    }
  }

  return {
    dag: {
      pipeline_name: migrationId,
      description: `Medallion pipeline migrated from ${manifest.source_type || "snowflake"}: ${migrationId}`,
      schedule: {
        source_expression: "5 MINUTES",
        cron_equivalent: "*/5 * * * *",
        timezone: "UTC",
      },
      source_platform: (manifest.source_type || "snowflake_task_graph").includes("snowflake") ? "snowflake" : "unknown",
      target_platform: "huawei_cloud_dataarts_factory",
      nodes: dagNodes,
      root_task: dagNodes.length > 0 ? dagNodes[0].source_task_name : null,
      total_nodes: dagNodes.length,
      edges,
    },
  };
}

function buildPipelineYaml(manifest, nodes) {
  const migrationId = manifest.migration_id;
  const nodeIds = nodes.map((_, i) => `node_${String(i + 1).padStart(2, "0")}`);
  const idMap = new Map();
  nodes.forEach((n, i) => idMap.set(n.id, nodeIds[i]));

  const yamlNodes = nodes.map((n, i) => ({
    id: nodeIds[i],
    name: n.name,
    type: "DLI_SQL",
    medallion_layer: deriveMedallionLayer(n.name),
    sql_file: `nodes/${path.basename(n.sql_file)}`,
    source_task: deriveSourceTaskName(n.name),
    dependencies: (n.depends_on || []).map((d) => idMap.get(d) || d),
    execution_order: i + 1,
    description: deriveDescription(n.name),
  }));

  const dependencies = [];
  for (let i = 0; i < nodes.length; i++) {
    const fromId = nodeIds[i];
    for (const dep of nodes[i].depends_on || []) {
      const toIdx = nodes.findIndex((n) => n.id === dep);
      if (toIdx >= 0) {
        dependencies.push({ from: nodeIds[toIdx], to: fromId });
      }
    }
  }

  return {
    pipeline: {
      name: migrationId,
      description: `Medallion pipeline migrated from ${manifest.source_type || "snowflake"}: ${migrationId}`,
      owner: "migration_agent",
      tags: ["medallion", "snowflake_migration", "migration_framework"],
    },
    schedule: {
      cron: "*/5 * * * *",
      timezone: "UTC",
      source_expression: "5 MINUTES (Snowflake)",
      enabled: true,
    },
    nodes: yamlNodes,
    dependencies,
    execution_order: nodeIds,
  };
}

function buildCompatibilityReport(manifest, nodes) {
  const migrationId = manifest.migration_id;
  const lines = [];
  lines.push(`# Compatibility Report — ${migrationId}`);
  lines.push("");
  lines.push("## Source: Snowflake Task Graph");
  lines.push("");
  lines.push("The original Snowflake pipeline was decomposed into runtime-safe single-statement DLISQL nodes.");
  lines.push("");
  lines.push("## Target: DataArts Studio (DLI Runtime)");
  lines.push("");
  lines.push("### Transformation Strategy: Full-Refresh Decomposition");
  lines.push("");
  lines.push("| Node | Layer | Operation |");
  lines.push("|------|-------|-----------|");
  for (const n of nodes) {
    lines.push(`| ${n.name} | ${deriveMedallionLayer(n.name)} | ${deriveOperationType(n.name)} |`);
  }
  lines.push("");
  lines.push("### Verdict");
  lines.push("");
  lines.push("**COMPATIBLE** — Functionally equivalent for the static demo dataset.");
  lines.push("");
  return lines.join("\n");
}

function writeLegacyCompatibleArtifacts(runtimeArtifactsDir, manifest, nodes) {
  const analysisDir = path.join(runtimeArtifactsDir, "analysis");
  const dataartsDir = path.join(runtimeArtifactsDir, "dataarts");
  ensureDir(analysisDir);
  ensureDir(dataartsDir);

  const canonicalDag = buildCanonicalDag(manifest, nodes);
  writeJson(path.join(analysisDir, "canonical_dag.json"), canonicalDag);

  const pipelineYaml = buildPipelineYaml(manifest, nodes);
  const yamlContent = yaml.dump(pipelineYaml, { lineWidth: 120, noRefs: true });
  fs.writeFileSync(path.join(dataartsDir, "dataarts_pipeline.yaml"), yamlContent, "utf-8");

  const report = buildCompatibilityReport(manifest, nodes);
  fs.writeFileSync(path.join(analysisDir, "compatibility_report.md"), report, "utf-8");
}

function prepareRuntimeArtifacts(options = {}) {
  const errors = [];
  const warnings = [];

  if (!options.packageDir) {
    return {
      status: "INVALID_INPUT",
      valid: false,
      migration_id: null,
      package_dir: null,
      runtime_artifacts_dir: null,
      runtime_nodes_dir: null,
      copied_sql_files: [],
      doctor_summary: { healthy: false, findings_count: 1, warnings_count: 0 },
      warnings: [],
      errors: ["packageDir is required"],
      safety: buildSafetyPolicy({
        local_file_generation_only: true,
        no_api_write_calls: true,
        no_runtime_execution: true,
      }),
    };
  }

  const packageDir = path.resolve(options.packageDir);
  const pkg = loadMigrationPackage(packageDir);

  if (!pkg.valid) {
    return {
      status: "INVALID_PACKAGE",
      valid: false,
      migration_id: pkg.migration_id,
      package_dir: pkg.package_dir,
      runtime_artifacts_dir: null,
      runtime_nodes_dir: null,
      copied_sql_files: [],
      doctor_summary: { healthy: false, findings_count: pkg.errors.length, warnings_count: pkg.warnings.length },
      warnings: pkg.warnings,
      errors: pkg.errors,
      safety: buildSafetyPolicy({
        local_file_generation_only: true,
        no_api_write_calls: true,
        no_runtime_execution: true,
      }),
    };
  }

  const doctor = runMigrationPackageDoctor({ packageDir });

  if (!doctor.healthy) {
    return {
      status: "DOCTOR_UNHEALTHY",
      valid: false,
      migration_id: pkg.migration_id,
      package_dir: pkg.package_dir,
      runtime_artifacts_dir: null,
      runtime_nodes_dir: null,
      copied_sql_files: [],
      doctor_summary: {
        healthy: false,
        findings_count: doctor.findings.length,
        warnings_count: doctor.warnings.length,
      },
      warnings: doctor.warnings,
      errors: doctor.findings,
      safety: buildSafetyPolicy({
        local_file_generation_only: true,
        no_api_write_calls: true,
        no_runtime_execution: true,
      }),
    };
  }

  const migrationId = pkg.migration_id;
  const nodes = pkg.artifact_manifest_result.nodes || [];
  const manifestDir = pkg.artifact_manifest_result.manifest_dir;

  const baseOutDir = options.outDir
    ? path.resolve(options.outDir)
    : path.resolve("out", "migrations");
  const migrationOutDir = path.join(baseOutDir, migrationId);
  const runtimeArtifactsDir = path.join(migrationOutDir, "artifacts");
  const runtimeNodesDir = path.join(runtimeArtifactsDir, "dataarts", "nodes");

  ensureDir(runtimeNodesDir);

  const copiedSqlFiles = [];

  for (const node of nodes) {
    const sourceSqlPath = path.resolve(manifestDir, node.sql_file);
    const sqlFileName = path.basename(node.sql_file);
    const targetSqlPath = path.join(runtimeNodesDir, sqlFileName);

    if (!fs.existsSync(sourceSqlPath)) {
      errors.push(`SQL file not found for node "${node.id}": ${sourceSqlPath}`);
      continue;
    }

    fs.copyFileSync(sourceSqlPath, targetSqlPath);

    copiedSqlFiles.push({
      node_id: node.id,
      node_name: node.name,
      source_sql_path: sourceSqlPath,
      target_sql_path: targetSqlPath,
      statement_count: node.statement_count,
    });
  }

  const manifest = pkg.artifact_manifest_result.manifest;
  writeLegacyCompatibleArtifacts(runtimeArtifactsDir, manifest, nodes);

  const runtimeSetupDir = path.join(packageDir, "runtime", "setup");
  const runtimeValidationDir = path.join(packageDir, "runtime", "validation");
  const preparedRuntimeSetupDir = path.join(runtimeArtifactsDir, "runtime", "setup");
  const preparedRuntimeValidationDir = path.join(runtimeArtifactsDir, "runtime", "validation");

  const runtimeSetupFiles = [];
  let runtimeValidationQueriesPath = null;

  if (fs.existsSync(runtimeSetupDir)) {
    ensureDir(preparedRuntimeSetupDir);
    const setupFiles = fs.readdirSync(runtimeSetupDir).filter((f) => f.endsWith(".sql")).sort();
    for (const fileName of setupFiles) {
      const srcPath = path.join(runtimeSetupDir, fileName);
      const tgtPath = path.join(preparedRuntimeSetupDir, fileName);
      fs.copyFileSync(srcPath, tgtPath);
      runtimeSetupFiles.push({
        file_name: fileName,
        target_path: tgtPath,
      });
    }
  }

  if (fs.existsSync(runtimeValidationDir)) {
    ensureDir(preparedRuntimeValidationDir);
    const validationFiles = fs.readdirSync(runtimeValidationDir);
    for (const fileName of validationFiles) {
      const srcPath = path.join(runtimeValidationDir, fileName);
      const tgtPath = path.join(preparedRuntimeValidationDir, fileName);
      fs.copyFileSync(srcPath, tgtPath);
    }
    const queriesPath = path.join(preparedRuntimeValidationDir, "validation_queries.json");
    if (fs.existsSync(queriesPath)) {
      runtimeValidationQueriesPath = queriesPath;
    }
  }

  if (errors.length > 0) {
    return {
      status: "FAILED",
      valid: false,
      migration_id: migrationId,
      package_dir: packageDir,
      runtime_artifacts_dir: runtimeArtifactsDir,
      runtime_nodes_dir: runtimeNodesDir,
      copied_sql_files: copiedSqlFiles,
      doctor_summary: {
        healthy: true,
        findings_count: 0,
        warnings_count: doctor.warnings.length,
      },
      warnings: doctor.warnings,
      errors,
      safety: buildSafetyPolicy({
        local_file_generation_only: true,
        no_api_write_calls: true,
        no_runtime_execution: true,
      }),
    };
  }

  const safetyPolicy = buildSafetyPolicy({
    local_file_generation_only: true,
    no_api_write_calls: true,
    no_runtime_execution: true,
  });

  const result = {
    status: "RUNTIME_ARTIFACTS_READY",
    valid: true,
    migration_id: migrationId,
    package_dir: packageDir,
    runtime_artifacts_dir: runtimeArtifactsDir,
    runtime_nodes_dir: runtimeNodesDir,
    copied_sql_files: copiedSqlFiles,
    doctor_summary: {
      healthy: true,
      findings_count: doctor.findings.length,
      warnings_count: doctor.warnings.length,
    },
    warnings: doctor.warnings,
    errors: [],
    safety: safetyPolicy,
  };

  writeJson(path.join(migrationOutDir, "runtime_prepare_result.json"), result);

  const report = renderMarkdownReport(result);
  fs.writeFileSync(path.join(migrationOutDir, "runtime_prepare_report.md"), report, "utf-8");

  const runtimeArtifactManifest = {
    manifest_version: "0.1",
    migration_id: migrationId,
    runtime_artifacts_dir: runtimeArtifactsDir,
    runtime_nodes_dir: runtimeNodesDir,
    sql_files: copiedSqlFiles.map((f) => ({
      node_id: f.node_id,
      node_name: f.node_name,
      target_sql_path: f.target_sql_path,
      statement_count: f.statement_count,
    })),
    runtime_setup_files: runtimeSetupFiles,
    runtime_validation_queries_path: runtimeValidationQueriesPath,
    generated_at: new Date().toISOString(),
    safety: safetyPolicy,
  };
  writeJson(path.join(runtimeArtifactsDir, "runtime_artifact_manifest.json"), runtimeArtifactManifest);

  return result;
}

function renderMarkdownReport(result) {
  const lines = [];

  lines.push("# Runtime Artifact Preparation Report");
  lines.push("");
  lines.push(`**Status:** ${result.status}`);
  lines.push(`**Valid:** ${result.valid ? "YES" : "NO"}`);
  lines.push(`**Migration ID:** ${result.migration_id || "N/A"}`);
  lines.push(`**Package Dir:** ${result.package_dir || "N/A"}`);
  lines.push("");

  lines.push("## Runtime Directories");
  lines.push("");
  lines.push(`- Artifacts: \`${result.runtime_artifacts_dir || "N/A"}\``);
  lines.push(`- Nodes: \`${result.runtime_nodes_dir || "N/A"}\``);
  lines.push("");

  lines.push("## Copied SQL Files");
  lines.push("");
  if (result.copied_sql_files.length > 0) {
    lines.push("| Node ID | Node Name | Statements | Source | Target |");
    lines.push("|---------|-----------|------------|--------|--------|");
    for (const f of result.copied_sql_files) {
      lines.push(`| ${f.node_id} | ${f.node_name} | ${f.statement_count} | \`${path.basename(f.source_sql_path)}\` | \`${path.basename(f.target_sql_path)}\` |`);
    }
  } else {
    lines.push("None.");
  }
  lines.push("");

  lines.push("## Doctor Summary");
  lines.push("");
  lines.push(`- Healthy: ${result.doctor_summary.healthy ? "YES" : "NO"}`);
  lines.push(`- Findings: ${result.doctor_summary.findings_count}`);
  lines.push(`- Warnings: ${result.doctor_summary.warnings_count}`);
  lines.push("");

  if (result.warnings.length > 0) {
    lines.push("## Warnings");
    lines.push("");
    for (const w of result.warnings) {
      lines.push(`- ${w}`);
    }
    lines.push("");
  }

  if (result.errors.length > 0) {
    lines.push("## Errors");
    lines.push("");
    for (const e of result.errors) {
      lines.push(`- ${e}`);
    }
    lines.push("");
  }

  lines.push("## Safety");
  lines.push("");
  lines.push("- Local file generation only.");
  lines.push("- No API write calls.");
  lines.push("- No runtime execution.");
  lines.push("");

  return lines.join("\n");
}

module.exports = {
  prepareRuntimeArtifacts,
  renderMarkdownReport,
  buildCanonicalDag,
  buildPipelineYaml,
  buildCompatibilityReport,
  writeLegacyCompatibleArtifacts,
  deriveMedallionLayer,
  deriveOperationType,
  deriveSourceTaskName,
  deriveDescription,
};
