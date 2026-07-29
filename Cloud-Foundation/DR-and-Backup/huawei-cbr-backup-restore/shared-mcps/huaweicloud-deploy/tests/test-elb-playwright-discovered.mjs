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

function assertApprox(actual, expected, tolerance, message) {
  const diff = Math.abs(actual - expected);
  const ok = diff <= tolerance;
  if (ok) {
    passed++;
    console.log(`  PASS: ${message} (actual=${actual.toFixed(2)}, expected=${expected.toFixed(2)}, diff=${diff.toFixed(4)})`);
  } else {
    failed++;
    console.log(`  FAIL: ${message} (actual=${actual.toFixed(2)}, expected=${expected.toFixed(2)}, diff=${diff.toFixed(4)}, tol=${tolerance})`);
  }
}

function loadTemplates() {
  const raw = readFileSync(TEMPLATES_PATH, "utf-8");
  return JSON.parse(raw);
}

function testElbTemplatesExist() {
  console.log("\n--- Test ELB-1: ELB templates exist in pricing-templates.json ---");
  const templates = loadTemplates();
  const elbRegion = templates.templates?.elb?.["la-north-2"];

  assert(elbRegion !== undefined, "elb.la-north-2 section exists");
  assert(elbRegion["elb-shared-instance-payg"] !== undefined, "elb-shared-instance-payg template exists");
  assert(elbRegion["elb-shared-lcu-payg"] !== undefined, "elb-shared-lcu-payg template exists");
}

function testElbInstanceTemplateFields() {
  console.log("\n--- Test ELB-2: elb-shared-instance-payg has Playwright-discovered fields ---");
  const templates = loadTemplates();
  const tpl = templates.templates.elb["la-north-2"]["elb-shared-instance-payg"];

  assert(tpl.service === "elb", "service = elb");
  assert(tpl.region === "la-north-2", "region = la-north-2");
  assert(tpl.billing_mode === "on_demand", "billing_mode = on_demand");
  assert(tpl.status === "ready", "status = ready");

  const pi = tpl.product_infos_template[0];
  assert(pi.cloud_service_type === "hws.service.type.elb", "cloud_service_type = hws.service.type.elb");
  assert(pi.resource_type === "hws.resource.type.elbv3", "resource_type = hws.resource.type.elbv3 (was elbv2)");
  assert(pi.resource_spec === "{{resource_spec}}", "resource_spec is parametric");
  assert(pi.usage_factor === "instance_duration", "usage_factor = instance_duration (was duration)");
  assert(pi.usage_measure_id === 4, "usage_measure_id = 4 (Hour)");
}

function testElbInstanceDefaultResourceSpec() {
  console.log("\n--- Test ELB-3: elb-shared-instance-payg default resource_spec is elbv3.professional ---");
  const templates = loadTemplates();
  const tpl = templates.templates.elb["la-north-2"]["elb-shared-instance-payg"];

  assert(tpl.parameters.resource_spec.default === "elbv3.professional", "default resource_spec = elbv3.professional (was 21_instance)");
}

function testElbInstanceNoElbv2() {
  console.log("\n--- Test ELB-4: elb-shared-instance-payg product_infos do NOT use elbv2 or 21_instance ---");
  const templates = loadTemplates();
  const tpl = templates.templates.elb["la-north-2"]["elb-shared-instance-payg"];
  const piRaw = JSON.stringify(tpl.product_infos_template);

  assert(!piRaw.includes("elbv2"), "No elbv2 in product_infos_template");
  assert(!piRaw.includes("21_instance"), "No 21_instance in product_infos_template");
  assert(tpl.parameters.resource_spec.default !== "21_instance", "Default resource_spec is not 21_instance");
}

function testElbLcuTemplateFields() {
  console.log("\n--- Test ELB-5: elb-shared-lcu-payg has correct LCU fields ---");
  const templates = loadTemplates();
  const tpl = templates.templates.elb["la-north-2"]["elb-shared-lcu-payg"];

  assert(tpl.service === "elb", "service = elb");
  assert(tpl.region === "la-north-2", "region = la-north-2");
  assert(tpl.billing_mode === "on_demand", "billing_mode = on_demand");
  assert(tpl.status === "ready", "status = ready");

  const pi = tpl.product_infos_template[0];
  assert(pi.cloud_service_type === "hws.service.type.elb", "cloud_service_type = hws.service.type.elb");
  assert(pi.resource_type === "hws.resource.type.elbv3", "resource_type = hws.resource.type.elbv3");
  assert(pi.resource_spec === "{{resource_spec}}", "resource_spec is parametric");
  assert(pi.usage_factor === "l4_lcu_duration", "usage_factor = l4_lcu_duration");
  assert(pi.usage_measure_id === 4, "usage_measure_id = 4 (Hour)");
}

function testElbLcuDefaultResourceSpec() {
  console.log("\n--- Test ELB-6: elb-shared-lcu-payg default resource_spec is elbv3.professional ---");
  const templates = loadTemplates();
  const tpl = templates.templates.elb["la-north-2"]["elb-shared-lcu-payg"];

  assert(tpl.parameters.resource_spec.default === "elbv3.professional", "default resource_spec = elbv3.professional");
}

