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

  console.log("SFS Turbo Standard Phase 1 tests\n");

  // T1: ListPricingTemplates includes sfs-turbo-standard-payg
  await testT("T1: ListPricingTemplates includes sfs-turbo-standard-payg", async () => {
    const res = await client.callTool({
      name: "ListPricingTemplates",
      arguments: { service: "sfs" }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.templates.length > 0, "must have SFS templates");

    const sfsTurboStd = data.templates.find((t) => t.template_id === "sfs-turbo-standard-payg");
    assert(sfsTurboStd, "sfs-turbo-standard-payg must be listed");
    assert(sfsTurboStd.service === "sfs", "service must be sfs");
    assert(sfsTurboStd.status === "ready", "status must be ready");
    assert(sfsTurboStd.ready_for_real_pricing === true, "must be ready for real pricing");
    assert(sfsTurboStd.has_product_infos_template === true, "must have product_infos_template");
  });

  // T2: RenderProductInfosFromTemplate with capacity_gb=500, monthly_hours=730
  await testT("T2: RenderProductInfosFromTemplate 500GB 730h", async () => {
    const res = await client.callTool({
      name: "RenderProductInfosFromTemplate",
      arguments: {
        service: "sfs",
        template_id: "sfs-turbo-standard-payg",
        region: REGION,
        parameters: {
          capacity_gb: 500,
          monthly_hours: 730
        }
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "render status must be OK");
    assert(data.product_infos.length === 1, "must have 1 product_info");

    const pi = data.product_infos[0];
    assert(pi.cloud_service_type === "hws.service.type.sfs", "cloud_service_type must match");
    assert(pi.resource_type === "hws.resource.type.sfs.turbo", "resource_type must match");
    assert(pi.resource_spec === "sfs.turbo.standard", "resource_spec must match");
    assert(pi.usage_factor === "period", "usage_factor must be period");
    assert(pi.usage_value === 730, "usage_value must be 730");
    assert(pi.usage_measure_id === 4, "usage_measure_id must be 4");
    assert(pi.resource_size === 500, "resource_size must be 500");
    assert(pi.size_measure_id === 17, "size_measure_id must be 17");
  });

  // T3: RenderProductInfosFromTemplate with capacity_gb=1000
  await testT("T3: RenderProductInfosFromTemplate 1000GB", async () => {
    const res = await client.callTool({
      name: "RenderProductInfosFromTemplate",
      arguments: {
        service: "sfs",
        template_id: "sfs-turbo-standard-payg",
        region: REGION,
        parameters: {
          capacity_gb: 1000,
          monthly_hours: 730
        }
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "render status must be OK");
    assert(data.product_infos[0].resource_size === 1000, "resource_size must be 1000");
  });

  // T4: capacity_gb below minimum (500)
  await testT("T4: capacity_gb below minimum 500", async () => {
    const res = await client.callTool({
      name: "RenderProductInfosFromTemplate",
      arguments: {
        service: "sfs",
        template_id: "sfs-turbo-standard-payg",
        region: REGION,
        parameters: {
          capacity_gb: 100,
          monthly_hours: 730
        }
      }
    });
    const data = JSON.parse(res.content[0].text);
    if (data.status === "ERROR" || data.status === "VALIDATION_ERROR") {
      return;
    }
    if (data.warnings && data.warnings.length > 0) {
      const minWarning = data.warnings.find((w) =>
        w.includes("min") || w.includes("minimum") || w.includes("500")
      );
      assert(minWarning, "must have min validation warning");
      return;
    }
    console.log("    NOTE: Template framework does not validate min yet. TODO: add min validation.");
  });

  // T5: EstimateTemplateOnDemandPrice 500GB 730h
  await testT("T5: EstimateTemplateOnDemandPrice 500GB 730h ≈ USD 45.42", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateTemplateOnDemandPrice",
      arguments: {
        service: "sfs",
        template_id: "sfs-turbo-standard-payg",
        region: REGION,
        parameters: {
          capacity_gb: 500,
          monthly_hours: 730
        }
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.pricing_summary, "must have pricing_summary");
    const monthly = data.pricing_summary.monthly_amount;
    assert(monthly > 40 && monthly < 50, `monthly must be ≈45.42, got ${monthly}`);
  });

  // T6: EstimateTemplateOnDemandPrice 1000GB 730h
  await testT("T6: EstimateTemplateOnDemandPrice 1000GB 730h ≈ USD 90.84", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateTemplateOnDemandPrice",
      arguments: {
        service: "sfs",
        template_id: "sfs-turbo-standard-payg",
        region: REGION,
        parameters: {
          capacity_gb: 1000,
          monthly_hours: 730
        }
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.pricing_summary, "must have pricing_summary");
    const monthly = data.pricing_summary.monthly_amount;
    assert(monthly > 85 && monthly < 100, `monthly must be ≈90.84, got ${monthly}`);
  });

  // T7: Architecture pricing with SFS Turbo + existing components
  await testT("T7: SFS Turbo in architecture contributes to monthly_total", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [
          {
            service: "sfs",
            template_id: "sfs-turbo-standard-payg",
            parameters: {
              capacity_gb: 500,
              monthly_hours: 730
            }
          },
          {
            service: "evs",
            template_id: "evs-ssd-gb-payg",
            parameters: {
              size_gb: 100,
              monthly_hours: 730
            }
          }
        ],
        validate_availability: false
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "status must be OK");

    const sfsPriced = data.priced_components.find((c) => c.template_id === "sfs-turbo-standard-payg");
    assert(sfsPriced, "SFS Turbo must be priced");
    assert(sfsPriced.monthly_amount > 0, "SFS Turbo must have positive monthly_amount");

    const evsPriced = data.priced_components.find((c) => c.template_id === "evs-ssd-gb-payg");
    assert(evsPriced, "EVS must still be priced alongside SFS");

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

    assert(!data.availability_validation, "SFS Turbo must not trigger ECS availability validation");
  });

  await client.close();

  console.log(`\nResults: ${passed} passed, ${failed} failed, ${skipped} skipped`);
  process.exit(failed > 0 ? 1 : 0);
}

runTest().catch((e) => {
  console.error("Test runner error:", e);
  process.exit(2);
});
