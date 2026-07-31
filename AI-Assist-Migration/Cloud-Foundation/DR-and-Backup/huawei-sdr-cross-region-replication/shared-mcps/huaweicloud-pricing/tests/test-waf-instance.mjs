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

  console.log("WAF Instance Fase 1 tests\n");

  // T1: ListPricingTemplates includes waf-instance-payg
  await testT("T1: ListPricingTemplates includes waf-instance-payg", async () => {
    const res = await client.callTool({
      name: "ListPricingTemplates",
      arguments: { service: "waf" }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.templates.length > 0, "must have WAF templates");

    const wafInst = data.templates.find((t) => t.template_id === "waf-instance-payg");
    assert(wafInst, "waf-instance-payg must be listed");
    assert(wafInst.service === "waf", "service must be waf");
    assert(wafInst.status === "ready", "status must be ready");
    assert(wafInst.ready_for_real_pricing === true, "must be ready for real pricing");
    assert(wafInst.has_product_infos_template === true, "must have product_infos_template");
  });

  // T2: RenderProductInfosFromTemplate with default params
  await testT("T2: RenderProductInfosFromTemplate with default params", async () => {
    const res = await client.callTool({
      name: "RenderProductInfosFromTemplate",
      arguments: {
        service: "waf",
        template_id: "waf-instance-payg",
        region: REGION,
        parameters: {}
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "render status must be OK");
    assert(data.product_infos.length === 1, "must have 1 product_info");

    const pi = data.product_infos[0];
    assert(pi.cloud_service_type === "hws.service.type.waf", "cloud_service_type must match");
    assert(pi.resource_type === "hws.resource.type.waf.instance", "resource_type must match");
    assert(pi.resource_spec === "waf.instance.professional", "resource_spec must be default");
    assert(pi.usage_factor === "Duration", "usage_factor must be Duration");
    assert(pi.usage_value === 730, "usage_value must be 730");
    assert(pi.usage_measure_id === 4, "usage_measure_id must be 4");
    assert(pi.subscription_num === 1, "subscription_num must be 1");
  });

  // T3: RenderProductInfosFromTemplate with waf.instance.enterprise
  await testT("T3: RenderProductInfosFromTemplate with waf.instance.enterprise", async () => {
    const res = await client.callTool({
      name: "RenderProductInfosFromTemplate",
      arguments: {
        service: "waf",
        template_id: "waf-instance-payg",
        region: REGION,
        parameters: {
          instance_resource_spec: "waf.instance.enterprise"
        }
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "render status must be OK");
    assert(data.product_infos[0].resource_spec === "waf.instance.enterprise", "resource_spec must match override");
  });

  // T4: EstimateTemplateOnDemandPrice waf.instance.professional 730h
  await testT("T4: EstimateTemplateOnDemandPrice professional 730h ≈ USD 576.70", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateTemplateOnDemandPrice",
      arguments: {
        service: "waf",
        template_id: "waf-instance-payg",
        region: REGION,
        parameters: {
          instance_resource_spec: "waf.instance.professional",
          monthly_hours: 730
        }
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.pricing_summary, "must have pricing_summary");
    const monthly = data.pricing_summary.monthly_amount;
    assert(monthly > 570 && monthly < 585, `monthly must be ≈576.70, got ${monthly}`);
  });

  // T5: EstimateTemplateOnDemandPrice waf.instance.enterprise 730h
  await testT("T5: EstimateTemplateOnDemandPrice enterprise 730h ≈ USD 1,365.10", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateTemplateOnDemandPrice",
      arguments: {
        service: "waf",
        template_id: "waf-instance-payg",
        region: REGION,
        parameters: {
          instance_resource_spec: "waf.instance.enterprise",
          monthly_hours: 730
        }
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.pricing_summary, "must have pricing_summary");
    const monthly = data.pricing_summary.monthly_amount;
    assert(monthly > 1355 && monthly < 1375, `monthly must be ≈1,365.10, got ${monthly}`);
  });

  // T6: Architecture pricing with WAF + ELB/EIP
  await testT("T6: WAF instance in architecture contributes to monthly_total", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [
          {
            service: "waf",
            template_id: "waf-instance-payg",
            parameters: {
              instance_resource_spec: "waf.instance.professional",
              monthly_hours: 730
            }
          },
          {
            service: "elb",
            template_id: "elb-shared-instance-payg",
            parameters: {
              resource_spec: "elbv3.professional",
              monthly_hours: 730
            }
          },
          {
            service: "eip",
            template_id: "eip-bandwidth-mbps-payg",
            parameters: {
              bandwidth_mbps: 10,
              monthly_hours: 730
            }
          }
        ],
        validate_availability: false
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "status must be OK");

    const wafPriced = data.priced_components.find((c) => c.template_id === "waf-instance-payg");
    assert(wafPriced, "WAF instance must be priced");
    assert(wafPriced.monthly_amount > 0, "WAF instance must have positive monthly_amount");

    const elbPriced = data.priced_components.find((c) => c.template_id === "elb-shared-instance-payg");
    assert(elbPriced, "ELB must still be priced alongside WAF");

    const eipPriced = data.priced_components.find((c) => c.template_id === "eip-bandwidth-mbps-payg");
    assert(eipPriced, "EIP must still be priced alongside WAF");

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

    assert(!data.availability_validation, "WAF must not trigger ECS availability validation");

    if (data.service_cost_breakdown) {
      const elbBreakdown = data.service_cost_breakdown.find((b) => b.service === "elb");
      if (elbBreakdown) {
        assert(elbBreakdown.components.length > 0, "ELB service_cost_breakdown must still function");
      }
    }
  });

  // T7: No WAF domain/rule/request/expansion templates in Fase 1
  await testT("T7: No WAF domain/rule/request/expansion templates in Fase 1", async () => {
    const res = await client.callTool({
      name: "ListPricingTemplates",
      arguments: { service: "waf" }
    });
    const data = JSON.parse(res.content[0].text);

    const wafDomain = data.templates.find((t) => t.template_id === "waf-domain-payg");
    assert(!wafDomain, "waf-domain-payg must NOT exist in Fase 1");

    const wafRule = data.templates.find((t) => t.template_id === "waf-rule-payg");
    assert(!wafRule, "waf-rule-payg must NOT exist in Fase 1");

    const wafRequest = data.templates.find((t) => t.template_id === "waf-request-payg");
    assert(!wafRequest, "waf-request-payg must NOT exist in Fase 1");

    const wafBandwidth = data.templates.find((t) => t.template_id === "waf-bandwidth-payg");
    assert(!wafBandwidth, "waf-bandwidth-payg must NOT exist in Fase 1");

    const wafInst = data.templates.find((t) => t.template_id === "waf-instance-payg");
    assert(wafInst, "waf-instance-payg must exist");

    const desc = wafInst.description || "";
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
