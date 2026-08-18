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

  console.log("CFW Instance Fase 1 tests\n");

  // T1: ListPricingTemplates includes cfw-instance-payg
  await testT("T1: ListPricingTemplates includes cfw-instance-payg", async () => {
    const res = await client.callTool({
      name: "ListPricingTemplates",
      arguments: { service: "cfw" }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.templates.length > 0, "must have CFW templates");

    const cfwInst = data.templates.find((t) => t.template_id === "cfw-instance-payg");
    assert(cfwInst, "cfw-instance-payg must be listed");
    assert(cfwInst.service === "cfw", "service must be cfw");
    assert(cfwInst.status === "ready", "status must be ready");
    assert(cfwInst.ready_for_real_pricing === true, "must be ready for real pricing");
    assert(cfwInst.has_product_infos_template === true, "must have product_infos_template");

    const params = cfwInst.parameters || {};
    assert(params.instance_resource_spec, "must have instance_resource_spec parameter");
    assert(params.instance_resource_spec.default === "cfw.professional", "default instance_resource_spec must be cfw.professional");
  });

  // T2: RenderProductInfosFromTemplate with default params
  await testT("T2: RenderProductInfosFromTemplate with default params", async () => {
    const res = await client.callTool({
      name: "RenderProductInfosFromTemplate",
      arguments: {
        service: "cfw",
        template_id: "cfw-instance-payg",
        region: REGION,
        parameters: {}
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "render status must be OK");
    assert(data.product_infos.length === 1, "must have 1 product_info");

    const pi = data.product_infos[0];
    assert(pi.cloud_service_type === "hws.service.type.cfw", "cloud_service_type must match");
    assert(pi.resource_type === "hws.resource.type.cfw", "resource_type must match");
    assert(pi.resource_spec === "cfw.professional", "resource_spec must be default cfw.professional");
    assert(pi.usage_factor === "usage_duration", "usage_factor must be usage_duration");
    assert(pi.usage_value === 730, "usage_value must be 730");
    assert(pi.usage_measure_id === 4, "usage_measure_id must be 4");
    assert(pi.subscription_num === 1, "subscription_num must be 1");
  });

  // T3: RenderProductInfosFromTemplate with quantity=2
  await testT("T3: RenderProductInfosFromTemplate with quantity=2", async () => {
    const res = await client.callTool({
      name: "RenderProductInfosFromTemplate",
      arguments: {
        service: "cfw",
        template_id: "cfw-instance-payg",
        region: REGION,
        parameters: {
          quantity: 2
        }
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "render status must be OK");
    assert(data.product_infos[0].subscription_num === 2, "subscription_num must be 2 (no local multiplication logic)");
  });

  // T4: EstimateTemplateOnDemandPrice cfw.professional 730h
  await testT("T4: EstimateTemplateOnDemandPrice professional 730h ≈ USD 262.80", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateTemplateOnDemandPrice",
      arguments: {
        service: "cfw",
        template_id: "cfw-instance-payg",
        region: REGION,
        parameters: {
          instance_resource_spec: "cfw.professional",
          monthly_hours: 730
        }
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.pricing_summary, "must have pricing_summary");
    const monthly = data.pricing_summary.monthly_amount;
    assert(monthly > 255 && monthly < 270, `monthly must be ≈262.80, got ${monthly}`);
  });

  // T5: Verify cfw.standard is NOT documented as on-demand ready
  await testT("T5: cfw.standard NOT documented as on-demand ready", async () => {
    const res = await client.callTool({
      name: "ListPricingTemplates",
      arguments: { service: "cfw" }
    });
    const data = JSON.parse(res.content[0].text);

    const cfwInst = data.templates.find((t) => t.template_id === "cfw-instance-payg");
    assert(cfwInst, "cfw-instance-payg must exist");

    const params = cfwInst.parameters || {};
    assert(params.instance_resource_spec.default === "cfw.professional", "default must be cfw.professional, NOT cfw.standard");

    const desc = (cfwInst.description || "") + " " + (cfwInst.notes || []).join(" ");
    assert(
      desc.toLowerCase().includes("period-only") || desc.toLowerCase().includes("period only") || desc.toLowerCase().includes("not available for pay-per-use"),
      "docs must indicate cfw.standard is period-only / not available for pay-per-use"
    );
  });

  // T6: Architecture pricing with CFW + ELB/EIP
  await testT("T6: CFW instance in architecture contributes to monthly_total", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [
          {
            service: "cfw",
            template_id: "cfw-instance-payg",
            parameters: {
              instance_resource_spec: "cfw.professional",
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

    const cfwPriced = data.priced_components.find((c) => c.template_id === "cfw-instance-payg");
    assert(cfwPriced, "CFW instance must be priced");
    assert(cfwPriced.monthly_amount > 0, "CFW instance must have positive monthly_amount");

    const elbPriced = data.priced_components.find((c) => c.template_id === "elb-shared-instance-payg");
    assert(elbPriced, "ELB must still be priced alongside CFW");

    const eipPriced = data.priced_components.find((c) => c.template_id === "eip-bandwidth-mbps-payg");
    assert(eipPriced, "EIP must still be priced alongside CFW");

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

    assert(!data.availability_validation, "CFW must not trigger ECS availability validation");

    if (data.service_cost_breakdown) {
      const elbBreakdown = data.service_cost_breakdown.find((b) => b.service === "elb");
      if (elbBreakdown) {
        assert(elbBreakdown.components.length > 0, "ELB service_cost_breakdown must still function");
      }
    }
  });

  // T7: No CFW expansion templates in Fase 1
  await testT("T7: No CFW expansion templates in Fase 1", async () => {
    const res = await client.callTool({
      name: "ListPricingTemplates",
      arguments: { service: "cfw" }
    });
    const data = JSON.parse(res.content[0].text);

    const cfwExpEip = data.templates.find((t) => t.template_id === "cfw-exp-eip-payg");
    assert(!cfwExpEip, "cfw-exp-eip-payg must NOT exist in Fase 1");

    const cfwExpVpc = data.templates.find((t) => t.template_id === "cfw-exp-vpc-payg");
    assert(!cfwExpVpc, "cfw-exp-vpc-payg must NOT exist in Fase 1");

    const cfwExpBandwidth = data.templates.find((t) => t.template_id === "cfw-exp-bandwidth-payg");
    assert(!cfwExpBandwidth, "cfw-exp-bandwidth-payg must NOT exist in Fase 1");

    const cfwInst = data.templates.find((t) => t.template_id === "cfw-instance-payg");
    assert(cfwInst, "cfw-instance-payg must exist");

    const desc = (cfwInst.description || "") + " " + (cfwInst.notes || []).join(" ");
    assert(
      desc.toLowerCase().includes("not included") || desc.toLowerCase().includes("deferred") || desc.toLowerCase().includes("pending"),
      "docs must indicate expansion packages are pending/deferred/not included"
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
