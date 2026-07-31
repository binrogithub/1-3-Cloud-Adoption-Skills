import { readFileSync } from "fs";
import { join } from "path";

const TEMPLATES_PATH = process.env.PRICING_TEMPLATES_PATH || join(process.env.HOME || "/root", ".config/maas-pricing/pricing-templates.json");

let passed = 0;
let failed = 0;

function assert(condition, message) {
  if (condition) {
    passed++;
    console.log(`  PASS: ${message}`);
  } else {
    failed++;
    console.log(`  FAIL: ${message}`);
  }
}

function loadTemplates() {
  const raw = readFileSync(TEMPLATES_PATH, "utf-8");
  return JSON.parse(raw);
}

function testNatTemplateExists() {
  console.log("\n--- Test NAT-1: nat-gateway-public-payg template exists ---");
  const templates = loadTemplates();
  const natRegion = templates.templates?.natgateway?.["la-north-2"];

  assert(natRegion !== undefined, "natgateway.la-north-2 section exists");
  assert(natRegion["nat-gateway-public-payg"] !== undefined, "nat-gateway-public-payg template exists");
}

function testNatTemplateFields() {
  console.log("\n--- Test NAT-2: nat-gateway-public-payg has Playwright-discovered fields ---");
  const templates = loadTemplates();
  const tpl = templates.templates.natgateway["la-north-2"]["nat-gateway-public-payg"];

  assert(tpl.service === "natgateway", "service = natgateway");
  assert(tpl.region === "la-north-2", "region = la-north-2");
  assert(tpl.billing_mode === "on_demand", "billing_mode = on_demand");
  assert(tpl.unit === "day", "unit = day (day-based, not hour-based)");
  assert(tpl.status === "ready", "status = ready");

  const pi = tpl.product_infos_template[0];
  assert(pi.cloud_service_type === "hws.service.type.natgateway", "cloud_service_type = hws.service.type.natgateway");
  assert(pi.resource_type === "hws.resource.type.natgateway", "resource_type = hws.resource.type.natgateway");
  assert(pi.resource_spec === "{{nat_resource_spec}}", "resource_spec is parametric");
  assert(pi.usage_factor === "duration", "usage_factor = duration");
  assert(pi.usage_measure_id === 0, "usage_measure_id = 0 (Day)");
}

function testNatDefaultParameters() {
  console.log("\n--- Test NAT-3: nat-gateway-public-payg default parameters match Playwright discovery ---");
  const templates = loadTemplates();
  const tpl = templates.templates.natgateway["la-north-2"]["nat-gateway-public-payg"];

  assert(tpl.parameters.nat_resource_spec.default === "natgateway_small", "default nat_resource_spec = natgateway_small");
  assert(tpl.parameters.usage_days.default === 30, "default usage_days = 30");
  assert(tpl.parameters.quantity.default === 1, "default quantity = 1");
}

function testNatRenderedProductInfo() {
  console.log("\n--- Test NAT-4: Rendered product_infos for nat-gateway-public-payg match Playwright discovery ---");
  const templates = loadTemplates();
  const tpl = templates.templates.natgateway["la-north-2"]["nat-gateway-public-payg"];
  const pi = tpl.product_infos_template[0];

  const region = "la-north-2";
  const nat_resource_spec = tpl.parameters.nat_resource_spec.default;
  const usage_days = tpl.parameters.usage_days.default;
  const quantity = tpl.parameters.quantity.default;

  const rendered = {};
  for (const [k, v] of Object.entries(pi)) {
    let val = v;
    if (typeof val === "string") {
      val = val.replace("{{nat_resource_spec}}", nat_resource_spec);
      val = val.replace("{{usage_days}}", String(usage_days));
      val = val.replace("{{quantity}}", String(quantity));
      val = val.replace("{{region}}", region);
    }
    rendered[k] = val;
  }

  assert(rendered.cloud_service_type === "hws.service.type.natgateway", "Rendered cloud_service_type = hws.service.type.natgateway");
  assert(rendered.resource_type === "hws.resource.type.natgateway", "Rendered resource_type = hws.resource.type.natgateway");
  assert(rendered.resource_spec === "natgateway_small", "Rendered resource_spec = natgateway_small");
  assert(rendered.usage_factor === "duration", "Rendered usage_factor = duration");
  assert(rendered.usage_measure_id === 0, "Rendered usage_measure_id = 0 (Day)");
  assert(rendered.usage_value === "30" || rendered.usage_value === 30, "Rendered usage_value = 30 (days)");
}

