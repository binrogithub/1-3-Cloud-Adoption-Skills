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

  console.log("NAT Gateway Public Fase 1 tests\n");

  await testT("T1: ListPricingTemplates includes nat-gateway-public-payg", async () => {
    const res = await client.callTool({
      name: "ListPricingTemplates",
      arguments: { service: "natgateway" }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.templates.length > 0, "must have NAT Gateway templates");

    const natPub = data.templates.find((t) => t.template_id === "nat-gateway-public-payg");
    assert(natPub, "nat-gateway-public-payg must be listed");
    assert(natPub.service === "natgateway", "service must be natgateway");
    assert(natPub.status === "ready", "status must be ready");
    assert(natPub.ready_for_real_pricing === true, "must be ready for real pricing");
    assert(natPub.has_product_infos_template === true, "must have product_infos_template");

    const params = natPub.parameters || {};
    assert(params.nat_resource_spec, "must have nat_resource_spec parameter");
    assert(params.nat_resource_spec.default === "natgateway_small", "default nat_resource_spec must be natgateway_small");
    assert(params.usage_days, "must have usage_days parameter");
    assert(params.usage_days.default === 30, "default usage_days must be 30");
  });

  await testT("T2: RenderProductInfosFromTemplate with default params", async () => {
    const res = await client.callTool({
      name: "RenderProductInfosFromTemplate",
      arguments: {
        service: "natgateway",
        template_id: "nat-gateway-public-payg",
        region: REGION,
        parameters: {}
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "render status must be OK");
    assert(data.product_infos.length === 1, "must have 1 product_info");

    const pi = data.product_infos[0];
    assert(pi.cloud_service_type === "hws.service.type.natgateway", "cloud_service_type must match");
    assert(pi.resource_type === "hws.resource.type.natgateway", "resource_type must match");
    assert(pi.resource_spec === "natgateway_small", "resource_spec must be default natgateway_small");
    assert(pi.usage_factor === "duration", "usage_factor must be duration");
    assert(pi.usage_value === 30, "usage_value must be 30 (default usage_days)");
    assert(pi.usage_measure_id === 0, "usage_measure_id must be 0 (days)");
    assert(pi.subscription_num === 1, "subscription_num must be 1");
  });

  await testT("T3: RenderProductInfosFromTemplate with natgateway_middle", async () => {
    const res = await client.callTool({
      name: "RenderProductInfosFromTemplate",
      arguments: {
        service: "natgateway",
        template_id: "nat-gateway-public-payg",
        region: REGION,
        parameters: {
          nat_resource_spec: "natgateway_middle"
        }
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "render status must be OK");
    assert(data.product_infos[0].resource_spec === "natgateway_middle", "resource_spec must be natgateway_middle");
  });

  await testT("T4: RenderProductInfosFromTemplate with usage_days=15", async () => {
    const res = await client.callTool({
      name: "RenderProductInfosFromTemplate",
      arguments: {
        service: "natgateway",
        template_id: "nat-gateway-public-payg",
        region: REGION,
        parameters: {
          usage_days: 15
        }
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "render status must be OK");
    assert(data.product_infos[0].usage_value === 15, "usage_value must be 15");
    assert(data.product_infos[0].usage_measure_id === 0, "usage_measure_id must be 0");
  });

  await testT("T5: EstimateTemplateOnDemandPrice natgateway_small 30d ≈ USD 73.14", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateTemplateOnDemandPrice",
      arguments: {
        service: "natgateway",
        template_id: "nat-gateway-public-payg",
        region: REGION,
        parameters: {
          nat_resource_spec: "natgateway_small",
          usage_days: 30
        }
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.pricing_summary, "must have pricing_summary");
    const monthly = data.pricing_summary.monthly_amount;
    assert(monthly > 70 && monthly < 76, `monthly must be ≈73.14, got ${monthly}`);
  });

  await testT("T6: EstimateTemplateOnDemandPrice natgateway_xlarge 30d ≈ USD 475.47", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateTemplateOnDemandPrice",
      arguments: {
        service: "natgateway",
        template_id: "nat-gateway-public-payg",
        region: REGION,
        parameters: {
          nat_resource_spec: "natgateway_xlarge",
          usage_days: 30
        }
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.pricing_summary, "must have pricing_summary");
    const monthly = data.pricing_summary.monthly_amount;
    assert(monthly > 470 && monthly < 480, `monthly must be ≈475.47, got ${monthly}`);
  });

  await testT("T7: NAT Gateway + EIP bandwidth architecture pricing", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [
          {
            service: "natgateway",
            template_id: "nat-gateway-public-payg",
            parameters: {
              nat_resource_spec: "natgateway_small",
              usage_days: 30
            }
          },
          {
            service: "eip",
            template_id: "eip-bandwidth-mbps-payg",
            parameters: {
              bandwidth_mbps: 20,
              monthly_hours: 730
            }
          }
        ],
        validate_availability: false
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "status must be OK");

    const natPriced = data.priced_components.find((c) => c.template_id === "nat-gateway-public-payg");
    assert(natPriced, "NAT Gateway must be priced");
    assert(natPriced.monthly_amount > 0, "NAT Gateway must have positive monthly_amount");

    const eipPriced = data.priced_components.find((c) => c.template_id === "eip-bandwidth-mbps-payg");
    assert(eipPriced, "EIP must still be priced alongside NAT");

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

    assert(!data.availability_validation, "NAT Gateway must not trigger ECS availability validation");
  });

  await testT("T8: No private/elastic/exclusive/SNAT/DNAT NAT templates in Fase 1", async () => {
    const res = await client.callTool({
      name: "ListPricingTemplates",
      arguments: { service: "natgateway" }
    });
    const data = JSON.parse(res.content[0].text);

    const privateNat = data.templates.find((t) => t.template_id === "private-nat-gateway-payg");
    assert(!privateNat, "private-nat-gateway-payg must NOT exist in Fase 1");

    const elasticNat = data.templates.find((t) => t.template_id === "elastic-nat-gateway-payg");
    assert(!elasticNat, "elastic-nat-gateway-payg must NOT exist in Fase 1");

    const snatRule = data.templates.find((t) => t.template_id === "nat-snat-rule-payg");
    assert(!snatRule, "nat-snat-rule-payg must NOT exist in Fase 1");

    const dnatRule = data.templates.find((t) => t.template_id === "nat-dnat-rule-payg");
    assert(!dnatRule, "nat-dnat-rule-payg must NOT exist in Fase 1");

    const natPub = data.templates.find((t) => t.template_id === "nat-gateway-public-payg");
    assert(natPub, "nat-gateway-public-payg must exist");

    const desc = (natPub.description || "") + " " + (natPub.notes || []).join(" ");
    assert(
      desc.toLowerCase().includes("not included") || desc.toLowerCase().includes("pending") || desc.toLowerCase().includes("deferred"),
      "docs must indicate private/elastic/exclusive/SNAT/DNAT are pending/deferred/not included"
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
