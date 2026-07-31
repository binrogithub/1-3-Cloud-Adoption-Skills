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

  console.log("DCS Redis Instance Fase 1 tests\n");

  // T1: ListPricingTemplates includes dcs-redis-instance-payg
  await testT("T1: ListPricingTemplates includes dcs-redis-instance-payg", async () => {
    const res = await client.callTool({
      name: "ListPricingTemplates",
      arguments: { service: "dcs" }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.templates.length > 0, "must have DCS templates");

    const dcsInst = data.templates.find((t) => t.template_id === "dcs-redis-instance-payg");
    assert(dcsInst, "dcs-redis-instance-payg must be listed");
    assert(dcsInst.service === "dcs", "service must be dcs");
    assert(dcsInst.status === "ready", "status must be ready");
    assert(dcsInst.ready_for_real_pricing === true, "must be ready for real pricing");
    assert(dcsInst.has_product_infos_template === true, "must have product_infos_template");
  });

  // T2: RenderProductInfosFromTemplate with default params
  await testT("T2: RenderProductInfosFromTemplate with default params", async () => {
    const res = await client.callTool({
      name: "RenderProductInfosFromTemplate",
      arguments: {
        service: "dcs",
        template_id: "dcs-redis-instance-payg",
        region: REGION,
        parameters: {}
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "render status must be OK");
    assert(data.product_infos.length === 1, "must have 1 product_info");

    const pi = data.product_infos[0];
    assert(pi.cloud_service_type === "hws.service.type.dcs", "cloud_service_type must match");
    assert(pi.resource_type === "hws.resource.type.dcs3", "resource_type must match");
    assert(pi.resource_spec === "redis.single.xu1.large.2", "resource_spec must be default");
    assert(pi.usage_factor === "duration", "usage_factor must be duration");
    assert(pi.usage_value === 730, "usage_value must be 730");
    assert(pi.usage_measure_id === 4, "usage_measure_id must be 4");
    assert(pi.subscription_num === 1, "subscription_num must be 1");
  });

  // T3: RenderProductInfosFromTemplate with redis.ha.xu1.large.r2.2
  await testT("T3: RenderProductInfosFromTemplate with redis.ha.xu1.large.r2.2", async () => {
    const res = await client.callTool({
      name: "RenderProductInfosFromTemplate",
      arguments: {
        service: "dcs",
        template_id: "dcs-redis-instance-payg",
        region: REGION,
        parameters: {
          instance_resource_spec: "redis.ha.xu1.large.r2.2"
        }
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "render status must be OK");
    assert(data.product_infos[0].resource_spec === "redis.ha.xu1.large.r2.2", "resource_spec must match override");
  });

  // T4: RenderProductInfosFromTemplate with redis.cluster.xu1.large.r1.4
  await testT("T4: RenderProductInfosFromTemplate with redis.cluster.xu1.large.r1.4", async () => {
    const res = await client.callTool({
      name: "RenderProductInfosFromTemplate",
      arguments: {
        service: "dcs",
        template_id: "dcs-redis-instance-payg",
        region: REGION,
        parameters: {
          instance_resource_spec: "redis.cluster.xu1.large.r1.4"
        }
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "render status must be OK");
    assert(data.product_infos[0].resource_spec === "redis.cluster.xu1.large.r1.4", "resource_spec must match override");
  });

  // T5: EstimateTemplateOnDemandPrice redis.single.xu1.large.2 730h
  await testT("T5: EstimateTemplateOnDemandPrice redis.single.xu1.large.2 730h ≈ USD 24.82", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateTemplateOnDemandPrice",
      arguments: {
        service: "dcs",
        template_id: "dcs-redis-instance-payg",
        region: REGION,
        parameters: {
          instance_resource_spec: "redis.single.xu1.large.2",
          monthly_hours: 730
        }
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.pricing_summary, "must have pricing_summary");
    const monthly = data.pricing_summary.monthly_amount;
    assert(monthly > 20 && monthly < 30, `monthly must be ≈24.82, got ${monthly}`);
  });

  // T6: EstimateTemplateOnDemandPrice redis.ha.xu1.large.r2.2 730h
  await testT("T6: EstimateTemplateOnDemandPrice redis.ha.xu1.large.r2.2 730h ≈ USD 49.64", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateTemplateOnDemandPrice",
      arguments: {
        service: "dcs",
        template_id: "dcs-redis-instance-payg",
        region: REGION,
        parameters: {
          instance_resource_spec: "redis.ha.xu1.large.r2.2",
          monthly_hours: 730
        }
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.pricing_summary, "must have pricing_summary");
    const monthly = data.pricing_summary.monthly_amount;
    assert(monthly > 40 && monthly < 60, `monthly must be ≈49.64, got ${monthly}`);
  });

  // T7: Architecture pricing with DCS Redis + SFS Turbo
  await testT("T7: DCS Redis instance in architecture contributes to monthly_total", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [
          {
            service: "dcs",
            template_id: "dcs-redis-instance-payg",
            parameters: {
              instance_resource_spec: "redis.single.xu1.large.2",
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

    const dcsPriced = data.priced_components.find((c) => c.template_id === "dcs-redis-instance-payg");
    assert(dcsPriced, "DCS Redis instance must be priced");
    assert(dcsPriced.monthly_amount > 0, "DCS Redis instance must have positive monthly_amount");

    const sfsPriced = data.priced_components.find((c) => c.template_id === "sfs-turbo-standard-payg");
    assert(sfsPriced, "SFS Turbo must still be priced alongside DCS");

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

    assert(!data.availability_validation, "DCS must not trigger ECS availability validation");
  });

  // T8: No DCS bandwidth/OBS/shard templates in Fase 1
  await testT("T8: No DCS bandwidth/OBS/shard templates in Fase 1", async () => {
    const res = await client.callTool({
      name: "ListPricingTemplates",
      arguments: { service: "dcs" }
    });
    const data = JSON.parse(res.content[0].text);
    const dcsBw = data.templates.find((t) => t.template_id === "dcs-bandwidth-payg");
    assert(!dcsBw, "dcs-bandwidth-payg must NOT exist in Fase 1");

    const dcsObs = data.templates.find((t) => t.template_id === "dcs-obs-backup-payg");
    assert(!dcsObs, "dcs-obs-backup-payg must NOT exist in Fase 1");

    const dcsShard = data.templates.find((t) => t.template_id === "dcs-shard-payg");
    assert(!dcsShard, "dcs-shard-payg must NOT exist in Fase 1");

    const dcsInst = data.templates.find((t) => t.template_id === "dcs-redis-instance-payg");
    assert(dcsInst, "dcs-redis-instance-payg must exist");

    const desc = dcsInst.description || "";
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