function testElbInstanceRenderedProductInfo() {
  console.log("\n--- Test ELB-7: Rendered product_infos for elb-shared-instance-payg match Playwright discovery ---");
  const templates = loadTemplates();
  const tpl = templates.templates.elb["la-north-2"]["elb-shared-instance-payg"];
  const pi = tpl.product_infos_template[0];

  const region = "la-north-2";
  const resource_spec = tpl.parameters.resource_spec.default;
  const monthly_hours = tpl.parameters.monthly_hours.default;
  const quantity = tpl.parameters.quantity.default;

  const rendered = {};
  for (const [k, v] of Object.entries(pi)) {
    let val = v;
    if (typeof val === "string") {
      val = val.replace("{{resource_spec}}", resource_spec);
      val = val.replace("{{monthly_hours}}", String(monthly_hours));
      val = val.replace("{{quantity}}", String(quantity));
      val = val.replace("{{region}}", region);
    }
    rendered[k] = val;
  }

  assert(rendered.cloud_service_type === "hws.service.type.elb", "Rendered cloud_service_type = hws.service.type.elb");
  assert(rendered.resource_type === "hws.resource.type.elbv3", "Rendered resource_type = hws.resource.type.elbv3");
  assert(rendered.resource_spec === "elbv3.professional", "Rendered resource_spec = elbv3.professional");
  assert(rendered.usage_factor === "instance_duration", "Rendered usage_factor = instance_duration");
  assert(rendered.usage_value === "730" || rendered.usage_value === 730, "Rendered usage_value = 730");
  assert(rendered.usage_measure_id === 4, "Rendered usage_measure_id = 4");
}

function testElbLcuRenderedProductInfo() {
  console.log("\n--- Test ELB-8: Rendered product_infos for elb-shared-lcu-payg match Playwright discovery ---");
  const templates = loadTemplates();
  const tpl = templates.templates.elb["la-north-2"]["elb-shared-lcu-payg"];
  const pi = tpl.product_infos_template[0];

  const region = "la-north-2";
  const resource_spec = tpl.parameters.resource_spec.default;
  const monthly_hours = tpl.parameters.monthly_hours.default;
  const quantity = tpl.parameters.quantity.default;

  const rendered = {};
  for (const [k, v] of Object.entries(pi)) {
    let val = v;
    if (typeof val === "string") {
      val = val.replace("{{resource_spec}}", resource_spec);
      val = val.replace("{{monthly_hours}}", String(monthly_hours));
      val = val.replace("{{quantity}}", String(quantity));
      val = val.replace("{{region}}", region);
    }
    rendered[k] = val;
  }

  assert(rendered.cloud_service_type === "hws.service.type.elb", "Rendered cloud_service_type = hws.service.type.elb");
  assert(rendered.resource_type === "hws.resource.type.elbv3", "Rendered resource_type = hws.resource.type.elbv3");
  assert(rendered.resource_spec === "elbv3.professional", "Rendered resource_spec = elbv3.professional");
  assert(rendered.usage_factor === "l4_lcu_duration", "Rendered usage_factor = l4_lcu_duration");
  assert(rendered.usage_value === "730" || rendered.usage_value === 730, "Rendered usage_value = 730");
  assert(rendered.usage_measure_id === 4, "Rendered usage_measure_id = 4");
}

function testElbNotesDocumentPlaywrightDiscovery() {
  console.log("\n--- Test ELB-9: ELB templates document Playwright discovery ---");
  const templates = loadTemplates();
  const instanceTpl = templates.templates.elb["la-north-2"]["elb-shared-instance-payg"];
  const lcuTpl = templates.templates.elb["la-north-2"]["elb-shared-lcu-payg"];

  assert(instanceTpl.notes?.length > 0, "Instance template has notes");
  assert(instanceTpl.notes.some(n => n.includes("Playwright-discovered")), "Instance notes mention Playwright-discovered");
  assert(instanceTpl.notes.some(n => n.includes("elbv3")), "Instance notes mention elbv3");
  assert(instanceTpl.notes.some(n => n.includes("instance_duration")), "Instance notes mention instance_duration");

  assert(lcuTpl.notes?.length > 0, "LCU template has notes");
  assert(lcuTpl.notes.some(n => n.includes("Playwright-discovered")), "LCU notes mention Playwright-discovered");
  assert(lcuTpl.notes.some(n => n.includes("l4_lcu_duration")), "LCU notes mention l4_lcu_duration");
}

function testElbNoEipReservationInNotes() {
  console.log("\n--- Test ELB-10: ELB instance notes warn against EIP reservation inclusion ---");
  const templates = loadTemplates();
  const tpl = templates.templates.elb["la-north-2"]["elb-shared-instance-payg"];

  assert(tpl.notes.some(n => n.includes("reservation") || n.includes("EIP reservation")), "Notes mention EIP reservation should not be included");
}

function testElbTotalPriceExpectation() {
  console.log("\n--- Test ELB-11: ELB total price expectation documented (instance + LCU ≈ USD 24.33) ---");
  const templates = loadTemplates();
  const instanceTpl = templates.templates.elb["la-north-2"]["elb-shared-instance-payg"];
  const lcuTpl = templates.templates.elb["la-north-2"]["elb-shared-lcu-payg"];

  assert(instanceTpl.notes.some(n => n.includes("24.33")), "Instance notes document total ELB ≈ USD 24.33");
  assert(lcuTpl.notes.some(n => n.includes("24.33")), "LCU notes document total ELB ≈ USD 24.33");
}

async function main() {
  console.log("=== ELB Playwright-Discovered Template Tests ===");

  testElbTemplatesExist();
  testElbInstanceTemplateFields();
  testElbInstanceDefaultResourceSpec();
  testElbInstanceNoElbv2();
  testElbLcuTemplateFields();
  testElbLcuDefaultResourceSpec();
  testElbInstanceRenderedProductInfo();
  testElbLcuRenderedProductInfo();
  testElbNotesDocumentPlaywrightDiscovery();
  testElbNoEipReservationInNotes();
  testElbTotalPriceExpectation();

  console.log(`\n=== Results: ${passed} passed, ${failed} failed ===`);
  process.exit(failed > 0 ? 1 : 0);
}

main();
