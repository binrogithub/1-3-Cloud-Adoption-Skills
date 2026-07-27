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
  const estimateOnDemandTool = tools.tools.find((t) => t.name === "EstimateTemplateOnDemandPrice");
  assert(estimateOnDemandTool, "EstimateTemplateOnDemandPrice tool must be registered");
  const estimatePeriodTool = tools.tools.find((t) => t.name === "EstimateTemplatePeriodPrice");
  assert(estimatePeriodTool, "EstimateTemplatePeriodPrice tool must be registered");
  const archPeriodTool = tools.tools.find((t) => t.name === "EstimateArchitecturePeriodPrice");
  assert(archPeriodTool, "EstimateArchitecturePeriodPrice tool must be registered");

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

  console.log("HSS Period Billing Phase 1 tests\n");

  await testT("T1: ListPricingTemplates includes hss-host-protection-period", async () => {
    const res = await client.callTool({
      name: "ListPricingTemplates",
      arguments: { service: "hss" }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.templates.length > 0, "must have HSS templates");

    const periodTemplate = data.templates.find((t) => t.template_id === "hss-host-protection-period");
    assert(periodTemplate, "hss-host-protection-period must be listed");
    assert(periodTemplate.service === "hss", "service must be hss");
    assert(periodTemplate.billing_mode === "period", "billing_mode must be period");
    assert(periodTemplate.status === "ready", "status must be ready");
    assert(periodTemplate.ready_for_real_pricing === true, "must be ready for real pricing");

    const params = periodTemplate.parameters || {};
    assert(params.hss_resource_spec, "must have hss_resource_spec parameter");
    assert(params.hss_resource_spec.default === "hss.version.premium", "default hss_resource_spec must be hss.version.premium");
    assert(params.period_type, "must have period_type parameter");
    assert(params.period_type.default === 2, "default period_type must be 2");
    assert(params.period_num, "must have period_num parameter");
    assert(params.period_num.default === 1, "default period_num must be 1");
  });

  await testT("T2: RenderProductInfosFromTemplate with default params for period", async () => {
    const res = await client.callTool({
      name: "RenderProductInfosFromTemplate",
      arguments: {
        service: "hss",
        template_id: "hss-host-protection-period",
        region: REGION,
        quantity: 3,
        parameters: {
          quantity: 3
        }
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
    assert(pi.subscription_num === 3, "subscription_num must be 3");
    assert(pi.period_type === 2, "period_type must be 2");
    assert(pi.period_num === 1, "period_num must be 1");
  });

  await testT("T3: EstimateTemplatePeriodPrice premium 3 PCS period 1 month = USD 41.40", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE period pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateTemplatePeriodPrice",
      arguments: {
        service: "hss",
        template_id: "hss-host-protection-period",
        region: REGION,
        parameters: {
          hss_resource_spec: "hss.version.premium",
          quantity: 3,
          period_type: 2,
          period_num: 1,
          monthly_hours: 730
        }
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.pricing_summary, "must have pricing_summary");
    const monthly = data.pricing_summary.monthly_amount;
    assert(monthly > 40 && monthly < 43, `monthly must be ~41.40, got ${monthly}`);
    assert(data.pricing_summary.pricing_basis.billing_mode === "period", "pricing_basis billing_mode must be period");
    assert(data.pricing_summary.pricing_basis.period_type === 2, "period_type must be 2");
    assert(data.pricing_summary.pricing_basis.period_num === 1, "period_num must be 1");
  });

  await testT("T4: EstimateTemplateOnDemandPrice premium 3 PCS 730h = USD 61.32 (on-demand still works)", async () => {
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

  await testT("T5: Period template must NOT be priced via EstimateTemplateOnDemandPrice (routing guard)", async () => {
    const res = await client.callTool({
      name: "EstimateTemplateOnDemandPrice",
      arguments: {
        service: "hss",
        template_id: "hss-host-protection-period",
        region: REGION,
        parameters: {}
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "ROUTING_ERROR", "must return ROUTING_ERROR");
    assert(data.reason && data.reason.includes("period"), "reason must mention period");
  });

  await testT("T6: On-demand template must NOT be priced via EstimateTemplatePeriodPrice (routing guard)", async () => {
    const res = await client.callTool({
      name: "EstimateTemplatePeriodPrice",
      arguments: {
        service: "hss",
        template_id: "hss-host-protection-payg",
        region: REGION,
        parameters: {}
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "ROUTING_ERROR", "must return ROUTING_ERROR");
    assert(data.reason && data.reason.includes("on_demand"), "reason must mention on_demand");
  });

  await testT("T7: hss-host-protection-payg still exists and works (retrocompatibility)", async () => {
    const res = await client.callTool({
      name: "ListPricingTemplates",
      arguments: { service: "hss" }
    });
    const data = JSON.parse(res.content[0].text);

    const paygTemplate = data.templates.find((t) => t.template_id === "hss-host-protection-payg");
    assert(paygTemplate, "hss-host-protection-payg must still exist");
    assert(paygTemplate.billing_mode === "on_demand", "billing_mode must be on_demand");
    assert(paygTemplate.status === "ready", "status must be ready");

    const periodTemplate = data.templates.find((t) => t.template_id === "hss-host-protection-period");
    assert(periodTemplate, "hss-host-protection-period must exist");
    assert(periodTemplate.billing_mode === "period", "billing_mode must be period");
  });

  await testT("T8: EstimateArchitecturePeriodPrice with HSS period + CBR on-demand", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateArchitecturePeriodPrice",
      arguments: {
        region: REGION,
        components: [
          {
            service: "hss",
            template_id: "hss-host-protection-period",
            parameters: {
              hss_resource_spec: "hss.version.premium",
              quantity: 3,
              period_type: 2,
              period_num: 1,
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
        ]
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "status must be OK");

    const hssPriced = data.priced_components.find((c) => c.template_id === "hss-host-protection-period");
    assert(hssPriced, "HSS period must be priced");
    assert(hssPriced.billing_mode === "period", "HSS billing_mode must be period");
    assert(hssPriced.monthly_amount > 0, "HSS must have positive monthly_amount");

    const cbrPriced = data.priced_components.find((c) => c.template_id === "cbr-server-backup-vault-gb-payg");
    assert(cbrPriced, "CBR must still be priced alongside HSS");
    assert(cbrPriced.billing_mode === "on_demand", "CBR billing_mode must be on_demand");

    assert(data.pricing_summary.monthly_total_period > 0, "monthly_total_period must be positive");
    assert(data.pricing_summary.monthly_total_on_demand > 0, "monthly_total_on_demand must be positive");

    const totalSum = data.pricing_summary.monthly_total_on_demand + data.pricing_summary.monthly_total_period;
    assert(
      Math.abs(data.pricing_summary.monthly_total - totalSum) < 0.01,
      "monthly_total must equal monthly_total_on_demand + monthly_total_period"
    );

    assert(data.pricing_summary.billing_modes.includes("on_demand"), "billing_modes must include on_demand");
    assert(data.pricing_summary.billing_modes.includes("period"), "billing_modes must include period");

    assert(data.warnings && data.warnings.length > 0, "must have warning for mixed billing modes");
    assert(data.warnings[0].includes("on-demand") || data.warnings[0].includes("period"), "warning must mention billing modes");
  });

  await testT("T9: EstimateArchitecturePeriodPrice period-only (no warning)", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateArchitecturePeriodPrice",
      arguments: {
        region: REGION,
        components: [
          {
            service: "hss",
            template_id: "hss-host-protection-period",
            parameters: {
              hss_resource_spec: "hss.version.premium",
              quantity: 3,
              period_type: 2,
              period_num: 1,
              monthly_hours: 730
            }
          }
        ]
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "status must be OK");
    assert(data.pricing_summary.monthly_total_on_demand === 0, "monthly_total_on_demand must be 0");
    assert(data.pricing_summary.monthly_total_period > 0, "monthly_total_period must be positive");
    assert(!data.warnings || data.warnings.length === 0, "no warning for period-only architecture");
  });

  await client.close();

  console.log(`\nResults: ${passed} passed, ${failed} failed, ${skipped} skipped`);
  process.exit(failed > 0 ? 1 : 0);
}

runTest().catch((e) => {
  console.error("Test runner error:", e);
  process.exit(2);
});
