import { listPricingTemplates, renderProductInfosFromTemplate } from "./template-tools.mjs";

const RUN_LIVE = process.env.RUN_LIVE_API === "true";
const REGION = "la-north-2";
const PROJECT_ID = "139bbc9f161d48c5a4612990bb3d6643";

let passed = 0;
let failed = 0;
let skipped = 0;

function assert(condition, label) {
  if (condition) {
    console.log(`  PASS: ${label}`);
    passed++;
  } else {
    console.log(`  FAIL: ${label}`);
    failed++;
  }
}

function skip(label, reason) {
  console.log(`  SKIP: ${label} (${reason})`);
  skipped++;
}

async function queryOnDemandPrice(productInfos, region) {
  const { default: axios } = await import("axios");
  const fs = await import("fs");

  const tmpFile = `/tmp/test-ecs-product-infos-${Date.now()}.json`;
  fs.writeFileSync(tmpFile, JSON.stringify(productInfos));

  const cmd = [
    ".venv/bin/python",
    "pricing_api_helper.py",
    "on-demand-price",
    "--product-infos-file", tmpFile,
    "--project-id", PROJECT_ID,
    "--inquiry-precision", "1"
  ].join(" ");

  const { execSync } = await import("child_process");
  try {
    const result = execSync(cmd, { cwd: "/root/opencode-pricing-assistant/pricing-mcp", timeout: 30000 }).toString();
    fs.unlinkSync(tmpFile);
    return JSON.parse(result);
  } catch (e) {
    fs.unlinkSync(tmpFile);
    throw e;
  }
}

console.log("=== T1: ListPricingTemplates includes ecs-flavor-payg ===");
{
  const result = listPricingTemplates({ service: "ecs" });
  const ids = result.templates.map(t => t.template_id);
  assert(ids.includes("ecs-flavor-payg"), "ecs-flavor-payg found in templates");
}

console.log("\n=== T2: ListPricingTemplates includes ecs-os-license-payg ===");
{
  const result = listPricingTemplates({ service: "ecs" });
  const ids = result.templates.map(t => t.template_id);
  assert(ids.includes("ecs-os-license-payg"), "ecs-os-license-payg found in templates");
}

console.log("\n=== T3: RenderProductInfosFromTemplate ecs-flavor-payg with defaults ===");
{
  const result = renderProductInfosFromTemplate({
    service: "ecs",
    template_id: "ecs-flavor-payg",
    region: REGION
  });
  assert(result.status === "OK", "status is OK");
  const pi = result.product_infos[0];
  assert(pi.cloud_service_type === "hws.service.type.ec2", "cloud_service_type = hws.service.type.ec2");
  assert(pi.resource_type === "hws.resource.type.vm", "resource_type = hws.resource.type.vm");
  assert(pi.resource_spec === "s6.xlarge.4.linux", `resource_spec = s6.xlarge.4.linux (got ${pi.resource_spec})`);
  assert(pi.usage_factor === "Duration", "usage_factor = Duration");
  assert(pi.usage_value === 730, "usage_value = 730");
  assert(pi.usage_measure_id === 4, "usage_measure_id = 4");
}

console.log("\n=== T4: RenderProductInfosFromTemplate ecs-flavor-payg with m6.3xlarge.8.linux ===");
{
  const result = renderProductInfosFromTemplate({
    service: "ecs",
    template_id: "ecs-flavor-payg",
    region: REGION,
    parameters: { ecs_resource_spec: "m6.3xlarge.8.linux" }
  });
  assert(result.status === "OK", "status is OK");
  const pi = result.product_infos[0];
  assert(pi.resource_spec === "m6.3xlarge.8.linux", `resource_spec = m6.3xlarge.8.linux (got ${pi.resource_spec})`);
}

console.log("\n=== T5: RenderProductInfosFromTemplate ecs-os-license-payg with defaults ===");
{
  const result = renderProductInfosFromTemplate({
    service: "ecs",
    template_id: "ecs-os-license-payg",
    region: REGION
  });
  assert(result.status === "OK", "status is OK");
  const pi = result.product_infos[0];
  assert(pi.resource_type === "hws.resource.type.vm.image", `resource_type = hws.resource.type.vm.image (got ${pi.resource_type})`);
  assert(pi.resource_spec === "suse.12", `resource_spec = suse.12 (got ${pi.resource_spec})`);
}

