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

  console.log("ELB service_cost_breakdown tests\n");

  // T1: ELB shared public with EIP auto-injected
  await testT("T1: ELB shared public with EIP auto-injected", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [{
          service: "elb",
          template_id: "elb-shared-instance-payg",
          parameters: {
            network_type: "public",
            bandwith_mbps: 20,
            monthly_hours: 730
          }
        }]
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "status must be OK");

    const elbComp = data.priced_components.find((c) => c.template_id === "elb-shared-instance-payg");
    const eipComp = data.priced_components.find((c) => c.template_id === "eip-bandwidth-mbps-payg");
    assert(elbComp, "ELB must be priced");
    assert(eipComp, "EIP must be priced (auto-injected)");

    assert(data.service_cost_breakdown, "service_cost_breakdown must exist");
    assert(data.service_cost_breakdown.length === 1, "must have exactly 1 group");
    const group = data.service_cost_breakdown[0];
    assert(group.group_type === "public_shared_elb", "group_type must be public_shared_elb");
    assert(group.components.length === 2, "group must have 2 components");
    assert(
      group.monthly_group_total === elbComp.monthly_amount + eipComp.monthly_amount,
      "monthly_group_total must equal ELB + EIP"
    );

    if (elbComp.monthly_amount === 0) {
      assert(elbComp.pricing_notes, "ELB must have pricing_notes when monthly_amount===0");
      assert(
        elbComp.pricing_notes.some((n) => n.includes("BSS/OCE") && n.includes("0.00")),
        "pricing_notes must mention BSS/OCE 0.00"
      );
      assert(
        elbComp.pricing_notes.some((n) => n.includes("EIP bandwidth")),
        "pricing_notes must mention EIP bandwidth"
      );
    }
  });

  // T2: ELB shared public + EIP manual (no duplication)
  await testT("T2: ELB shared public + EIP manual (no duplication)", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [
          {
            service: "elb",
            template_id: "elb-shared-instance-payg",
            parameters: {
              network_type: "public",
              monthly_hours: 730
            }
          },
          {
            service: "eip",
            template_id: "eip-bandwidth-mbps-payg",
            parameters: {
              bandwidth_mbps: 30,
              monthly_hours: 730
            }
          }
        ]
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "status must be OK");

    const eipComps = data.priced_components.filter((c) => c.template_id === "eip-bandwidth-mbps-payg");
    assert(eipComps.length === 1, "EIP must not be duplicated");

    assert(data.service_cost_breakdown, "service_cost_breakdown must exist");
    const group = data.service_cost_breakdown[0];
    assert(group.group_type === "public_shared_elb", "group_type must be public_shared_elb");
    assert(
      group.monthly_group_total === data.priced_components.find((c) => c.template_id === "elb-shared-instance-payg").monthly_amount + eipComps[0].monthly_amount,
      "monthly_group_total must equal ELB + EIP manual"
    );
  });

  // T3: ELB shared internal
  await testT("T3: ELB shared internal", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [{
          service: "elb",
          template_id: "elb-shared-instance-payg",
          parameters: {
            network_type: "internal",
            monthly_hours: 730
          }
        }]
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "status must be OK");

    const eipComps = data.priced_components.filter((c) => c.template_id === "eip-bandwidth-mbps-payg");
    assert(eipComps.length === 0, "No EIP must be added for internal ELB");

    assert(!data.service_cost_breakdown, "No service_cost_breakdown for internal ELB");

    const elbComp = data.priced_components.find((c) => c.template_id === "elb-shared-instance-payg");
    if (elbComp && elbComp.monthly_amount === 0) {
      assert(elbComp.pricing_notes, "ELB must have pricing_notes when monthly_amount===0");
      assert(
        elbComp.pricing_notes.some((n) => n.includes("internal")),
        "pricing_notes must mention internal"
      );
      assert(
        elbComp.pricing_notes.some((n) => n.includes("No public EIP/bandwidth")),
        "pricing_notes must say no public bandwidth required"
      );
    }
  });

  // T4: ELB shared without network_type
  await testT("T4: ELB shared without network_type", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [{
          service: "elb",
          template_id: "elb-shared-instance-payg",
          parameters: {
            monthly_hours: 730
          }
        }]
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "status must be OK");

    const eipComps = data.priced_components.filter((c) => c.template_id === "eip-bandwidth-mbps-payg");
    assert(eipComps.length === 0, "No EIP must be added when no network_type");

    assert(!data.service_cost_breakdown, "No service_cost_breakdown when no network_type");

    const elbComp = data.priced_components.find((c) => c.template_id === "elb-shared-instance-payg");
    if (elbComp && elbComp.monthly_amount === 0) {
      assert(elbComp.pricing_notes, "ELB must have pricing_notes when monthly_amount===0");
      assert(
        elbComp.pricing_notes.some((n) => n.includes("network_type") && n.includes("not specified") || n.includes("was specified")),
        "pricing_notes must mention network_type not specified"
      );
    }
  });

  // T5: ELB shared with amount > 0 (we can't control BSS/OCE, but we verify the structure)
  await testT("T5: ELB shared amount > 0 respects BSS/OCE price", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [{
          service: "elb",
          template_id: "elb-shared-instance-payg",
          parameters: {
            network_type: "public",
            bandwith_mbps: 20,
            monthly_hours: 730
          }
        }]
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "status must be OK");

    const elbComp = data.priced_components.find((c) => c.template_id === "elb-shared-instance-payg");
    assert(elbComp, "ELB must be priced");
    assert(typeof elbComp.monthly_amount === "number", "monthly_amount must be a number");

    if (elbComp.monthly_amount > 0 && data.service_cost_breakdown) {
      const group = data.service_cost_breakdown[0];
      assert(group.group_type === "public_shared_elb", "group_type must be public_shared_elb");
      assert(
        !group.notes.some((n) => n.includes("0.00")),
        "Notes must not say ELB is free when amount > 0"
      );
    }

    if (elbComp.monthly_amount > 0) {
      assert(!elbComp.pricing_notes, "No pricing_notes when monthly_amount > 0");
    }
  });

  // T6: Two ELB publics and one EIP → ambiguous
  await testT("T6: Two ELB publics + one EIP → ambiguous grouping", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [
          {
            service: "elb",
            template_id: "elb-shared-instance-payg",
            parameters: { network_type: "public", monthly_hours: 730 }
          },
          {
            service: "elb",
            template_id: "elb-shared-instance-payg",
            parameters: { network_type: "public", monthly_hours: 730 }
          },
          {
            service: "eip",
            template_id: "eip-bandwidth-mbps-payg",
            parameters: { bandwidth_mbps: 20, monthly_hours: 730 }
          }
        ]
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "status must be OK");
    assert(!data.service_cost_breakdown, "No service_cost_breakdown for ambiguous grouping");
    assert(
      data.warnings && data.warnings.some((w) => w.includes("Multiple ELB/EIP")),
      "Must have warning about multiple ELB/EIP"
    );
  });

  // T7: Two EIPs and one ELB public → ambiguous
  await testT("T7: Two EIPs + one ELB public → ambiguous grouping", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [
          {
            service: "elb",
            template_id: "elb-shared-instance-payg",
            parameters: { network_type: "public", monthly_hours: 730 }
          },
          {
            service: "eip",
            template_id: "eip-bandwidth-mbps-payg",
            parameters: { bandwidth_mbps: 20, monthly_hours: 730 }
          },
          {
            service: "eip",
            template_id: "eip-bandwidth-mbps-payg",
            parameters: { bandwidth_mbps: 30, monthly_hours: 730 }
          }
        ]
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "status must be OK");
    assert(!data.service_cost_breakdown, "No service_cost_breakdown for ambiguous grouping");
    assert(
      data.warnings && data.warnings.some((w) => w.includes("Multiple ELB/EIP")),
      "Must have warning about multiple ELB/EIP"
    );
  });

  // T8: Full public web architecture with ECS/EVS/ELB/EIP/RDS/OBS
  await testT("T8: Full public web architecture", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [
          {
            service: "ecs",
            template_id: "ecs-linux-2vcpu-4gb-payg",
            parameters: { monthly_hours: 730, system_disk_gb: 40 }
          },
          {
            service: "evs",
            template_id: "evs-ssd-gb-payg",
            parameters: { size_gb: 100 }
          },
          {
            service: "elb",
            template_id: "elb-shared-instance-payg",
            parameters: { network_type: "public", bandwith_mbps: 20, monthly_hours: 730 }
          },
          {
            service: "rds",
            template_id: "rds-mysql-small-payg",
            parameters: { monthly_hours: 730, storage_gb: 100 }
          },
          {
            service: "evs",
            template_id: "evs-ssd-gb-payg",
            parameters: { size_gb: 500 }
          }
        ]
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "status must be OK");

    assert(data.service_cost_breakdown, "service_cost_breakdown must exist for full architecture");
    const group = data.service_cost_breakdown.find((g) => g.group_type === "public_shared_elb");
    assert(group, "Must have public_shared_elb group");

    const elbComp = data.priced_components.find((c) => c.template_id === "elb-shared-instance-payg");
    if (elbComp && elbComp.monthly_amount === 0) {
      assert(elbComp.pricing_notes, "ELB must have pricing_notes when monthly_amount===0");
    }

    assert(data.priced_components.length >= 4, "Must have multiple priced components");
  });

  // T9: Retrocompatibility - monthly_total identical before/after change
  await testT("T9: Retrocompatibility - monthly_total unchanged", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [
          {
            service: "elb",
            template_id: "elb-shared-instance-payg",
            parameters: { network_type: "public", bandwith_mbps: 20, monthly_hours: 730 }
          },
          {
            service: "evs",
            template_id: "evs-ssd-gb-payg",
            parameters: { size_gb: 100 }
          }
        ]
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "status must be OK");
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
  });

  // T10: Dedicated ELB placeholder - no modification
  await testT("T10: Dedicated ELB placeholder - no behavior change", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [{
          service: "evs",
          template_id: "evs-ssd-gb-payg",
          parameters: { size_gb: 50 }
        }]
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "status must be OK");
    assert(!data.service_cost_breakdown, "No service_cost_breakdown for non-ELB architecture");
    assert(
      data.pricing_summary.monthly_total_calculated === data.pricing_summary.monthly_total_validated,
      "monthly_total must equal monthly_total_validated"
    );
  });

  // Extra: componentPricingMap is internal (not exposed in output)
  await testT("Extra: componentPricingMap not exposed in output", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [{
          service: "elb",
          template_id: "elb-shared-instance-payg",
          parameters: { network_type: "public", bandwith_mbps: 20, monthly_hours: 730 }
        }]
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(!data.componentPricingMap, "componentPricingMap must not be exposed in output");
  });

  // Extra: service_cost_breakdown group structure
  await testT("Extra: service_cost_breakdown group structure", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [{
          service: "elb",
          template_id: "elb-shared-instance-payg",
          parameters: { network_type: "public", bandwith_mbps: 20, monthly_hours: 730 }
        }]
      }
    });
    const data = JSON.parse(res.content[0].text);
    if (data.service_cost_breakdown && data.service_cost_breakdown.length > 0) {
      const group = data.service_cost_breakdown[0];
      assert(group.group_type === "public_shared_elb", "group_type");
      assert(group.description, "description must exist");
      assert(group.pricing_source === "BSS/OCE", "pricing_source must be BSS/OCE");
      assert(Array.isArray(group.components), "components must be array");
      assert(typeof group.monthly_group_total === "number", "monthly_group_total must be number");
      assert(Array.isArray(group.notes), "notes must be array");
      assert(
        group.notes.some((n) => n.includes("informational") && n.includes("does not change monthly_total")),
        "notes must say group is informational"
      );
    }
  });

  // Extra: ELB internal does not create group even with EIP present
  await testT("Extra: ELB internal + separate EIP does not create group", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [
          {
            service: "elb",
            template_id: "elb-shared-instance-payg",
            parameters: { network_type: "internal", monthly_hours: 730 }
          },
          {
            service: "eip",
            template_id: "eip-bandwidth-mbps-payg",
            parameters: { bandwidth_mbps: 20, monthly_hours: 730 }
          }
        ]
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "status must be OK");
    assert(!data.service_cost_breakdown, "No service_cost_breakdown for internal ELB + separate EIP");
  });

  await client.close();

  console.log(`\nResults: ${passed} passed, ${failed} failed, ${skipped} skipped`);
  process.exit(failed > 0 ? 1 : 0);
}

runTest().catch((e) => {
  console.error("Test runner error:", e);
  process.exit(2);
});