function testNatDayBasedNotHourBased() {
  console.log("\n--- Test NAT-5: NAT Gateway uses day-based billing, not hour-based ---");
  const templates = loadTemplates();
  const tpl = templates.templates.natgateway["la-north-2"]["nat-gateway-public-payg"];
  const pi = tpl.product_infos_template[0];

  assert(pi.usage_measure_id === 0, "usage_measure_id = 0 (Day, not 4 for Hour)");
  assert(tpl.parameters.usage_days !== undefined, "Has usage_days parameter (not monthly_hours)");
  assert(tpl.parameters.monthly_hours === undefined, "Does NOT have monthly_hours parameter");
}

function testNatNoSnatRulePaidModel() {
  console.log("\n--- Test NAT-6: NAT template does NOT model SNAT rule as paid resource ---");
  const templates = loadTemplates();
  const tpl = templates.templates.natgateway["la-north-2"]["nat-gateway-public-payg"];
  const piRaw = JSON.stringify(tpl.product_infos_template);

  assert(!piRaw.includes("snat"), "No snat in product_infos_template");
  assert(!piRaw.includes("SNAT"), "No SNAT in product_infos_template");
  assert(tpl.product_infos_template.length === 1, "Only one productInfo (instance only, no SNAT rule component)");
}

function testNatNotesDocumentValidation() {
  console.log("\n--- Test NAT-7: NAT template notes document validated pricing ---");
  const templates = loadTemplates();
  const tpl = templates.templates.natgateway["la-north-2"]["nat-gateway-public-payg"];

  assert(tpl.notes?.length > 0, "Template has notes");
  assert(tpl.notes.some(n => n.includes("73.14")), "Notes document natgateway_small x 30d = USD 73.14");
  assert(tpl.notes.some(n => n.includes("usage_measure_id=0")), "Notes document usage_measure_id=0");
}

function testNatComposableWithEip() {
  console.log("\n--- Test NAT-8: NAT Gateway is independently composable (no hardcoded EIP) ---");
  const templates = loadTemplates();
  const tpl = templates.templates.natgateway["la-north-2"]["nat-gateway-public-payg"];
  const piRaw = JSON.stringify(tpl.product_infos_template);

  assert(!piRaw.includes("hws.service.type.vpc"), "No VPC/EIP service type in product_infos_template");
  assert(!piRaw.includes("bandwidth"), "No bandwidth in product_infos_template");
  assert(tpl.notes.some(n => n.includes("EIP") || n.includes("eip-bandwidth")), "Notes mention EIP must be priced separately");
}

function testNatPriceExpectation() {
  console.log("\n--- Test NAT-9: NAT Gateway small 30d ≈ USD 73.14 documented ---");
  const templates = loadTemplates();
  const tpl = templates.templates.natgateway["la-north-2"]["nat-gateway-public-payg"];

  assert(tpl.notes.some(n => n.includes("73.14")), "Notes document USD 73.14 for small 30d");
}

function testNatOtherSpecsDocumented() {
  console.log("\n--- Test NAT-10: NAT Gateway other specs documented in notes ---");
  const templates = loadTemplates();
  const tpl = templates.templates.natgateway["la-north-2"]["nat-gateway-public-payg"];

  assert(tpl.notes.some(n => n.includes("natgateway_middle")), "Notes mention natgateway_middle");
  assert(tpl.notes.some(n => n.includes("natgateway_large")), "Notes mention natgateway_large");
  assert(tpl.notes.some(n => n.includes("natgateway_xlarge")), "Notes mention natgateway_xlarge");
}

async function main() {
  console.log("=== NAT Gateway Public Template Tests ===");

  testNatTemplateExists();
  testNatTemplateFields();
  testNatDefaultParameters();
  testNatRenderedProductInfo();
  testNatDayBasedNotHourBased();
  testNatNoSnatRulePaidModel();
  testNatNotesDocumentValidation();
  testNatComposableWithEip();
  testNatPriceExpectation();
  testNatOtherSpecsDocumented();

  console.log(`\n=== Results: ${passed} passed, ${failed} failed ===`);
  process.exit(failed > 0 ? 1 : 0);
}

main();
