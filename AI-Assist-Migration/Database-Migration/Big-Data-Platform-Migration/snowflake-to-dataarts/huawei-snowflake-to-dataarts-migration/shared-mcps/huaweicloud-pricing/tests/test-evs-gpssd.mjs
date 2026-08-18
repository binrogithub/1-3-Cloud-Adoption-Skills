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

  console.log("EVS GPSSD Phase 1 tests\n");

  // T1: ListPricingTemplates includes evs-gpssd-gb-payg
  await testT("T1: ListPricingTemplates includes evs-gpssd-gb-payg", async () => {
    const res = await client.callTool({
      name: "ListPricingTemplates",
      arguments: { service: "evs" }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.templates.length > 0, "must have EVS templates");

    const gpssd = data.templates.find((t) => t.template_id === "evs-gpssd-gb-payg");
    assert(gpssd, "evs-gpssd-gb-payg must be listed");
    assert(gpssd.service === "evs", "service must be evs");
    assert(gpssd.status === "ready", "status must be ready");
    assert(gpssd.ready_for_real_pricing === true, "must be ready for real pricing");
    assert(gpssd.has_product_infos_template === true, "must have product_infos_template");
  });

  // T2: RenderProductInfosFromTemplate with defaults
  await testT("T2: RenderProductInfosFromTemplate with defaults", async () => {
    const res = await client.callTool({
      name: "RenderProductInfosFromTemplate",
      arguments: {
        service: "evs",
        template_id: "evs-gpssd-gb-payg",
        region: REGION
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "render status must be OK");
    assert(data.product_infos.length === 1, "must have 1 product_info");

    const pi = data.product_infos[0];
    assert(pi.cloud_service_type === "hws.service.type.ebs", "cloud_service_type must match");
    assert(pi.resource_type === "hws.resource.type.volume", "resource_type must match");
    assert(pi.resource_spec === "GPSSD", "resource_spec must be GPSSD");
    assert(pi.usage_factor === "Duration", "usage_factor must be Duration");
    assert(pi.usage_value === 730, "usage_value must be 730");
    assert(pi.usage_measure_id === 4, "usage_measure_id must be 4");
    assert(pi.resource_size === 100, "resource_size must be 100");
    assert(pi.size_measure_id === 17, "size_measure_id must be 17");
    assert(pi.subscription_num === 1, "subscription_num must be 1");
  });

  // T3: RenderProductInfosFromTemplate with size_gb=200
  await testT("T3: RenderProductInfosFromTemplate size_gb=200", async () => {
    const res = await client.callTool({
      name: "RenderProductInfosFromTemplate",
      arguments: {
        service: "evs",
        template_id: "evs-gpssd-gb-payg",
        region: REGION,
        parameters: { size_gb: 200 }
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "render status must be OK");
    assert(data.product_infos[0].resource_size === 200, "resource_size must be 200");
    assert(data.product_infos[0].resource_spec === "GPSSD", "resource_spec must be GPSSD");
  });

  // T4: EstimateTemplateOnDemandPrice 200GB 730h ≈ USD 18.98
  await testT("T4: EstimateTemplateOnDemandPrice 200GB 730h ≈ USD 18.98", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateTemplateOnDemandPrice",
      arguments: {
        service: "evs",
        template_id: "evs-gpssd-gb-payg",
        region: REGION,
        parameters: { size_gb: 200, monthly_hours: 730 }
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.pricing_summary, "must have pricing_summary");
    const monthly = data.pricing_summary.monthly_amount;
    assert(monthly > 18 && monthly < 20, `monthly must be ≈18.98, got ${monthly}`);
  });

  // T5: EstimateTemplateOnDemandPrice 300GB 730h ≈ USD 28.47
  await testT("T5: EstimateTemplateOnDemandPrice 300GB 730h ≈ USD 28.47", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateTemplateOnDemandPrice",
      arguments: {
        service: "evs",
        template_id: "evs-gpssd-gb-payg",
        region: REGION,
        parameters: { size_gb: 300, monthly_hours: 730 }
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.pricing_summary, "must have pricing_summary");
    const monthly = data.pricing_summary.monthly_amount;
    assert(monthly > 27 && monthly < 30, `monthly must be ≈28.47, got ${monthly}`);
  });

  // T6: EstimateTemplateOnDemandPrice 700GB 730h ≈ USD 66.43
  await testT("T6: EstimateTemplateOnDemandPrice 700GB 730h ≈ USD 66.43", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateTemplateOnDemandPrice",
      arguments: {
        service: "evs",
        template_id: "evs-gpssd-gb-payg",
        region: REGION,
        parameters: { size_gb: 700, monthly_hours: 730 }
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.pricing_summary, "must have pricing_summary");
    const monthly = data.pricing_summary.monthly_amount;
    assert(monthly > 64 && monthly < 68, `monthly must be ≈66.43, got ${monthly}`);
  });

  // T7: Architecture pricing with three EVS GPSSD disks
  await testT("T7: Architecture 700+300+200 GB GPSSD ≈ USD 113.88", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [
          {
            service: "evs",
            template_id: "evs-gpssd-gb-payg",
            parameters: { size_gb: 700, monthly_hours: 730 }
          },
          {
            service: "evs",
            template_id: "evs-gpssd-gb-payg",
            parameters: { size_gb: 300, monthly_hours: 730 }
          },
          {
            service: "evs",
            template_id: "evs-gpssd-gb-payg",
            parameters: { size_gb: 200, monthly_hours: 730 }
          }
        ],
        validate_availability: false
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "status must be OK");

    const total = data.pricing_summary.monthly_total_calculated;
    assert(total > 110 && total < 120, `total must be ≈113.88, got ${total}`);

    assert(
      data.pricing_summary.monthly_total_calculated === data.pricing_summary.monthly_total_validated,
      "monthly_total_calculated must equal monthly_total_validated"
    );

    let sumFromPriced = 0;
    for (const comp of data.priced_components) {
      sumFromPriced += comp.monthly_amount;
    }
    assert(
      Math.abs(data.pricing_summary.monthly_total_calculated - sumFromPriced) < 0.01,
      "monthly_total must equal sum of priced components"
    );
  });

  // T8: evs-gpssd-gb-payg does NOT replace evs-ssd-gb-payg
  await testT("T8: Both evs-ssd-gb-payg and evs-gpssd-gb-payg coexist", async () => {
    const res = await client.callTool({
      name: "ListPricingTemplates",
      arguments: { service: "evs" }
    });
    const data = JSON.parse(res.content[0].text);

    const ssd = data.templates.find((t) => t.template_id === "evs-ssd-gb-payg");
    const gpssd = data.templates.find((t) => t.template_id === "evs-gpssd-gb-payg");

    assert(ssd, "evs-ssd-gb-payg must still exist");
    assert(gpssd, "evs-gpssd-gb-payg must exist");
    assert(ssd.status === "ready", "evs-ssd-gb-payg must be ready");
    assert(gpssd.status === "ready", "evs-gpssd-gb-payg must be ready");

    const ssdRender = await client.callTool({
      name: "RenderProductInfosFromTemplate",
      arguments: { service: "evs", template_id: "evs-ssd-gb-payg", region: REGION }
    });
    const ssdData = JSON.parse(ssdRender.content[0].text);
    assert(ssdData.product_infos[0].resource_spec === "SSD", "SSD template must still use SSD spec");

    const gpssdRender = await client.callTool({
      name: "RenderProductInfosFromTemplate",
      arguments: { service: "evs", template_id: "evs-gpssd-gb-payg", region: REGION }
    });
    const gpssdData = JSON.parse(gpssdRender.content[0].text);
    assert(gpssdData.product_infos[0].resource_spec === "GPSSD", "GPSSD template must use GPSSD spec");
  });

  await client.close();

  console.log(`\nResults: ${passed} passed, ${failed} failed, ${skipped} skipped`);
  process.exit(failed > 0 ? 1 : 0);
}

runTest().catch((e) => {
  console.error("Test runner error:", e);
  process.exit(2);
});
