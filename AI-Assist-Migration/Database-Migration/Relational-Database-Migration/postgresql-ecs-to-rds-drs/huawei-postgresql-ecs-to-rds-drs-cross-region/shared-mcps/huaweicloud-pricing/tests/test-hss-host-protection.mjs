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

  console.log("HSS Host Protection Fase 1 tests\n");

  await testT("T1: ListPricingTemplates includes hss-host-protection-payg", async () => {
    const res = await client.callTool({
      name: "ListPricingTemplates",
      arguments: { service: "hss" }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.templates.length > 0, "must have HSS templates");

    const hssInst = data.templates.find((t) => t.template_id === "hss-host-protection-payg");
    assert(hssInst, "hss-host-protection-payg must be listed");
    assert(hssInst.service === "hss", "service must be hss");
    assert(hssInst.status === "ready", "status must be ready");
    assert(hssInst.ready_for_real_pricing === true, "must be ready for real pricing");
    assert(hssInst.has_product_infos_template === true, "must have product_infos_template");

    const params = hssInst.parameters || {};
    assert(params.hss_resource_spec, "must have hss_resource_spec parameter");
    assert(params.hss_resource_spec.default === "hss.version.premium", "default hss_resource_spec must be hss.version.premium");
  });

  await testT("T2: RenderProductInfosFromTemplate with default params", async () => {
    const res = await client.callTool({
      name: "RenderProductInfosFromTemplate",
      arguments: {
        service: "hss",
        template_id: "hss-host-protection-payg",
        region: REGION,
        parameters: {}
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "render status must be OK");
    assert(data.product_infos.length === 1, "must have 1 product_info");

    const pi = data.product_infos[0];
    assert(pi.cloud_service_type === "hws.service.type.hss", "cloud_service_type must match");
    assert(pi.resource_type === "hws.resource.type.hss", "resource_type must match");
    assert(pi.resource_spec === "hss.version.premium", "resource_spec must be default hss.version.premium");
    assert(pi.usage_factor === "duration", "usage_factor must be duration");
    assert(pi.usage_value === 730, "usage_value must be 730");
    assert(pi.usage_measure_id === 4, "usage_measure_id must be 4");
    assert(pi.subscription_num === 1, "subscription_num must be 1");
  });

  await testT("T3: RenderProductInfosFromTemplate with quantity=3", async () => {
    const res = await client.callTool({
      name: "RenderProductInfosFromTemplate",
      arguments: {
        service: "hss",
        template_id: "hss-host-protection-payg",
        region: REGION,
        parameters: {
          quantity: 3
        }
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "render status must be OK");
    assert(data.product_infos[0].subscription_num === 3, "subscription_num must be 3");
  });

  await testT("T4: EstimateTemplateOnDemandPrice premium 730h ~ USD 20.44", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateTemplateOnDemandPrice",
      arguments: {
        service: "hss",
        template_id: "hss-host-protection-payg",
        region: REGION,
        parameters: {
          hss_resource_spec: "hss.version.premium",
          monthly_hours: 730
        }
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.pricing_summary, "must have pricing_summary");
    const monthly = data.pricing_summary.monthly_amount;
    assert(monthly > 19 && monthly < 22, `monthly must be ~20.44, got ${monthly}`);
  });

  await testT("T5: EstimateTemplateOnDemandPrice premium 3 PCS ~ USD 61.32", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateTemplateOnDemandPrice",
      arguments: {
        service: "hss",
        template_id: "hss-host-protection-payg",
        region: REGION,
        parameters: {
          hss_resource_spec: "hss.version.premium",
          monthly_hours: 730,
          quantity: 3
        }
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.pricing_summary, "must have pricing_summary");
    const monthly = data.pricing_summary.monthly_amount;
    assert(monthly > 59 && monthly < 64, `monthly must be ~61.32, got ${monthly}`);
  });

  await testT("T6: HSS in architecture contributes to monthly_total", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [
          {
            service: "hss",
            template_id: "hss-host-protection-payg",
            parameters: {
              hss_resource_spec: "hss.version.premium",
              monthly_hours: 730
            }
          },
          {
            service: "cbr",
            template_id: "cbr-server-backup-vault-gb-payg",
            parameters: {
              capacity_gb: 2400,
              monthly_hours: 730
            }
          }
        ],
        validate_availability: false
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "status must be OK");

    const hssPriced = data.priced_components.find((c) => c.template_id === "hss-host-protection-payg");
    assert(hssPriced, "HSS must be priced");
    assert(hssPriced.monthly_amount > 0, "HSS must have positive monthly_amount");

    const cbrPriced = data.priced_components.find((c) => c.template_id === "cbr-server-backup-vault-gb-payg");
    assert(cbrPriced, "CBR must still be priced alongside HSS");

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

    assert(!data.availability_validation, "HSS must not trigger ECS availability validation");
  });

  await testT("T7: No HSS expansion templates in Fase 1", async () => {
    const res = await client.callTool({
      name: "ListPricingTemplates",
      arguments: { service: "hss" }
    });
    const data = JSON.parse(res.content[0].text);

    const hssContainer = data.templates.find((t) => t.template_id === "hss-container-security-payg");
    assert(!hssContainer, "hss-container-security-payg must NOT exist in Fase 1");

    const hssWtp = data.templates.find((t) => t.template_id === "hss-web-tamper-payg");
    assert(!hssWtp, "hss-web-tamper-payg must NOT exist in Fase 1");

    const hssRansomware = data.templates.find((t) => t.template_id === "hss-ransomware-payg");
    assert(!hssRansomware, "hss-ransomware-payg must NOT exist in Fase 1");

    const hssInst = data.templates.find((t) => t.template_id === "hss-host-protection-payg");
    assert(hssInst, "hss-host-protection-payg must exist");

    const desc = (hssInst.description || "") + " " + (hssInst.notes || []).join(" ");
    assert(
      desc.toLowerCase().includes("not included") || desc.toLowerCase().includes("pending") || desc.toLowerCase().includes("fase 1"),
      "docs must indicate expansion modules are pending/not included/fase 1"
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
