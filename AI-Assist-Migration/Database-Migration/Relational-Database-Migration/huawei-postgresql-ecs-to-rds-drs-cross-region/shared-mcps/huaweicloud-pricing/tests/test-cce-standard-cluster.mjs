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

  const draftTool = tools.tools.find((t) => t.name === "EstimateArchitectureCostDraft");
  assert(draftTool, "EstimateArchitectureCostDraft tool must be registered");

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
  const AZ = "la-north-2a";

  console.log("CCE Standard Cluster Phase 1 tests\n");

  // T1: CCE small sin ingress publico → 5 componentes
  await testT("T1: CCE small sin ingress publico expande a 5 componentes", async () => {
    const res = await client.callTool({
      name: "EstimateArchitectureCostDraft",
      arguments: {
        region: REGION,
        components: [{
          service: "cce",
          template_id: "cce-standard-cluster-payg",
          parameters: {
            cluster_type: "standard",
            cluster_scale: "cce.s1.small",
            node_count: 2,
            node_template_id: "ecs-linux-2vcpu-4gb-payg",
            node_system_disk_size_gb: 40,
            node_data_disk_size_gb: null,
            public_ingress: false
          }
        }]
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.normalization, "normalization must exist");
    assert(data.normalization.notes.length > 0, "must have normalization notes");

    const cceMgmt = data.components.filter((c) => c.template_id === "cce-cluster-mgmt-payg");
    const ecsComps = data.components.filter((c) => c.service === "ecs");
    const evsComps = data.components.filter((c) => c.service === "evs");
    const elbComps = data.components.filter((c) => c.service === "elb");
    const eipComps = data.components.filter((c) => c.service === "eip");

    assert(cceMgmt.length === 1, `must have 1 CCE cluster mgmt, got ${cceMgmt.length}`);
    assert(ecsComps.length === 2, `must have 2 ECS, got ${ecsComps.length}`);
    assert(evsComps.length === 2, `must have 2 EVS system disks, got ${evsComps.length}`);
    assert(elbComps.length === 0, `must have 0 ELB, got ${elbComps.length}`);
    assert(eipComps.length === 0, `must have 0 EIP, got ${eipComps.length}`);
    assert(data.normalization.normalized_components_count === 5, `total must be 5, got ${data.normalization.normalized_components_count}`);
  });

  // T2: CCE small con ingress publico → 7 componentes
  await testT("T2: CCE small con ingress publico expande a 7 componentes", async () => {
    const res = await client.callTool({
      name: "EstimateArchitectureCostDraft",
      arguments: {
        region: REGION,
        components: [{
          service: "cce",
          template_id: "cce-standard-cluster-payg",
          parameters: {
            cluster_type: "standard",
            cluster_scale: "cce.s1.small",
            node_count: 2,
            node_template_id: "ecs-linux-2vcpu-4gb-payg",
            node_system_disk_size_gb: 40,
            public_ingress: true,
            ingress_bandwidth_mbps: 20
          }
        }]
      }
    });
    const data = JSON.parse(res.content[0].text);

    const cceMgmt = data.components.filter((c) => c.template_id === "cce-cluster-mgmt-payg");
    const ecsComps = data.components.filter((c) => c.service === "ecs");
    const evsComps = data.components.filter((c) => c.service === "evs");
    const elbComps = data.components.filter((c) => c.service === "elb");
    const eipComps = data.components.filter((c) => c.service === "eip");

    assert(cceMgmt.length === 1, `must have 1 CCE cluster mgmt, got ${cceMgmt.length}`);
    assert(ecsComps.length === 2, `must have 2 ECS, got ${ecsComps.length}`);
    assert(evsComps.length === 2, `must have 2 EVS, got ${evsComps.length}`);
    assert(elbComps.length === 1, `must have 1 ELB, got ${elbComps.length}`);
    assert(eipComps.length === 1, `must have 1 EIP auto-agregado, got ${eipComps.length}`);
    assert(data.normalization.normalized_components_count === 7, `total must be 7, got ${data.normalization.normalized_components_count}`);
  });

  // T3: CCE con data disk → 2 EVS data disk adicionales
  await testT("T3: CCE con data disk agrega EVS data disks", async () => {
    const res = await client.callTool({
      name: "EstimateArchitectureCostDraft",
      arguments: {
        region: REGION,
        components: [{
          service: "cce",
          template_id: "cce-standard-cluster-payg",
          parameters: {
            cluster_type: "standard",
            cluster_scale: "cce.s1.small",
            node_count: 2,
            node_template_id: "ecs-linux-2vcpu-4gb-payg",
            node_system_disk_size_gb: 40,
            node_data_disk_size_gb: 100,
            public_ingress: false
          }
        }]
      }
    });
    const data = JSON.parse(res.content[0].text);

    const evsComps = data.components.filter((c) => c.service === "evs");
    assert(evsComps.length === 4, `must have 4 EVS (2 system + 2 data), got ${evsComps.length}`);

    const systemDiskComps = evsComps.filter((c) => c.resolved_parameters && c.resolved_parameters.size_gb === 40);
    const dataDiskComps = evsComps.filter((c) => c.resolved_parameters && c.resolved_parameters.size_gb === 100);
    assert(systemDiskComps.length === 2, `must have 2 system disk EVS, got ${systemDiskComps.length}`);
    assert(dataDiskComps.length === 2, `must have 2 data disk EVS, got ${dataDiskComps.length}`);
  });

  // T4: EstimateArchitectureOnDemandPrice con validate_availability=false
  await testT("T4: CCE small con validate_availability=false cotiza todo", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [{
          service: "cce",
          template_id: "cce-standard-cluster-payg",
          parameters: {
            cluster_type: "standard",
            cluster_scale: "cce.s1.small",
            node_count: 2,
            node_template_id: "ecs-linux-2vcpu-4gb-payg",
            node_system_disk_size_gb: 40,
            public_ingress: false
          }
        }],
        validate_availability: false
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "status must be OK");

    const ccePriced = data.priced_components.find((c) => c.template_id === "cce-cluster-mgmt-payg");
    assert(ccePriced, "CCE cluster management must be priced");

    const ecsPriced = data.priced_components.filter((c) => c.service === "ecs");
    assert(ecsPriced.length === 2, `must have 2 priced ECS, got ${ecsPriced.length}`);

    const evsPriced = data.priced_components.filter((c) => c.service === "evs");
    assert(evsPriced.length === 2, `must have 2 priced EVS, got ${evsPriced.length}`);

    assert(data.pricing_summary.monthly_total_calculated > 0, "monthly_total must include all components");
    assert(
      data.pricing_summary.monthly_total_calculated === data.pricing_summary.monthly_total_validated,
      "monthly_total must equal monthly_total_validated"
    );
  });

  // T5: EstimateArchitectureOnDemandPrice con validate_availability=true
  await testT("T5: CCE small con validate_availability=true valida ECS workers", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing + ECS flavor discovery API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [{
          service: "cce",
          template_id: "cce-standard-cluster-payg",
          parameters: {
            cluster_type: "standard",
            cluster_scale: "cce.s1.small",
            node_count: 2,
            node_template_id: "ecs-linux-2vcpu-4gb-payg",
            node_system_disk_size_gb: 40,
            public_ingress: false
          }
        }],
        validate_availability: true,
        default_availability_zone: AZ
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "status must be OK");
    assert(data.availability_validation, "availability_validation must exist");
    assert(data.availability_validation.enabled === true, "availability_validation must be enabled");

    const ccePriced = data.priced_components.find((c) => c.template_id === "cce-cluster-mgmt-payg");
    assert(ccePriced, "CCE cluster management must be priced regardless of availability validation");

    const availComps = data.availability_validation.components;
    const ecsAvailComps = availComps.filter((c) => c.component_type === "ecs");
    assert(ecsAvailComps.length === 2, "both ECS workers must be validated for availability");

    if (data.availability_blocked_components.length > 0) {
      const blockedEcs = data.availability_blocked_components.filter((c) => c.service === "ecs");
      const ecsInMonthlyTotal = data.priced_components.filter((c) => c.service === "ecs");
      assert(ecsInMonthlyTotal.length === 0, "blocked ECS must be excluded from monthly_total");
    }
  });

  // T6: CCE small con validate_availability=true e include_unavailable_reference_pricing=true
  await testT("T6: CCE small con reference pricing para ECS abandon", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing + ECS flavor discovery API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [{
          service: "cce",
          template_id: "cce-standard-cluster-payg",
          parameters: {
            cluster_type: "standard",
            cluster_scale: "cce.s1.small",
            node_count: 2,
            node_template_id: "ecs-linux-2vcpu-4gb-payg",
            node_system_disk_size_gb: 40,
            public_ingress: false
          }
        }],
        validate_availability: true,
        include_unavailable_reference_pricing: true,
        default_availability_zone: AZ
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "status must be OK");

    if (data.availability_blocked_components.length > 0 && data.pricing_mode === "validated_with_reference") {
      assert(data.unavailable_reference_priced_components, "must have unavailable_reference_priced_components");
      assert(data.unavailable_reference_priced_components.length > 0, "must have reference priced components");

      const refEcs = data.unavailable_reference_priced_components.filter((c) => c.template_id.includes("ecs"));
      if (refEcs.length > 0) {
        assert(refEcs[0].deployment_status === "not_recommended", "reference ECS must be not_recommended");
        assert(
          refEcs[0].pricing_status === "reference_priced" || refEcs[0].pricing_status === "reference_pricing_failed",
          "pricing_status must be reference_priced or reference_pricing_failed"
        );
      }

      assert(
        data.pricing_summary.monthly_total_calculated === data.pricing_summary.monthly_total_validated,
        "monthly_total must equal monthly_total_validated (excludes blocked ECS)"
      );

      if (data.unavailable_reference_pricedComponents?.[0]?.pricing_status === "reference_priced" ||
          (data.unavailable_reference_priced_components && data.unavailable_reference_priced_components[0]?.pricing_status === "reference_priced")) {
        assert(
          data.pricing_summary.monthly_total_estimated_with_blocked > data.pricing_summary.monthly_total_validated,
          "monthly_total_estimated_with_blocked must include reference ECS"
        );
      }
    }
  });

  // T7: CCE public ingress → service_cost_breakdown incluye public_shared_elb
  await testT("T7: CCE public ingress con service_cost_breakdown", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API (ELB must be priced for service_cost_breakdown)");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [{
          service: "cce",
          template_id: "cce-standard-cluster-payg",
          parameters: {
            cluster_type: "standard",
            cluster_scale: "cce.s1.small",
            node_count: 2,
            node_template_id: "ecs-linux-2vcpu-4gb-payg",
            node_system_disk_size_gb: 40,
            public_ingress: true,
            ingress_bandwidth_mbps: 20
          }
        }],
        validate_availability: false
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "status must be OK");

    assert(data.service_cost_breakdown, "service_cost_breakdown must exist");
    const group = data.service_cost_breakdown.find((g) => g.group_type === "public_shared_elb");
    assert(group, "must have public_shared_elb group");

    const elbComp = data.priced_components.find((c) => c.template_id === "elb-shared-instance-payg");
    if (elbComp && elbComp.monthly_amount === 0) {
      assert(elbComp.pricing_notes, "ELB must have pricing_notes when monthly_amount===0");
    }
  });

  // T8: CCE Turbo → unsupported en Phase 1
  await testT("T8: CCE Turbo no se cotiza como ready en Phase 1", async () => {
    const res = await client.callTool({
      name: "EstimateArchitectureCostDraft",
      arguments: {
        region: REGION,
        components: [{
          service: "cce",
          template_id: "cce-standard-cluster-payg",
          parameters: {
            cluster_type: "turbo",
            cluster_scale: "cce.s1.small",
            node_count: 2,
            node_template_id: "ecs-linux-2vcpu-4gb-payg",
            node_system_disk_size_gb: 40,
            public_ingress: false
          }
        }]
      }
    });
    const data = JSON.parse(res.content[0].text);

    const turboComp = data.components.find((c) => c.template_id === "cce-standard-cluster-payg");
    assert(turboComp, "Turbo component must be present");
    assert(
      turboComp.template_status === "missing_product_infos_template" || turboComp.status === "MISSING_TEMPLATE" || turboComp.ready_for_real_pricing === false,
      "Turbo must not be ready for real pricing in Phase 1"
    );

    const turboNote = data.normalization.notes.find((n) => n.action === "cce_turbo_unsupported_phase1");
    assert(turboNote, "must have cce_turbo_unsupported_phase1 normalization note");
  });

  // Extra: CCE cluster management template exists in ListPricingTemplates
  await testT("Extra: cce-cluster-mgmt-payg visible in ListPricingTemplates", async () => {
    const res = await client.callTool({
      name: "ListPricingTemplates",
      arguments: { service: "cce" }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.templates.length > 0, "must have CCE templates");

    const cceMgmt = data.templates.find((t) => t.template_id === "cce-cluster-mgmt-payg");
    assert(cceMgmt, "cce-cluster-mgmt-payg must be listed");
    assert(cceMgmt.status === "ready", "cce-cluster-mgmt-payg must be ready");
    assert(cceMgmt.ready_for_real_pricing === true, "cce-cluster-mgmt-payg must be ready for real pricing");
  });

  // Extra: RenderProductInfosFromTemplate for CCE
  await testT("Extra: RenderProductInfosFromTemplate for CCE cluster mgmt", async () => {
    const res = await client.callTool({
      name: "RenderProductInfosFromTemplate",
      arguments: {
        service: "cce",
        template_id: "cce-cluster-mgmt-payg",
        region: REGION,
        parameters: {
          resource_spec: "cce.s1.small",
          monthly_hours: 730
        }
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "render status must be OK");
    assert(data.product_infos.length === 1, "must have 1 product_info");
    assert(data.product_infos[0].cloud_service_type === "hws.service.type.cce", "cloud_service_type must match");
    assert(data.product_infos[0].resource_type === "hws.resource.type.cce.cluster", "resource_type must match");
    assert(data.product_infos[0].resource_spec === "cce.s1.small", "resource_spec must be cce.s1.small");
    assert(data.product_infos[0].usage_measure_id === 4, "usage_measure_id must be 4");
  });

  // Extra: monthly_total semantics preserved with CCE
  await testT("Extra: monthly_total semantics preserved with CCE", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for BSS/OCE pricing API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [{
          service: "cce",
          template_id: "cce-standard-cluster-payg",
          parameters: {
            cluster_type: "standard",
            cluster_scale: "cce.s1.small",
            node_count: 1,
            node_template_id: "ecs-linux-2vcpu-4gb-payg",
            node_system_disk_size_gb: 40,
            public_ingress: false
          }
        }],
        validate_availability: false
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

  await client.close();

  console.log(`\nResults: ${passed} passed, ${failed} failed, ${skipped} skipped`);
  process.exit(failed > 0 ? 1 : 0);
}

runTest().catch((e) => {
  console.error("Test runner error:", e);
  process.exit(2);
});
