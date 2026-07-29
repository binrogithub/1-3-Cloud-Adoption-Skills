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

  console.log("VPC Bandwidth Traffic (vpc-bandwidth-traffic-gb-payg) tests\n");

  await testT("T1: ListPricingTemplates includes vpc-bandwidth-traffic-gb-payg", async () => {
    const res = await client.callTool({
      name: "ListPricingTemplates",
      arguments: { service: "vpc" }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.templates.length > 0, "must have VPC templates");

    const tpl = data.templates.find((t) => t.template_id === "vpc-bandwidth-traffic-gb-payg");
    assert(tpl, "vpc-bandwidth-traffic-gb-payg must be listed");
    assert(tpl.service === "vpc", "service must be vpc");
    assert(tpl.status === "ready", "status must be ready");
    assert(tpl.ready_for_real_pricing === true, "must be ready for real pricing");
    assert(tpl.has_product_infos_template === true, "must have product_infos_template");

    const pi = tpl.product_infos_template || tpl.product_infos_preview;
    if (pi && pi.length > 0) {
      const entry = pi[0];
      assert(entry.resource_type === "hws.resource.type.bandwidth", "resource_type must be hws.resource.type.bandwidth");
      assert(entry.usage_factor === "upflow", "usage_factor must be upflow");
      assert(entry.usage_measure_id === 10, "usage_measure_id must be 10");
    }
  });

  await testT("T2: RenderProductInfosFromTemplate with default params", async () => {
    const res = await client.callTool({
      name: "RenderProductInfosFromTemplate",
      arguments: {
        service: "vpc",
        template_id: "vpc-bandwidth-traffic-gb-payg",
        region: REGION,
        parameters: {}
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "render status must be OK");
    assert(data.product_infos.length === 1, "must have 1 product_info");

    const pi = data.product_infos[0];
    assert(pi.cloud_service_type === "hws.service.type.vpc", "cloud_service_type must match");
    assert(pi.resource_type === "hws.resource.type.bandwidth", "resource_type must match");
    assert(pi.resource_spec === "12_bgp", "resource_spec must be default 12_bgp");
    assert(pi.usage_factor === "upflow", "usage_factor must be upflow");
    assert(pi.usage_value === 300, "usage_value must be 300 (default traffic_gb)");
    assert(pi.usage_measure_id === 10, "usage_measure_id must be 10");
    assert(pi.subscription_num === 1, "subscription_num must be 1");
  });

  await testT("T3: RenderProductInfosFromTemplate with traffic_resource_spec=12_share, traffic_gb=200", async () => {
    const res = await client.callTool({
      name: "RenderProductInfosFromTemplate",
      arguments: {
        service: "vpc",
        template_id: "vpc-bandwidth-traffic-gb-payg",
        region: REGION,
        parameters: {
          traffic_resource_spec: "12_share",
          traffic_gb: 200
        }
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "render status must be OK");
    assert(data.product_infos.length === 1, "must have 1 product_info");

    const pi = data.product_infos[0];
    assert(pi.resource_spec === "12_share", "resource_spec must be 12_share");
    assert(pi.usage_value === 200, "usage_value must be 200");
  });

  await testT("T4: EstimateTemplateOnDemandPrice 12_bgp 300GB ≈ USD 24.30", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateTemplateOnDemandPrice",
      arguments: {
        service: "vpc",
        template_id: "vpc-bandwidth-traffic-gb-payg",
        region: REGION,
        parameters: {
          traffic_resource_spec: "12_bgp",
          traffic_gb: 300
        }
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.pricing_summary, "must have pricing_summary");
    const monthly = data.pricing_summary.monthly_amount;
    assert(monthly > 23.5 && monthly < 25.0, `monthly must be ≈24.30, got ${monthly}`);
  });

  await testT("T5: EstimateTemplateOnDemandPrice 12_share 200GB ≈ USD 16.20", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateTemplateOnDemandPrice",
      arguments: {
        service: "vpc",
        template_id: "vpc-bandwidth-traffic-gb-payg",
        region: REGION,
        parameters: {
          traffic_resource_spec: "12_share",
          traffic_gb: 200
        }
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.pricing_summary, "must have pricing_summary");
    const monthly = data.pricing_summary.monthly_amount;
    assert(monthly > 15.5 && monthly < 17.0, `monthly must be ≈16.20, got ${monthly}`);
  });

  await testT("T6: Architecture 2× vpc-bandwidth-traffic-gb-payg 12_bgp 300GB ≈ USD 48.61", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [
          {
            service: "vpc",
            template_id: "vpc-bandwidth-traffic-gb-payg",
            parameters: {
              traffic_resource_spec: "12_bgp",
              traffic_gb: 300
            }
          },
          {
            service: "vpc",
            template_id: "vpc-bandwidth-traffic-gb-payg",
            parameters: {
              traffic_resource_spec: "12_bgp",
              traffic_gb: 300
            }
          }
        ],
        validate_availability: false
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "status must be OK");
    assert(data.priced_components.length === 2, "must have 2 priced components");

    const total = data.pricing_summary.monthly_total_calculated;
    assert(total > 47.0 && total < 50.0, `total must be ≈48.60-48.61, got ${total}`);

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

  await testT("T7: vpc-bandwidth-traffic-gb-payg does not conflict with eip-bandwidth-mbps-payg", async () => {
    const resVpc = await client.callTool({
      name: "ListPricingTemplates",
      arguments: { service: "vpc" }
    });
    const dataVpc = JSON.parse(resVpc.content[0].text);
    const trafficTpl = dataVpc.templates.find((t) => t.template_id === "vpc-bandwidth-traffic-gb-payg");
    assert(trafficTpl, "vpc-bandwidth-traffic-gb-payg must exist");

    const resEip = await client.callTool({
      name: "ListPricingTemplates",
      arguments: { service: "eip" }
    });
    const dataEip = JSON.parse(resEip.content[0].text);
    const eipTpl = dataEip.templates.find((t) => t.template_id === "eip-bandwidth-mbps-payg");
    assert(eipTpl, "eip-bandwidth-mbps-payg must exist");

    assert(trafficTpl.unit === "GB", "traffic template unit must be GB");
    assert(eipTpl.unit === "mbps_month", "EIP template unit must be mbps_month");

    const trafficRender = await client.callTool({
      name: "RenderProductInfosFromTemplate",
      arguments: {
        service: "vpc",
        template_id: "vpc-bandwidth-traffic-gb-payg",
        region: REGION,
        parameters: {}
      }
    });
    const trafficData = JSON.parse(trafficRender.content[0].text);
    const trafficPi = trafficData.product_infos[0];
    assert(trafficPi.usage_factor === "upflow", "traffic template uses upflow");
    assert(trafficPi.usage_measure_id === 10, "traffic template uses GB (measure_id=10)");
    assert(!trafficPi.resource_size, "traffic template must NOT use resource_size");

    const eipRender = await client.callTool({
      name: "RenderProductInfosFromTemplate",
      arguments: {
        service: "eip",
        template_id: "eip-bandwidth-mbps-payg",
        region: REGION,
        parameters: {}
      }
    });
    const eipData = JSON.parse(eipRender.content[0].text);
    const eipPi = eipData.product_infos[0];
    assert(eipPi.usage_factor === "Duration", "EIP template uses Duration");
    assert(eipPi.usage_measure_id === 4, "EIP template uses Hour (measure_id=4)");
    assert(eipPi.resource_size !== undefined, "EIP template uses resource_size for Mbps");
  });

  await client.close();

  console.log(`\nResults: ${passed} passed, ${failed} failed, ${skipped} skipped`);
  process.exit(failed > 0 ? 1 : 0);
}

runTest().catch((e) => {
  console.error("Test runner error:", e);
  process.exit(2);
});
