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

  console.log("ECS Linux system disk PAYG tests\n");

  await testT("T1: ListPricingTemplates includes ecs-linux-2vcpu-4gb-payg", async () => {
    const res = await client.callTool({
      name: "ListPricingTemplates",
      arguments: { service: "ecs", region: REGION }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.templates.length > 0, "must have ECS templates");
    const tpl = data.templates.find((t) => t.template_id === "ecs-linux-2vcpu-4gb-payg");
    assert(tpl, "ecs-linux-2vcpu-4gb-payg must be listed");
    assert(tpl.service === "ecs", "service must be ecs");
    assert(tpl.status === "ready", "status must be ready");
    assert(tpl.ready_for_real_pricing === true, "must be ready for real pricing");
  });

  await testT("T2: RenderProductInfosFromTemplate returns 2 productInfos (vm + volume)", async () => {
    const res = await client.callTool({
      name: "RenderProductInfosFromTemplate",
      arguments: {
        service: "ecs",
        template_id: "ecs-linux-2vcpu-4gb-payg",
        region: REGION,
        parameters: { monthly_hours: 730, system_disk_gb: 40 }
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "render status must be OK");
    assert(data.product_infos.length === 2, `must have 2 product_infos, got ${data.product_infos.length}`);

    const vm = data.product_infos.find((pi) => pi.resource_type === "hws.resource.type.vm");
    const vol = data.product_infos.find((pi) => pi.resource_type === "hws.resource.type.volume");
    assert(vm, "must have vm product_info");
    assert(vol, "must have volume product_info");
  });

  await testT("T3: VM productInfo uses s6.large.2.linux and usage_value=730", async () => {
    const res = await client.callTool({
      name: "RenderProductInfosFromTemplate",
      arguments: {
        service: "ecs",
        template_id: "ecs-linux-2vcpu-4gb-payg",
        region: REGION,
        parameters: { monthly_hours: 730, system_disk_gb: 40 }
      }
    });
    const data = JSON.parse(res.content[0].text);
    const vm = data.product_infos.find((pi) => pi.resource_type === "hws.resource.type.vm");
    assert(vm.resource_spec === "s6.large.2.linux", `resource_spec must be s6.large.2.linux, got ${vm.resource_spec}`);
    assert(vm.usage_value === 730, `usage_value must be 730, got ${vm.usage_value}`);
    assert(vm.cloud_service_type === "hws.service.type.ec2", "cloud_service_type must match");
    assert(vm.usage_measure_id === 4, "usage_measure_id must be 4");
  });

  await testT("T4: Volume productInfo uses GPSSD, resource_size=40, usage_value=730", async () => {
    const res = await client.callTool({
      name: "RenderProductInfosFromTemplate",
      arguments: {
        service: "ecs",
        template_id: "ecs-linux-2vcpu-4gb-payg",
        region: REGION,
        parameters: { monthly_hours: 730, system_disk_gb: 40 }
      }
    });
    const data = JSON.parse(res.content[0].text);
    const vol = data.product_infos.find((pi) => pi.resource_type === "hws.resource.type.volume");
    assert(vol.resource_spec === "GPSSD", `resource_spec must be GPSSD, got ${vol.resource_spec}`);
    assert(vol.resource_size === 40, `resource_size must be 40, got ${vol.resource_size}`);
    assert(vol.usage_value === 730, `usage_value must be 730, got ${vol.usage_value}`);
    assert(vol.cloud_service_type === "hws.service.type.ebs", "cloud_service_type must be ebs");
    assert(vol.size_measure_id === 17, "size_measure_id must be 17");
  });

  await testT("T5: EstimateTemplateOnDemandPrice qty=1 730h system_disk_gb=40 ≈ USD 43.22", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateTemplateOnDemandPrice",
      arguments: {
        service: "ecs",
        template_id: "ecs-linux-2vcpu-4gb-payg",
        region: REGION,
        quantity: 1,
        parameters: { monthly_hours: 730, system_disk_gb: 40 },
        inquiry_precision: 1
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.pricing_summary, "must have pricing_summary");
    const monthly = data.pricing_summary.monthly_amount;
    assert(
      Math.abs(monthly - 43.22) < 0.05,
      `monthly must be ≈43.22 (±0.05), got ${monthly}`
    );
  });

  await testT("T6: Architecture 2x ECS ≈ USD 86.44 total for ECS", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        inquiry_precision: 1,
        components: [
          {
            service: "ecs",
            template_id: "ecs-linux-2vcpu-4gb-payg",
            quantity: 2,
            parameters: { monthly_hours: 730, system_disk_gb: 40 }
          }
        ]
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "status must be OK");
    const ecsComp = data.priced_components.find((c) => c.template_id === "ecs-linux-2vcpu-4gb-payg");
    assert(ecsComp, "must have ECS component");
    const monthly = ecsComp.monthly_amount;
    assert(
      Math.abs(monthly - 86.44) < 0.10,
      `ECS x2 monthly must be ≈86.44 (±0.10), got ${monthly}`
    );
  });

  await testT("T7: ecs-flavor-payg compute-only still returns only 1 productInfo", async () => {
    const res = await client.callTool({
      name: "RenderProductInfosFromTemplate",
      arguments: {
        service: "ecs",
        template_id: "ecs-flavor-payg",
        region: REGION,
        parameters: { monthly_hours: 730 }
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "render status must be OK");
    assert(data.product_infos.length === 1, `ecs-flavor-payg must have 1 product_info, got ${data.product_infos.length}`);
    assert(data.product_infos[0].resource_type === "hws.resource.type.vm", "must be vm only");
  });

  await client.close();

  console.log(`\nResults: ${passed} passed, ${failed} failed, ${skipped} skipped`);
  process.exit(failed > 0 ? 1 : 0);
}

runTest().catch((e) => {
  console.error("Test runner error:", e);
  process.exit(2);
});
