const fs = require("fs");
const path = require("path");
const config = require("./config");
const { loadAll } = require("./load-artifacts");
const { generatePayload, generateV1Request, generateReadinessReport } = require("./generate-dataarts-payload");

function main() {
  console.log("=== DataArts Deploy Agent: DRY RUN ===\n");

  try {
    const parsed = config.load();
    config.validate(parsed);

    const artifactsDir = config.getArtifactsDir(parsed);
    if (!fs.existsSync(artifactsDir)) {
      throw new Error(`DATAARTS_ARTIFACTS_DIR does not exist: ${artifactsDir}`);
    }

    console.log(`Loading artifacts from: ${artifactsDir}`);
    const artifacts = loadAll(artifactsDir);
    console.log(`  canonical_dag.json: ${artifacts.canonicalDag.dag.total_nodes} nodes`);
    console.log(`  dataarts_pipeline.yaml: ${artifacts.pipelineYaml.nodes.length} nodes, cron=${artifacts.pipelineYaml.schedule.cron}`);
    console.log(`  SQL nodes: ${Object.keys(artifacts.sqlNodes).join(", ")}`);
    console.log("");

    console.log("Generating DataArts Create Job payload...");
    const payload = generatePayload(artifacts, parsed);
    console.log(`  Job name: ${payload.job.name}`);
    console.log(`  Workspace: ${payload.job.workspace_id}`);
    console.log(`  Region: ${payload.job.region}`);
    console.log(`  Nodes: ${payload.job.total_nodes}`);
    console.log("");

    const outDir = path.resolve(__dirname, "..", "out");
    if (!fs.existsSync(outDir)) {
      fs.mkdirSync(outDir, { recursive: true });
    }

    const payloadPath = path.join(outDir, "dataarts_create_job_payload.dryrun.json");
    fs.writeFileSync(payloadPath, JSON.stringify(payload, null, 2), "utf-8");
    console.log(`Payload saved: ${payloadPath}`);

    console.log("Generating DataArts v1 Create Job request...");
    const v1Request = generateV1Request(artifacts, parsed, payload);
    const v1Path = path.join(outDir, "dataarts_create_job_request.v1.dryrun.json");
    fs.writeFileSync(v1Path, JSON.stringify(v1Request, null, 2), "utf-8");
    console.log(`V1 request saved: ${v1Path}`);

    console.log("Generating deployment readiness report...");
    const report = generateReadinessReport(artifacts, parsed, payload, v1Request);
    const reportPath = path.join(outDir, "deployment_readiness_report.md");
    fs.writeFileSync(reportPath, report, "utf-8");
    console.log(`Report saved: ${reportPath}`);

    console.log("\nDRY RUN COMPLETE. No API calls were made.");
    process.exit(0);
  } catch (err) {
    console.error(`DRY RUN FAILED: ${err.message}`);
    process.exit(1);
  }
}

main();
