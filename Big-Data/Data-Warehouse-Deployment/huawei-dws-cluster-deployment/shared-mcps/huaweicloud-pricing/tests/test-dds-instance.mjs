import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

function assert(cond, msg) {
  if (!cond) throw new Error(`ASSERTION FAILED: ${msg}`);
}

const RUN_LIVE_API = process.env.RUN_LIVE_API === "true";
function requireLiveApi(reason) {
  if (!RUN_LIVE_API) return `SKIP_LIVE_API: ${reason}`;
  return null;
}

async function runTest() {
  const transport = new StdioClientTransport({
    command: "node",
    args: ["server.mjs"],
    env: { ...process.env }
  });

  const client = new Client({ name: "test-client", version: "1.0.0" });
  await client.connect(transport);

  const tools = await client.listTools();
  const listTool = tools.tools.find((t) => t.name === "ListPricingTemplates");
  assert(listTool, "ListPricingTemplates tool must be registered");
  const renderTool = tools.tools.find((t) => t.name === "RenderProductInfosFromTemplate");
  assert(renderTool, "RenderProductInfosFromTemplate tool must be registered");
  const estimateTool = tools.tools.find((t) => t.name === "EstimateTemplateOnDemandPrice");
  assert(estimateTool, "EstimateTemplateOnDemandPrice tool must be registered");
  const archTool = tools.tools.find((t) => t.name === "EstimateArchitectureOnDemandPrice");
  assert(archTool, "EstimateArchitectureOnDemandPrice tool must be registered");

  let passed = 0;
  let failed = 0;
  let skipped = 0;

  async function testT(name, fn) {
    try {
      const result = await fn();
      if (result === "skip" || (typeof result === "string" && result.startsWith("SKIP_LIVE_API:"))) {
        console.log(`  SKIP: ${name} (${result})`);
        skipped++;
      } else {
        console.log(`  PASS: ${name}`);
        passed++;
      }
    } catch (e) {
      console.log(`  FAIL: ${name}: ${e.message}`);
      failed++;
    }
  }

  const REGION = "la-north-2";

  console.log("DDS Instance Fase 1 tests\n");

  // T1: ListPricingTemplates includes dds-instance-payg
  await testT("T1: ListPricingTemplates includes dds-instance-payg", async () => {
    const res = await client.callTool({
      name: "ListPricingTemplates",
      arguments: { service: "dds" }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.templates.length > 0, "must have DDS templates");

    const ddsInst = data.templates.find((t) => t.template_id === "dds-instance-payg");
    assert(ddsInst, "dds-instance-payg must be listed");
    assert(ddsInst.service === "dds", "service must be dds");
    assert(ddsInst.status === "ready", "status must be ready");
    assert(ddsInst.ready_for_real_pricing === true, "must be ready for real pricing");
    assert(ddsInst.has_product_infos_template === true, "must have product_infos_template");
  });

  // T2: RenderProductInfosFromTemplate with default params
  await testT("T2: RenderProductInfosFromTemplate with default params", async () => {
    const res = await client.callTool({
      name: "RenderProductInfosFromTemplate",
      arguments: {
        service: "dds",
        template_id: "dds-instance-payg",
        region: REGION,
        parameters: {}
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "render status must be OK");
    assert(data.product_infos.length === 1, "must have 1 product_info");

    const pi = data.product_infos[0];
    assert(pi.cloud_service_type === "hws.service.type.dds", "cloud_service_type must match");
    assert(pi.resource_type === "hws.resource.type.dds.vm", "resource_type must match");
    assert(pi.resource_spec === "dds.mongodb.s6.medium.4.repset", "resource_spec must be default");
    assert(pi.usage_factor === "duration", "usage_factor must be duration");
    assert(pi.usage_value === 730, "usage_value must be 730");
    assert(pi.usage_measure_id === 4, "usage_measure_id must be 4");
    assert(pi.subscription_num === 1, "subscription_num must be 1");
  });

  // T3: RenderProductInfosFromTemplate with dds.mongodb.s6.large.2.repset
  await testT("T3: RenderProductInfosFromTemplate with s6.large.2.repset", async () => {
    const res = await client.callTool({
      name: "RenderProductInfosFromTemplate",
      arguments: {
        service: "dds",
        template_id: "dds-instance-payg",
        region: REGION,
        parameters: {
          instance_resource_spec: "dds.mongodb.s6.large.2.repset"
        }
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "render status must be OK");
    assert(data.product_infos[0].resource_spec === "dds.mongodb.s6.large.2.repset", "resource_spec must match override");
  });

  // T4: EstimateTemplateOnDemandPrice dds.mongodb.s6.medium.4.repset 730h
  await testT("T4: EstimateTemplateOnDemandPrice s6.medium.4.repset 730h ≈ USD 102.20", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateTemplateOnDemandPrice",
      arguments: {
        service: "dds",
        template_id: "dds-instance-payg",
        region: REGION,
        parameters: {
          instance_resource_spec: "dds.mongodb.s6.medium.4.repset",
          monthly_hours: 730
        }
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.pricing_summary, "must have pricing_summary");
    const monthly = data.pricing_summary.monthly_amount;
    assert(monthly > 95 && monthly < 110, `monthly must be ≈102.20, got ${monthly}`);
  });

  // T5: EstimateTemplateOnDemandPrice dds.mongodb.s6.large.2.repset 730h
  await testT("T5: EstimateTemplateOnDemandPrice s6.large.2.repset 730h ≈ USD 184.69", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateTemplateOnDemandPrice",
      arguments: {
        service: "dds",
        template_id: "dds-instance-payg",
        region: REGION,
        parameters: {
          instance_resource_spec: "dds.mongodb.s6.large.2.repset",
          monthly_hours: 730
        }
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.pricing_summary, "must have pricing_summary");
    const monthly = data.pricing_summary.monthly_amount;
    assert(monthly > 175 && monthly < 195, `monthly must be ≈184.69, got ${monthly}`);
  });

  // T6: Architecture pricing with DDS instance + SFS Turbo
  await testT("T6: DDS instance in architecture contributes to monthly_total", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [
          {
            service: "dds",
            template_id: "dds-instance-payg",
            parameters: {
              instance_resource_spec: "dds.mongodb.s6.medium.4.repset",
              monthly_hours: 730
            }
          },
          {
            service: "sfs",
            template_id: "sfs-turbo-standard-payg",
            parameters: {
              capacity_gb: 500,
              monthly_hours: 730
            }
          }
        ],
        validate_availability: false
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "status must be OK");

    const ddsPriced = data.priced_components.find((c) => c.template_id === "dds-instance-payg");
    assert(ddsPriced, "DDS instance must be priced");
    assert(ddsPriced.monthly_amount > 0, "DDS instance must have positive monthly_amount");

    const sfsPriced = data.priced_components.find((c) => c.template_id === "sfs-turbo-standard-payg");
    assert(sfsPriced, "SFS Turbo must still be priced alongside DDS");

    assert(
      data.pricing_summary.monthly_total_calculated === data.pricing_summary.monthly_total_validated,
      "monthly_total must equal monthly_total_validated"
    );

    let sumFromPriced = 0;
    for (const comp of data.priced_components) {
      sumFromPriced += comp.monthly_amount;
    }
    assert(
      Math.abs(data.pricing_summary.monthly_total_calculated - sumFromPriced) < 0.01,
      "monthly_total must equal sum of priced components"
    );

    assert(!data.availability_validation, "DDS must not trigger ECS availability validation");
  });

  // T7: No DDS volume/backup templates in Fase 1
  await testT("T7: No DDS volume/backup templates in Fase 1", async () => {
    const res = await client.callTool({
      name: "ListPricingTemplates",
      arguments: { service: "dds" }
    });
    const data = JSON.parse(res.content[0].text);
    const ddsVolume = data.templates.find((t) => t.template_id === "dds-volume-payg");
    assert(!ddsVolume, "dds-volume-payg must NOT exist in Fase 1");

    const ddsBackup = data.templates.find((t) => t.template_id === "dds-backup-payg");
    assert(!ddsBackup, "dds-backup-payg must NOT exist in Fase 1");

    const ddsInst = data.templates.find((t) => t.template_id === "dds-instance-payg");
    assert(ddsInst, "dds-instance-payg must exist");

    const desc = ddsInst.description || "";
    assert(
      desc.includes("instance") && (desc.includes("hour") || desc.includes("per hour")),
      "description must indicate instance-only hourly pricing"
    );
  });

  await client.close();

  console.log(`\nResults: ${passed} passed, ${failed} failed, ${skipped} skipped`);
  process.exit(failed > 0 ? 1 : 0);
}

runTest().catch((e) => {
  console.error("Test runner error:", e);
  process.exit(2);
});
