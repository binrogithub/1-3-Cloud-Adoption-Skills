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

  console.log("CBR Backup Vaults Phase 1 tests\n");

  await testT("T1: ListPricingTemplates includes cbr-server-backup-vault-gb-payg", async () => {
    const res = await client.callTool({
      name: "ListPricingTemplates",
      arguments: { service: "cbr" }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.templates.length > 0, "must have CBR templates");

    const serverVault = data.templates.find((t) => t.template_id === "cbr-server-backup-vault-gb-payg");
    assert(serverVault, "cbr-server-backup-vault-gb-payg must be listed");
    assert(serverVault.service === "cbr", "service must be cbr");
    assert(serverVault.status === "ready", "status must be ready");
    assert(serverVault.ready_for_real_pricing === true, "must be ready for real pricing");

    const pi = serverVault;
    assert(pi.has_product_infos_template === true, "must have product_infos_template");
  });

  await testT("T2: ListPricingTemplates includes cbr-disk-backup-vault-gb-payg", async () => {
    const res = await client.callTool({
      name: "ListPricingTemplates",
      arguments: { service: "cbr" }
    });
    const data = JSON.parse(res.content[0].text);

    const diskVault = data.templates.find((t) => t.template_id === "cbr-disk-backup-vault-gb-payg");
    assert(diskVault, "cbr-disk-backup-vault-gb-payg must be listed");
    assert(diskVault.service === "cbr", "service must be cbr");
    assert(diskVault.status === "ready", "status must be ready");
    assert(diskVault.ready_for_real_pricing === true, "must be ready for real pricing");
    assert(diskVault.has_product_infos_template === true, "must have product_infos_template");
  });

  await testT("T3: RenderProductInfosFromTemplate server backup vault defaults", async () => {
    const res = await client.callTool({
      name: "RenderProductInfosFromTemplate",
      arguments: {
        service: "cbr",
        template_id: "cbr-server-backup-vault-gb-payg",
        region: REGION
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "render status must be OK");
    assert(data.product_infos.length === 1, "must have 1 product_info");

    const pi = data.product_infos[0];
    assert(pi.cloud_service_type === "hws.service.type.cbr", "cloud_service_type must match");
    assert(pi.resource_type === "hws.resource.type.cbr.vault", "resource_type must match");
    assert(pi.resource_spec === "vault.backup.server.normal", "resource_spec must match");
    assert(pi.usage_factor === "duration", "usage_factor must be duration");
    assert(pi.usage_value === 730, "usage_value must be 730");
    assert(pi.usage_measure_id === 4, "usage_measure_id must be 4");
    assert(pi.resource_size === 2400, "resource_size must be 2400 (default)");
    assert(pi.size_measure_id === 17, "size_measure_id must be 17");
    assert(pi.subscription_num === 1, "subscription_num must be 1");
  });

  await testT("T4: RenderProductInfosFromTemplate disk backup vault defaults", async () => {
    const res = await client.callTool({
      name: "RenderProductInfosFromTemplate",
      arguments: {
        service: "cbr",
        template_id: "cbr-disk-backup-vault-gb-payg",
        region: REGION
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "render status must be OK");
    assert(data.product_infos.length === 1, "must have 1 product_info");

    const pi = data.product_infos[0];
    assert(pi.cloud_service_type === "hws.service.type.cbr", "cloud_service_type must match");
    assert(pi.resource_type === "hws.resource.type.cbr.vault", "resource_type must match");
    assert(pi.resource_spec === "vault.backup.volume.normal", "resource_spec must match");
    assert(pi.usage_factor === "duration", "usage_factor must be duration");
    assert(pi.usage_value === 730, "usage_value must be 730");
    assert(pi.usage_measure_id === 4, "usage_measure_id must be 4");
    assert(pi.resource_size === 1000, "resource_size must be 1000 (default)");
    assert(pi.size_measure_id === 17, "size_measure_id must be 17");
    assert(pi.subscription_num === 1, "subscription_num must be 1");
  });

  await testT("T5: EstimateTemplateOnDemandPrice server vault 2400GB ≈ USD 87.60", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateTemplateOnDemandPrice",
      arguments: {
        service: "cbr",
        template_id: "cbr-server-backup-vault-gb-payg",
        region: REGION,
        parameters: {
          capacity_gb: 2400,
          monthly_hours: 730
        }
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.pricing_summary, "must have pricing_summary");
    const monthly = data.pricing_summary.monthly_amount;
    assert(monthly > 85 && monthly < 90, `monthly must be ≈87.60, got ${monthly}`);
  });

  await testT("T6: EstimateTemplateOnDemandPrice server vault 1000GB ≈ USD 36.50", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateTemplateOnDemandPrice",
      arguments: {
        service: "cbr",
        template_id: "cbr-server-backup-vault-gb-payg",
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
    assert(monthly > 35 && monthly < 38, `monthly must be ≈36.50, got ${monthly}`);
  });

  await testT("T7: EstimateTemplateOnDemandPrice disk vault 1000GB ≈ USD 21.90", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateTemplateOnDemandPrice",
      arguments: {
        service: "cbr",
        template_id: "cbr-disk-backup-vault-gb-payg",
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
    assert(monthly > 20 && monthly < 23, `monthly must be ≈21.90, got ${monthly}`);
  });

  await testT("T8: CBR Server Backup Vault + EVS GPSSD architecture pricing", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [
          {
            service: "cbr",
            template_id: "cbr-server-backup-vault-gb-payg",
            parameters: {
              capacity_gb: 2400,
              monthly_hours: 730
            }
          },
          {
            service: "evs",
            template_id: "evs-gpssd-gb-payg",
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

    const cbrPriced = data.priced_components.find((c) => c.template_id === "cbr-server-backup-vault-gb-payg");
    assert(cbrPriced, "CBR Server Backup Vault must be priced");
    assert(cbrPriced.monthly_amount > 0, "CBR must have positive monthly_amount");

    const evsPriced = data.priced_components.find((c) => c.template_id === "evs-gpssd-gb-payg");
    assert(evsPriced, "EVS must still be priced alongside CBR");

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

    assert(!data.availability_validation, "CBR must not trigger ECS availability validation");
  });

  await testT("T9: CBR Fase 1 does not include other vault types", async () => {
    const res = await client.callTool({
      name: "ListPricingTemplates",
      arguments: { service: "cbr" }
    });
    const data = JSON.parse(res.content[0].text);

    const templateIds = data.templates.map((t) => t.template_id);
    assert(!templateIds.includes("cbr-database-backup-vault-gb-payg"), "must not include database backup vault");
    assert(!templateIds.includes("cbr-multi-az-server-backup-vault-gb-payg"), "must not include multi-AZ server backup vault");
    assert(!templateIds.includes("cbr-replication-vault-gb-payg"), "must not include replication vault");
    assert(!templateIds.includes("cbr-desktop-backup-vault-gb-payg"), "must not include desktop backup vault");
    assert(!templateIds.includes("cbr-dedicated-cloud-backup-vault-gb-payg"), "must not include dedicated cloud backup vault");
    assert(!templateIds.includes("cbr-dedicated-cloud-replication-vault-gb-payg"), "must not include dedicated cloud replication vault");

    assert(templateIds.includes("cbr-server-backup-vault-gb-payg"), "must include server backup vault");
    assert(templateIds.includes("cbr-disk-backup-vault-gb-payg"), "must include disk backup vault");
    assert(templateIds.length === 2, "must have exactly 2 CBR templates in Fase 1");
  });

  await client.close();

  console.log(`\nResults: ${passed} passed, ${failed} failed, ${skipped} skipped`);
  process.exit(failed > 0 ? 1 : 0);
}

runTest().catch((e) => {
  console.error("Test runner error:", e);
  process.exit(2);
});