console.log("\n=== T6: EstimateTemplateOnDemandPrice m6.3xlarge.8.linux (live) ===");
if (RUN_LIVE) {
  const rendered = renderProductInfosFromTemplate({
    service: "ecs",
    template_id: "ecs-flavor-payg",
    region: REGION,
    parameters: { ecs_resource_spec: "m6.3xlarge.8.linux" }
  });
  const result = await queryOnDemandPrice(rendered.product_infos, REGION);
  const amount = result.data.amount;
  console.log(`  BSS/OCE amount: USD ${amount}`);
  console.log(`  Quotation target: USD 356.36`);
  console.log(`  Ratio: ${(amount / 356.36).toFixed(4)}`);
  assert(amount > 0, "amount > 0");
  assert(Math.abs(amount - 494.94) < 1.0, `amount ≈ 494.94 (got ${amount})`);
} else {
  skip("T6", "RUN_LIVE_API not set");
}

console.log("\n=== T7: EstimateTemplateOnDemandPrice suse.12 (live) ===");
if (RUN_LIVE) {
  const rendered = renderProductInfosFromTemplate({
    service: "ecs",
    template_id: "ecs-os-license-payg",
    region: REGION
  });
  const result = await queryOnDemandPrice(rendered.product_infos, REGION);
  const amount = result.data.amount;
  console.log(`  BSS/OCE amount: USD ${amount}`);
  console.log(`  Quotation target: USD 55.00`);
  console.log(`  Ratio: ${(amount / 55.0).toFixed(4)}`);
  assert(amount > 0, "amount > 0");
  assert(Math.abs(amount - 109.5) < 1.0, `amount ≈ 109.50 (got ${amount})`);
} else {
  skip("T7", "RUN_LIVE_API not set");
}

console.log("\n=== T8: EstimateTemplateOnDemandPrice c6.3xlarge.4.linux (live) ===");
if (RUN_LIVE) {
  const rendered = renderProductInfosFromTemplate({
    service: "ecs",
    template_id: "ecs-flavor-payg",
    region: REGION,
    parameters: { ecs_resource_spec: "c6.3xlarge.4.linux" }
  });
  const result = await queryOnDemandPrice(rendered.product_infos, REGION);
  const amount = result.data.amount;
  console.log(`  BSS/OCE amount: USD ${amount}`);
  console.log(`  Quotation target: USD 271.21`);
  console.log(`  Ratio: ${(amount / 271.21).toFixed(4)}`);
  assert(amount > 0, "amount > 0");
  assert(Math.abs(amount - 376.68) < 1.0, `amount ≈ 376.68 (got ${amount})`);
} else {
  skip("T8", "RUN_LIVE_API not set");
}

console.log("\n=== T9: EstimateTemplateOnDemandPrice s6.xlarge.4.linux (live) ===");
if (RUN_LIVE) {
  const rendered = renderProductInfosFromTemplate({
    service: "ecs",
    template_id: "ecs-flavor-payg",
    region: REGION
  });
  const result = await queryOnDemandPrice(rendered.product_infos, REGION);
  const amount = result.data.amount;
  console.log(`  BSS/OCE amount: USD ${amount}`);
  console.log(`  Quotation target: USD 63.07`);
  console.log(`  Ratio: ${(amount / 63.07).toFixed(4)}`);
  assert(amount > 0, "amount > 0");
  assert(Math.abs(amount - 87.60) < 1.0, `amount ≈ 87.60 (got ${amount})`);
} else {
  skip("T9", "RUN_LIVE_API not set");
}

