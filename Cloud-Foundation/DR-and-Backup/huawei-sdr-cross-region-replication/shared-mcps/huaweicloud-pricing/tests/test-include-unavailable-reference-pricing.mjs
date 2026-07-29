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

  const schemaProps = archTool.inputSchema.properties;
  assert(
    schemaProps.include_unavailable_reference_pricing,
    "include_unavailable_reference_pricing must be in input schema"
  );
  assert(
    schemaProps.include_unavailable_reference_pricing.type === "boolean",
    "include_unavailable_reference_pricing must be boolean"
  );
  assert(
    schemaProps.include_unavailable_reference_pricing.default === false,
    "include_unavailable_reference_pricing default must be false"
  );

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

  console.log("Discovering ECS flavors for test setup...\n");

  let abandonFlavorId = null;
  let abandonVcpus = null;
  let abandonRamGb = null;
  let selloutFlavorId = null;
  let selloutVcpus = null;
  let selloutRamGb = null;
  let selloutAz = null;
  let recommendableFlavorId = null;
  let recommendableVcpus = null;
  let recommendableRamGb = null;

  const AZS_TO_CHECK = [AZ, "la-north-2b", "la-north-2c"];

  for (const checkAz of AZS_TO_CHECK) {
    try {
      const flavorsRes = await client.callTool({
        name: "QueryEcsFlavors",
        arguments: { region: REGION, availability_zone: checkAz }
      });
      const flavorsData = JSON.parse(flavorsRes.content[0].text);
      const flavors = flavorsData.result?.data?.flavors || [];

      for (const f of flavors) {
        const specs = f.os_extra_specs || {};
        const opStatus = specs["cond:operation:status"] || "";
        const azSpec = specs["cond:operation:az"] || "";
        const fVcpus = parseInt(f.vcpus, 10);
        const fRamGb = (f.ram || 0) / 1024;

        if (!abandonFlavorId && opStatus === "abandon" && fVcpus <= 8 && fRamGb <= 32) {
          abandonFlavorId = f.id;
          abandonVcpus = fVcpus;
          abandonRamGb = fRamGb;
        }

        if (!selloutFlavorId && opStatus !== "abandon") {
          const parts = azSpec.split(",");
          for (const part of parts) {
            const match = part.trim().match(/^([^(]+)\(([^)]+)\)$/);
            if (match && match[1] === checkAz && match[2] === "sellout") {
              selloutFlavorId = f.id;
              selloutVcpus = fVcpus;
              selloutRamGb = fRamGb;
              selloutAz = checkAz;
              break;
            }
          }
        }

        if (!recommendableFlavorId && opStatus === "normal") {
          const parts = azSpec.split(",");
          let azNormal = false;
          for (const part of parts) {
            const match = part.trim().match(/^([^(]+)\(([^)]+)\)$/);
            if (match && match[1] === checkAz && match[2] === "normal") {
              azNormal = true;
              break;
            }
          }
          if (azNormal) {
            recommendableFlavorId = f.id;
            recommendableVcpus = fVcpus;
            recommendableRamGb = fRamGb;
          }
        }
      }
    } catch {}
  }

  console.log(`  Setup: recommendableFlavorId=${recommendableFlavorId} (${recommendableVcpus}vCPU/${recommendableRamGb}GB)`);
  console.log(`  Setup: abandonFlavorId=${abandonFlavorId} (${abandonVcpus}vCPU/${abandonRamGb}GB)`);
  console.log(`  Setup: selloutFlavorId=${selloutFlavorId} (${selloutVcpus}vCPU/${selloutRamGb}GB) in AZ=${selloutAz}\n`);

  console.log("include_unavailable_reference_pricing tests\n");

  if (!RUN_LIVE_API) {
    console.log("  ALL TESTS SKIPPED: RUN_LIVE_API not set. These tests require HUAWEI_PROJECT_ID for BSS/OCE pricing + ECS flavor discovery APIs.");
    console.log(`\nResults: 0 passed, 0 failed, ${passed === 0 && failed === 0 ? 'all' : '0'} skipped`);
    await client.close();
    process.exit(0);
  }

  // T1: ECS recommendable, validate_availability=true, include_unavailable_reference_pricing=false
  await testT("T1: recommendable ECS with flag=false behaves as current", async () => {
    if (!recommendableFlavorId) return "skip";
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [{
          service: "ecs",
          template_id: "ecs-linux-2vcpu-4gb-payg",
          preferred_flavor: recommendableFlavorId,
          availability_zone: AZ
        }],
        validate_availability: true,
        include_unavailable_reference_pricing: false,
        default_availability_zone: AZ
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "status must be OK");
    assert(data.pricing_mode === "validated_only", `pricing_mode must be validated_only, got ${data.pricing_mode}`);
    assert(
      data.pricing_summary.monthly_total_calculated === data.pricing_summary.monthly_total_validated,
      "monthly_total must equal monthly_total_validated"
    );
    assert(!data.unavailable_reference_priced_components, "no unavailable_reference_priced_components");
  });

  // T2: ECS abandon, validate_availability=true, include_unavailable_reference_pricing=false
  await testT("T2: abandon ECS with flag=false blocks pricing", async () => {
    if (!abandonFlavorId) return "skip";
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [{
          service: "ecs",
          template_id: `ecs-linux-${abandonVcpus}vcpu-${abandonRamGb}gb-payg`,
          preferred_flavor: abandonFlavorId,
          availability_zone: AZ
        }],
        validate_availability: true,
        include_unavailable_reference_pricing: false,
        default_availability_zone: AZ
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "status must be OK");
    assert(data.availability_blocked_components.length > 0, "must have blocked components");
    assert(data.pricing_summary.monthly_total_calculated === 0, "monthly_total must be 0 (ECS excluded)");
  });

  // T3: ECS abandon, validate_availability=true, include_unavailable_reference_pricing=true
  await testT("T3: abandon ECS with flag=true gets reference pricing", async () => {
    if (!abandonFlavorId) return "skip";
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [{
          service: "ecs",
          template_id: `ecs-linux-${abandonVcpus}vcpu-${abandonRamGb}gb-payg`,
          preferred_flavor: abandonFlavorId,
          availability_zone: AZ
        }],
        validate_availability: true,
        include_unavailable_reference_pricing: true,
        default_availability_zone: AZ
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "status must be OK");
    assert(data.pricing_mode === "validated_with_reference", `pricing_mode must be validated_with_reference, got ${data.pricing_mode}`);
    assert(data.availability_blocked_components.length > 0, "must have blocked components");

    const refComponents = data.unavailable_reference_priced_components || [];
    assert(refComponents.length > 0, "must have unavailable_reference_priced_components");
    const refEcs = refComponents[0];
    assert(refEcs.deployment_status === "not_recommended", "deployment_status must be not_recommended");
    assert(
      refEcs.pricing_status === "reference_priced" || refEcs.pricing_status === "reference_pricing_failed",
      `pricing_status must be reference_priced or reference_pricing_failed, got ${refEcs.pricing_status}`
    );

    assert(
      data.pricing_summary.monthly_total_calculated === data.pricing_summary.monthly_total_validated,
      "monthly_total must equal monthly_total_validated (excludes ECS)"
    );
    assert(data.warnings && data.warnings.length > 0, "must have warnings");
    assert(
      data.warnings.some((w) => w.includes("reference only")),
      "must have warning about reference only pricing"
    );

    if (refEcs.pricing_status === "reference_priced") {
      assert(
        data.pricing_summary.monthly_total_estimated_with_blocked > data.pricing_summary.monthly_total_validated,
        "monthly_total_estimated_with_blocked must include reference ECS"
      );
      assert(refEcs.quantity !== undefined, "refEntry must have quantity field");
      assert(refEcs.unit_monthly_reference_price !== null, "must have unit_monthly_reference_price");
      assert(refEcs.monthly_reference_total !== null, "must have monthly_reference_total");
      assert(
        refEcs.monthly_reference_price === refEcs.monthly_reference_total,
        "monthly_reference_price must equal monthly_reference_total (alias)"
      );
      assert(refEcs.unit_annual_reference_price !== null, "must have unit_annual_reference_price");
      assert(refEcs.annual_reference_total !== null, "must have annual_reference_total");
      assert(
        refEcs.annual_reference_price === refEcs.annual_reference_total,
        "annual_reference_price must equal annual_reference_total (alias)"
      );
    }
  });

  // T3b: abandon ECS quantity=2 with flag=true, no double multiplication
  await testT("T3b: abandon ECS quantity=2 no double multiplication", async () => {
    if (!abandonFlavorId) return "skip";
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [{
          service: "ecs",
          template_id: `ecs-linux-${abandonVcpus}vcpu-${abandonRamGb}gb-payg`,
          preferred_flavor: abandonFlavorId,
          availability_zone: AZ,
          quantity: 2
        }],
        validate_availability: true,
        include_unavailable_reference_pricing: true,
        default_availability_zone: AZ
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "status must be OK");
    const refComponents = data.unavailable_reference_priced_components || [];
    assert(refComponents.length > 0, "must have reference components");
    const refEcs = refComponents[0];
    if (refEcs.pricing_status === "reference_priced") {
      assert(refEcs.quantity === 2, `quantity must be 2, got ${refEcs.quantity}`);
      assert(
        Math.abs(refEcs.monthly_reference_total - refEcs.unit_monthly_reference_price * 2) < 0.01,
        `monthly_reference_total must equal unit_monthly_reference_price * 2, got total=${refEcs.monthly_reference_total} unit=${refEcs.unit_monthly_reference_price}`
      );
      assert(
        refEcs.monthly_reference_total < refEcs.unit_monthly_reference_price * 3,
        `monthly_reference_total must NOT be triple the unit price (would indicate double multiplication), got total=${refEcs.monthly_reference_total} unit=${refEcs.unit_monthly_reference_price}`
      );
    }
  });

  // T4: ECS sellout, validate_availability=true, include_unavailable_reference_pricing=true
  await testT("T4: sellout ECS with flag=true gets reference pricing", async () => {
    if (!selloutFlavorId) return "skip";
    const selloutTestAz = selloutAz || AZ;
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [{
          service: "ecs",
          template_id: "ecs-linux-2vcpu-4gb-payg",
          preferred_flavor: selloutFlavorId,
          availability_zone: selloutTestAz
        }],
        validate_availability: true,
        include_unavailable_reference_pricing: true,
        default_availability_zone: selloutTestAz
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "status must be OK");
    assert(data.pricing_mode === "validated_with_reference", "pricing_mode must be validated_with_reference");

    const refComponents = data.unavailable_reference_priced_components || [];
    assert(refComponents.length > 0, "must have reference components");
    const refEcs = refComponents[0];
    assert(
      refEcs.availability_reason && refEcs.availability_reason.toLowerCase().includes("sold out"),
      `availability_reason must mention sellout, got: ${refEcs.availability_reason}`
    );
    assert(refEcs.deployment_status === "not_recommended", "deployment_status must be not_recommended");
  });

  // T5: ECS abandon where BSS/OCE may not return price → reference_pricing_failed handled
  await testT("T5: abandon ECS handles pricing failure gracefully", async () => {
    if (!abandonFlavorId) return "skip";
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [{
          service: "ecs",
          template_id: `ecs-linux-${abandonVcpus}vcpu-${abandonRamGb}gb-payg`,
          preferred_flavor: abandonFlavorId,
          availability_zone: AZ,
          parameters: { resource_spec: `${abandonFlavorId}.linux` }
        }],
        validate_availability: true,
        include_unavailable_reference_pricing: true,
        default_availability_zone: AZ
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "overall status must be OK even if reference pricing fails");
    const refComponents = data.unavailable_reference_priced_components || [];
    assert(refComponents.length > 0, "must have reference component entry");
    const refEcs = refComponents[0];
    if (refEcs.pricing_status === "reference_pricing_failed") {
      assert(refEcs.monthly_reference_price === null, "monthly_reference_price must be null on failure");
      assert(refEcs.annual_reference_price === null, "annual_reference_price must be null on failure");
      assert(refEcs.monthly_reference_total === null, "monthly_reference_total must be null on failure");
      assert(refEcs.unit_monthly_reference_price === null, "unit_monthly_reference_price must be null on failure");
      assert(refEcs.annual_reference_total === null, "annual_reference_total must be null on failure");
      assert(refEcs.unit_annual_reference_price === null, "unit_annual_reference_price must be null on failure");
      assert(refEcs.pricing_error, "must have pricing_error on failure");
    }
  });

  // T6: Mix: 1 ECS recommendable + 1 ECS abandon + 1 EVS
  await testT("T6: mixed architecture with reference pricing", async () => {
    if (!abandonFlavorId) return "skip";
    const components = [
      {
        service: "ecs",
        template_id: `ecs-linux-${abandonVcpus}vcpu-${abandonRamGb}gb-payg`,
        preferred_flavor: abandonFlavorId,
        availability_zone: AZ
      },
      {
        service: "evs",
        template_id: "evs-ssd-gb-payg",
        parameters: { size_gb: 100 }
      }
    ];
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components,
        validate_availability: true,
        include_unavailable_reference_pricing: true,
        default_availability_zone: AZ
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "status must be OK");
    assert(data.pricing_mode === "validated_with_reference", "pricing_mode must be validated_with_reference");

    const refComponents = data.unavailable_reference_priced_components || [];
    const abandonRef = refComponents.find((r) => r.template_id.includes("ecs-linux"));
    assert(abandonRef, "abandon ECS must be in reference components");
    assert(abandonRef.deployment_status === "not_recommended", "abandon ECS must be not_recommended");

    assert(data.priced_components.length > 0, "EVS must be priced normally");
    if (abandonRef.pricing_status === "reference_priced") {
      assert(
        data.pricing_summary.monthly_total_estimated_with_blocked > data.pricing_summary.monthly_total_validated,
        "monthly_total_estimated_with_blocked must be greater than monthly_total_validated when reference pricing succeeds"
      );
    }
  });

  // T7: validate_availability=false, include_unavailable_reference_pricing=true
  await testT("T7: flag=true with validate_availability=false has no effect", async () => {
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [{
          service: "evs",
          template_id: "evs-ssd-gb-payg",
          parameters: { size_gb: 100 }
        }],
        validate_availability: false,
        include_unavailable_reference_pricing: true
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "status must be OK");
    assert(data.pricing_mode === "standard_pricing", `pricing_mode must be standard_pricing, got ${data.pricing_mode}`);
    assert(data.warnings && data.warnings.length > 0, "must have warnings");
    assert(
      data.warnings.some((w) => w.includes("validate_availability=false")),
      "must have warning about flag having no effect"
    );
    assert(!data.unavailable_reference_priced_components, "no reference components when validate_availability=false");
  });

  // T8: Flag default false, validate_availability=true, ECS abandon
  await testT("T8: flag default=false identical to current behavior", async () => {
    if (!abandonFlavorId) return "skip";
    const resExplicit = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [{
          service: "ecs",
          template_id: `ecs-linux-${abandonVcpus}vcpu-${abandonRamGb}gb-payg`,
          preferred_flavor: abandonFlavorId,
          availability_zone: AZ
        }],
        validate_availability: true,
        include_unavailable_reference_pricing: false,
        default_availability_zone: AZ
      }
    });
    const dataExplicit = JSON.parse(resExplicit.content[0].text);

    const resDefault = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [{
          service: "ecs",
          template_id: `ecs-linux-${abandonVcpus}vcpu-${abandonRamGb}gb-payg`,
          preferred_flavor: abandonFlavorId,
          availability_zone: AZ
        }],
        validate_availability: true,
        default_availability_zone: AZ
      }
    });
    const dataDefault = JSON.parse(resDefault.content[0].text);

    assert(
      dataExplicit.pricing_summary.monthly_total_calculated === dataDefault.pricing_summary.monthly_total_calculated,
      "monthly_total must be same with explicit false and default"
    );
    assert(
      dataExplicit.availability_blocked_components.length === dataDefault.availability_blocked_components.length,
      "blocked components count must be same"
    );
    assert(
      dataExplicit.pricing_mode === dataDefault.pricing_mode,
      "pricing_mode must be same"
    );
  });

  // T9: ECS abandon with error in reference pricing does not crash architecture
  await testT("T9: reference pricing error does not crash architecture", async () => {
    if (!abandonFlavorId) return "skip";
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [
          {
            service: "ecs",
            template_id: `ecs-linux-${abandonVcpus}vcpu-${abandonRamGb}gb-payg`,
            preferred_flavor: abandonFlavorId,
            availability_zone: AZ
          },
          {
            service: "evs",
            template_id: "evs-ssd-gb-payg",
            parameters: { size_gb: 100 }
          }
        ],
        validate_availability: true,
        include_unavailable_reference_pricing: true,
        default_availability_zone: AZ
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "overall status must be OK even if reference pricing fails");
    assert(data.priced_components.length > 0, "other components must still be priced normally");

    const refComponents = data.unavailable_reference_priced_components || [];
    if (refComponents.length > 0 && refComponents[0].pricing_status === "reference_pricing_failed") {
      assert(refComponents[0].pricing_error, "must have sanitized pricing_error");
      assert(!refComponents[0].pricing_error.includes("AK"), "error must not contain AK");
      assert(!refComponents[0].pricing_error.includes("SK"), "error must not contain SK");
    }
  });

  // T10: Architecture only with blocked components
  await testT("T10: all-blocked architecture with reference pricing", async () => {
    if (!abandonFlavorId) return "skip";
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [{
          service: "ecs",
          template_id: `ecs-linux-${abandonVcpus}vcpu-${abandonRamGb}gb-payg`,
          preferred_flavor: abandonFlavorId,
          availability_zone: AZ
        }],
        validate_availability: true,
        include_unavailable_reference_pricing: true,
        default_availability_zone: AZ
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "status must be OK");
    assert(data.pricing_mode === "validated_with_reference", "pricing_mode must be validated_with_reference");
    assert(data.pricing_summary.monthly_total_validated === 0, "monthly_total_validated must be 0");
    assert(data.pricing_summary.monthly_total_calculated === 0, "monthly_total must be 0");

    const refComponents = data.unavailable_reference_priced_components || [];
    if (refComponents.length > 0 && refComponents[0].pricing_status === "reference_priced") {
      assert(
        data.pricing_summary.monthly_total_estimated_with_blocked > 0,
        "monthly_total_estimated_with_blocked must include reference sum"
      );
    }
  });

  // T10b: abandon ECS quantity=40, no double multiplication (CCE 40 workers scenario)
  await testT("T10b: abandon ECS quantity=40 no double multiplication", async () => {
    if (!abandonFlavorId) return "skip";
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [{
          service: "ecs",
          template_id: `ecs-linux-${abandonVcpus}vcpu-${abandonRamGb}gb-payg`,
          preferred_flavor: abandonFlavorId,
          availability_zone: AZ,
          quantity: 40
        }],
        validate_availability: true,
        include_unavailable_reference_pricing: true,
        default_availability_zone: AZ
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "OK", "status must be OK");
    const refComponents = data.unavailable_reference_priced_components || [];
    assert(refComponents.length > 0, "must have reference components");
    const refEcs = refComponents[0];
    if (refEcs.pricing_status === "reference_priced") {
      assert(refEcs.quantity === 40, `quantity must be 40, got ${refEcs.quantity}`);
      assert(refEcs.unit_monthly_reference_price > 0, "unit_monthly_reference_price must be positive");
      const expectedTotal = refEcs.unit_monthly_reference_price * 40;
      assert(
        Math.abs(refEcs.monthly_reference_total - expectedTotal) < 0.01,
        `monthly_reference_total must equal unit * 40, got total=${refEcs.monthly_reference_total} expected=${expectedTotal}`
      );
      const wrongDoubleMult = refEcs.unit_monthly_reference_price * 40 * 40;
      assert(
        refEcs.monthly_reference_total < wrongDoubleMult * 0.5,
        `monthly_reference_total must NOT show double multiplication (would be ~${wrongDoubleMult.toFixed(2)}), got ${refEcs.monthly_reference_total}`
      );
      assert(
        Math.abs(data.pricing_summary.monthly_total_estimated_with_blocked - refEcs.monthly_reference_total) < 0.01,
        `monthly_total_estimated_with_blocked must equal monthly_reference_total when all components blocked, got ${data.pricing_summary.monthly_total_estimated_with_blocked} vs ${refEcs.monthly_reference_total}`
      );
    }
  });

  // Extra: pricing_mode=validated_only when no blocked components
  await testT("Extra: pricing_mode=validated_only when no blocked components", async () => {
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [{
          service: "evs",
          template_id: "evs-ssd-gb-payg",
          parameters: { size_gb: 100 }
        }],
        validate_availability: true,
        include_unavailable_reference_pricing: true,
        default_availability_zone: AZ
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.pricing_mode === "validated_only", `pricing_mode must be validated_only when no blocked, got ${data.pricing_mode}`);
  });

  // Extra: monthly_total always equals monthly_total_validated
  await testT("Extra: monthly_total always equals monthly_total_validated", async () => {
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [{
          service: "evs",
          template_id: "evs-ssd-gb-payg",
          parameters: { size_gb: 50 }
        }],
        validate_availability: false
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(
      data.pricing_summary.monthly_total_calculated === data.pricing_summary.monthly_total_validated,
      "monthly_total must always equal monthly_total_validated"
    );
  });

  // Extra: standard_pricing without flag has no warnings
  await testT("Extra: standard_pricing without flag has no warnings", async () => {
    const res = await client.callTool({
      name: "EstimateArchitectureOnDemandPrice",
      arguments: {
        region: REGION,
        components: [{
          service: "evs",
          template_id: "evs-ssd-gb-payg",
          parameters: { size_gb: 50 }
        }],
        validate_availability: false
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.pricing_mode === "standard_pricing", "pricing_mode must be standard_pricing");
    assert(!data.warnings || data.warnings.length === 0, "no warnings in standard mode without flag");
  });

  // Extra: pricing_mode field always present
  await testT("Extra: pricing_mode always present in output", async () => {
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
    assert(data.pricing_mode !== undefined, "pricing_mode must always be present");
    assert(
      ["standard_pricing", "validated_only", "validated_with_reference"].includes(data.pricing_mode),
      `pricing_mode must be valid, got ${data.pricing_mode}`
    );
  });

  // Extra: monthly_total_validated always present
  await testT("Extra: monthly_total_validated always present in output", async () => {
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
    assert(data.pricing_summary.monthly_total_validated !== undefined, "monthly_total_validated must always be present");
  });

  await client.close();

  console.log(`\nResults: ${passed} passed, ${failed} failed, ${skipped} skipped`);
  process.exit(failed > 0 ? 1 : 0);
}

runTest().catch((e) => {
  console.error("Test runner error:", e);
  process.exit(2);
});
