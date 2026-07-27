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

  console.log("ECS/SUSE Period Billing Phase 1 tests (T1-T12)\n");

  await testT("T1: ListPricingTemplates includes ecs-flavor-period", async () => {
    const res = await client.callTool({
      name: "ListPricingTemplates",
      arguments: { service: "ecs" }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.templates.length > 0, "must have ECS templates");

    const periodTemplate = data.templates.find((t) => t.template_id === "ecs-flavor-period");
    assert(periodTemplate, "ecs-flavor-period must be listed");
    assert(periodTemplate.service === "ecs", "service must be ecs");
    assert(periodTemplate.billing_mode === "period", "billing_mode must be period");
    assert(periodTemplate.status === "ready", "status must be ready");
    assert(periodTemplate.ready_for_real_pricing === true, "must be ready for real pricing");

    const pi = periodTemplate.parameters || {};
    assert(pi.ecs_resource_spec, "must have ecs_resource_spec parameter");
    assert(pi.period_type, "must have period_type parameter");
    assert(pi.period_type.default === 2, "default period_type must be 2");
    assert(pi.period_num, "must have period_num parameter");
    assert(pi.period_num.default === 1, "default period_num must be 1");

    const pit = periodTemplate.has_product_infos_template;
    assert(pit === true, "must have product_infos_template");

    const renderedPi = periodTemplate.parameters || {};
    const productInfos = periodTemplate.parameter_names || [];
    assert(productInfos.includes("ecs_resource_spec"), "must include ecs_resource_spec in parameter_names");
  });

  await testT("T2: ListPricingTemplates includes ecs-os-license-period", async () => {
    const res = await client.callTool({
      name: "ListPricingTemplates",
      arguments: { service: "ecs" }
    });
    const data = JSON.parse(res.content[0].text);

    const periodTemplate = data.templates.find((t) => t.template_id === "ecs-os-license-period");
    assert(periodTemplate, "ecs-os-license-period must be listed");
    assert(periodTemplate.service === "ecs", "service must be ecs");
    assert(periodTemplate.billing_mode === "period", "billing_mode must be period");
    assert(periodTemplate.status === "ready", "status must be ready");
    assert(periodTemplate.ready_for_real_pricing === true, "must be ready for real pricing");

    const pi = periodTemplate.parameters || {};
    assert(pi.os_resource_spec, "must have os_resource_spec parameter");
    assert(pi.os_resource_spec.default === "suse.12", "default os_resource_spec must be suse.12");
    assert(pi.period_type, "must have period_type parameter");
    assert(pi.period_type.default === 2, "default period_type must be 2");
    assert(pi.period_num, "must have period_num parameter");
    assert(pi.period_num.default === 1, "default period_num must be 1");
  });

  await testT("T3: RenderProductInfosFromTemplate ecs-flavor-period with defaults", async () => {
    const res = await client.callTool({
      name: "RenderProductInfosFromTemplate",
      arguments: {
        service: "ecs",
        template_id: "ecs-flavor-period",
        region: REGION
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "render status must be OK");
    assert(data.product_infos.length === 1, "must have 1 product_info");

    const pi = data.product_infos[0];
    assert(pi.cloud_service_type === "hws.service.type.ec2", "cloud_service_type must match");
    assert(pi.resource_type === "hws.resource.type.vm", "resource_type must be hws.resource.type.vm");
    assert(pi.resource_spec === "s6.xlarge.4.linux", "resource_spec must be default s6.xlarge.4.linux");
    assert(pi.period_type === 2, "period_type must be 2");
    assert(pi.period_num === 1, "period_num must be 1");
    assert(pi.usage_value === 730, "usage_value must be 730");
    assert(pi.usage_measure_id === 4, "usage_measure_id must be 4");
  });

  await testT("T4: RenderProductInfosFromTemplate ecs-os-license-period with defaults", async () => {
    const res = await client.callTool({
      name: "RenderProductInfosFromTemplate",
      arguments: {
        service: "ecs",
        template_id: "ecs-os-license-period",
        region: REGION
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "render status must be OK");
    assert(data.product_infos.length === 1, "must have 1 product_info");

    const pi = data.product_infos[0];
    assert(pi.cloud_service_type === "hws.service.type.ec2", "cloud_service_type must match");
    assert(pi.resource_type === "hws.resource.type.vm.image", "resource_type must be hws.resource.type.vm.image");
    assert(pi.resource_spec === "suse.12", "resource_spec must be default suse.12");
    assert(pi.period_type === 2, "period_type must be 2");
    assert(pi.period_num === 1, "period_num must be 1");
  });

  await testT("T5: EstimateTemplatePeriodPrice m6.3xlarge.8.linux period 1 month = USD 356.36", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE period pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateTemplatePeriodPrice",
      arguments: {
        service: "ecs",
        template_id: "ecs-flavor-period",
        region: REGION,
        parameters: {
          ecs_resource_spec: "m6.3xlarge.8.linux",
          period_type: 2,
          period_num: 1,
          monthly_hours: 730
        }
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.pricing_summary, "must have pricing_summary");
    const monthly = data.pricing_summary.monthly_amount;
    assert(Math.abs(monthly - 356.36) < 1.0, `monthly must be ~356.36, got ${monthly}`);
    assert(data.pricing_summary.pricing_basis.billing_mode === "period", "pricing_basis billing_mode must be period");
  });

  await testT("T6: EstimateTemplatePeriodPrice c6.3xlarge.4.linux period 1 month = USD 271.21", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE period pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateTemplatePeriodPrice",
      arguments: {
        service: "ecs",
        template_id: "ecs-flavor-period",
        region: REGION,
        parameters: {
          ecs_resource_spec: "c6.3xlarge.4.linux",
          period_type: 2,
          period_num: 1,
          monthly_hours: 730
        }
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.pricing_summary, "must have pricing_summary");
    const monthly = data.pricing_summary.monthly_amount;
    assert(Math.abs(monthly - 271.21) < 1.0, `monthly must be ~271.21, got ${monthly}`);
  });

  await testT("T7: EstimateTemplatePeriodPrice s6.xlarge.4.linux period 1 month = USD 63.07", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE period pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateTemplatePeriodPrice",
      arguments: {
        service: "ecs",
        template_id: "ecs-flavor-period",
        region: REGION,
        parameters: {
          ecs_resource_spec: "s6.xlarge.4.linux",
          period_type: 2,
          period_num: 1,
          monthly_hours: 730
        }
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.pricing_summary, "must have pricing_summary");
    const monthly = data.pricing_summary.monthly_amount;
    assert(Math.abs(monthly - 63.07) < 1.0, `monthly must be ~63.07, got ${monthly}`);
  });

  await testT("T8: EstimateTemplatePeriodPrice suse.12 period 1 month = USD 55.00", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE period pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateTemplatePeriodPrice",
      arguments: {
        service: "ecs",
        template_id: "ecs-os-license-period",
        region: REGION,
        parameters: {
          os_resource_spec: "suse.12",
          period_type: 2,
          period_num: 1,
          monthly_hours: 730
        }
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.pricing_summary, "must have pricing_summary");
    const monthly = data.pricing_summary.monthly_amount;
    assert(Math.abs(monthly - 55.00) < 1.0, `monthly must be ~55.00, got ${monthly}`);
  });

  await testT("T9: Routing guard - period template rejected by OnDemand, payg rejected by Period", async () => {
    const res1 = await client.callTool({
      name: "EstimateTemplateOnDemandPrice",
      arguments: {
        service: "ecs",
        template_id: "ecs-flavor-period",
        region: REGION,
        parameters: {}
      }
    });
    const data1 = JSON.parse(res1.content[0].text);
    assert(data1.status === "ROUTING_ERROR", "ecs-flavor-period must be rejected by EstimateTemplateOnDemandPrice");
    assert(data1.reason && data1.reason.includes("period"), "reason must mention period");

    const res2 = await client.callTool({
      name: "EstimateTemplatePeriodPrice",
      arguments: {
        service: "ecs",
        template_id: "ecs-flavor-payg",
        region: REGION,
        parameters: {}
      }
    });
    const data2 = JSON.parse(res2.content[0].text);
    assert(data2.status === "ROUTING_ERROR", "ecs-flavor-payg must be rejected by EstimateTemplatePeriodPrice");
    assert(data2.reason && data2.reason.includes("on_demand"), "reason must mention on_demand");
  });

  await testT("T10: EstimateArchitecturePeriodPrice with three ECS benchmark lines (mixed period + on-demand)", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateArchitecturePeriodPrice",
      arguments: {
        region: REGION,
        components: [
          {
            service: "ecs",
            template_id: "ecs-flavor-period",
            parameters: {
              ecs_resource_spec: "m6.3xlarge.8.linux",
              period_type: 2,
              period_num: 1,
              monthly_hours: 730
            }
          },
          {
            service: "ecs",
            template_id: "ecs-os-license-period",
            parameters: {
              os_resource_spec: "suse.12",
              period_type: 2,
              period_num: 1,
              monthly_hours: 730
            }
          },
          {
            service: "evs",
            template_id: "evs-gpssd-gb-payg",
            parameters: {
              size_gb: 700,
              monthly_hours: 730
            }
          },
          {
            service: "ecs",
            template_id: "ecs-flavor-period",
            parameters: {
              ecs_resource_spec: "c6.3xlarge.4.linux",
              period_type: 2,
              period_num: 1,
              monthly_hours: 730
            }
          },
          {
            service: "evs",
            template_id: "evs-gpssd-gb-payg",
            parameters: {
              size_gb: 300,
              monthly_hours: 730
            }
          },
          {
            service: "ecs",
            template_id: "ecs-flavor-period",
            parameters: {
              ecs_resource_spec: "s6.xlarge.4.linux",
              period_type: 2,
              period_num: 1,
              monthly_hours: 730
            }
          },
          {
            service: "evs",
            template_id: "evs-gpssd-gb-payg",
            parameters: {
              size_gb: 200,
              monthly_hours: 730
            }
          }
        ]
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "status must be OK");

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

    const computePeriodTotal = 356.36 + 271.21 + 63.07 + 55.00;
    assert(
      Math.abs(data.pricing_summary.monthly_total_period - computePeriodTotal) < 2.0,
      `monthly_total_period must be ~${computePeriodTotal}, got ${data.pricing_summary.monthly_total_period}`
    );

    const expectedTotal = 859.09;
    assert(
      Math.abs(data.pricing_summary.monthly_total - expectedTotal) < 5.0,
      `monthly_total must be ~${expectedTotal}, got ${data.pricing_summary.monthly_total}`
    );
  });

  await testT("T11: payg still works - ecs-flavor-payg and ecs-os-license-payg return on-demand prices", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;

    const res1 = await client.callTool({
      name: "EstimateTemplateOnDemandPrice",
      arguments: {
        service: "ecs",
        template_id: "ecs-flavor-payg",
        region: REGION,
        parameters: {
          ecs_resource_spec: "s6.xlarge.4.linux",
          monthly_hours: 730
        }
      }
    });
    const data1 = JSON.parse(res1.content[0].text);
    assert(data1.pricing_summary, "must have pricing_summary");
    const monthly1 = data1.pricing_summary.monthly_amount;
    assert(Math.abs(monthly1 - 87.60) < 1.0, `ecs-flavor-payg s6.xlarge.4.linux must be ~87.60, got ${monthly1}`);

    const res2 = await client.callTool({
      name: "EstimateTemplateOnDemandPrice",
      arguments: {
        service: "ecs",
        template_id: "ecs-os-license-payg",
        region: REGION,
        parameters: {
          os_resource_spec: "suse.12",
          monthly_hours: 730
        }
      }
    });
    const data2 = JSON.parse(res2.content[0].text);
    assert(data2.pricing_summary, "must have pricing_summary");
    const monthly2 = data2.pricing_summary.monthly_amount;
    assert(Math.abs(monthly2 - 109.50) < 1.0, `ecs-os-license-payg suse.12 must be ~109.50, got ${monthly2}`);
  });

  await testT("T12: No macro ECS template exists", async () => {
    const res = await client.callTool({
      name: "ListPricingTemplates",
      arguments: { service: "ecs" }
    });
    const data = JSON.parse(res.content[0].text);

    const macroTemplate = data.templates.find((t) => t.template_id === "ecs-instance-with-system-disk");
    assert(!macroTemplate, "ecs-instance-with-system-disk must NOT exist (macro deferred)");
  });

  await client.close();

  console.log(`\nResults: ${passed} passed, ${failed} failed, ${skipped} skipped`);
  process.exit(failed > 0 ? 1 : 0);
}

runTest().catch((e) => {
  console.error("Test runner error:", e);
  process.exit(2);
});