console.log("\n=== T10: Architecture pricing BD line (m6 + SUSE + GPSSD 700GB) (live) ===");
if (RUN_LIVE) {
  const m6Rendered = renderProductInfosFromTemplate({
    service: "ecs",
    template_id: "ecs-flavor-payg",
    region: REGION,
    parameters: { ecs_resource_spec: "m6.3xlarge.8.linux" }
  });
  const suseRendered = renderProductInfosFromTemplate({
    service: "ecs",
    template_id: "ecs-os-license-payg",
    region: REGION
  });
  const gpssdRendered = renderProductInfosFromTemplate({
    service: "evs",
    template_id: "evs-gpssd-gb-payg",
    region: REGION,
    parameters: { size_gb: 700 }
  });

  const allProductInfos = [
    ...m6Rendered.product_infos,
    ...suseRendered.product_infos,
    ...gpssdRendered.product_infos
  ];

  const result = await queryOnDemandPrice(allProductInfos, REGION);
  const total = result.data.amount;
  const bssExpected = 494.94 + 109.50 + 66.43;
  const quoteExpected = 477.16;
  console.log(`  BSS/OCE total: USD ${total.toFixed(2)}`);
  console.log(`  BSS/OCE expected (compute + SUSE + GPSSD): USD ${bssExpected.toFixed(2)}`);
  console.log(`  Quotation BD line: USD ${quoteExpected.toFixed(2)}`);
  console.log(`  BSS vs Quote ratio: ${(total / quoteExpected).toFixed(4)}`);
  assert(Math.abs(total - bssExpected) < 2.0, `total ≈ ${bssExpected.toFixed(2)} (got ${total.toFixed(2)})`);
} else {
  skip("T10", "RUN_LIVE_API not set");
}

console.log("\n=== T11: Architecture pricing for three ECS benchmark lines (live) ===");
if (RUN_LIVE) {
  const m6Rendered = renderProductInfosFromTemplate({
    service: "ecs", template_id: "ecs-flavor-payg", region: REGION,
    parameters: { ecs_resource_spec: "m6.3xlarge.8.linux" }
  });
  const suseRendered = renderProductInfosFromTemplate({
    service: "ecs", template_id: "ecs-os-license-payg", region: REGION
  });
  const gpssd700Rendered = renderProductInfosFromTemplate({
    service: "evs", template_id: "evs-gpssd-gb-payg", region: REGION,
    parameters: { size_gb: 700 }
  });
  const c6Rendered = renderProductInfosFromTemplate({
    service: "ecs", template_id: "ecs-flavor-payg", region: REGION,
    parameters: { ecs_resource_spec: "c6.3xlarge.4.linux" }
  });
  const gpssd300Rendered = renderProductInfosFromTemplate({
    service: "evs", template_id: "evs-gpssd-gb-payg", region: REGION,
    parameters: { size_gb: 300 }
  });
  const s6Rendered = renderProductInfosFromTemplate({
    service: "ecs", template_id: "ecs-flavor-payg", region: REGION,
    parameters: { ecs_resource_spec: "s6.xlarge.4.linux" }
  });
  const gpssd200Rendered = renderProductInfosFromTemplate({
    service: "evs", template_id: "evs-gpssd-gb-payg", region: REGION,
    parameters: { size_gb: 200 }
  });

  const allProductInfos = [
    ...m6Rendered.product_infos,
    ...suseRendered.product_infos,
    ...gpssd700Rendered.product_infos,
    ...c6Rendered.product_infos,
    ...gpssd300Rendered.product_infos,
    ...s6Rendered.product_infos,
    ...gpssd200Rendered.product_infos
  ];

  const result = await queryOnDemandPrice(allProductInfos, REGION);
  const total = result.data.amount;
  const bssExpected = 494.94 + 109.50 + 66.43 + 376.68 + 28.47 + 87.60 + 18.98;
  const quoteExpected = 477.16 + 299.41 + 81.87;
  console.log(`  BSS/OCE total: USD ${total.toFixed(2)}`);
  console.log(`  BSS/OCE expected sum: USD ${bssExpected.toFixed(2)}`);
  console.log(`  Quotation total (3 lines): USD ${quoteExpected.toFixed(2)}`);
  console.log(`  BSS vs Quote ratio: ${(total / quoteExpected).toFixed(4)}`);
  assert(Math.abs(total - bssExpected) < 3.0, `total ≈ ${bssExpected.toFixed(2)} (got ${total.toFixed(2)})`);
} else {
  skip("T11", "RUN_LIVE_API not set");
}

console.log("\n=== T12: Confirm no AlmaLinux license template ===");
{
  const result = listPricingTemplates({ service: "ecs" });
  const ids = result.templates.map(t => t.template_id);
  const hasAlmaLinux = ids.some(id => id.includes("almalinux") || id.includes("alma"));
  assert(!hasAlmaLinux, "No AlmaLinux license template exists");
  console.log("  AlmaLinux has no productInfo/cost in benchmark (free OS, no license template needed)");
}

console.log(`\n=== Summary: ${passed} passed, ${failed} failed, ${skipped} skipped ===`);
process.exit(failed > 0 ? 1 : 0);
