import { validateArchitecture } from "../architecture-validator.mjs";
import { generateTerraform } from "../terraform-generator.mjs";

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

function testUnsupportedServiceReturnsUnsupported() {
  console.log("\n--- Test: Unsupported service returns UNSUPPORTED status ---");
  const result = validateArchitecture({
    architecture_id: "test",
    region: "la-north-2",
    deployment_mode: "terraform",
    components: [
      { service: "vpc", name: "vpc", cidr: "10.0.0.0/16" },
      { service: "cce_cluster", name: "my-cluster" }
    ]
  });

  const cceStatus = result.componentStatus.find(c => c.service === "cce_cluster");
  assert(cceStatus !== undefined, "cce_cluster has a component status");
  assert(cceStatus?.status === "UNSUPPORTED", "cce_cluster is UNSUPPORTED");
}

function testRdsMysqlReturnsReady() {
  console.log("\n--- Test: RDS MySQL returns READY status (phase 2) ---");
  const result = validateArchitecture({
    architecture_id: "test",
    region: "la-north-2",
    deployment_mode: "terraform",
    components: [
      { service: "vpc", name: "vpc", cidr: "10.0.0.0/16" },
      { service: "rds_mysql", name: "mydb", flavor: "rds.mysql.n1.large.2", storage_type: "CLOUDSSD", storage_gb: 100 }
    ]
  });

  const rdsStatus = result.componentStatus.find(c => c.service === "rds_mysql");
  assert(rdsStatus !== undefined, "rds_mysql has a component status");
  assert(rdsStatus?.status === "READY", "rds_mysql is READY (phase 2)");
}

function testObsReturnsReady() {
  console.log("\n--- Test: OBS returns READY status (phase 2) ---");
  const result = validateArchitecture({
    architecture_id: "test",
    region: "la-north-2",
    deployment_mode: "terraform",
    components: [
      { service: "vpc", name: "vpc", cidr: "10.0.0.0/16" },
      { service: "obs", name: "mybucket" }
    ]
  });

  const obsStatus = result.componentStatus.find(c => c.service === "obs");
  assert(obsStatus?.status === "READY", "obs is READY (phase 2)");
}

function testElbBackendAttachmentReturnsReady() {
  console.log("\n--- Test: elb_backend_attachment returns READY status (phase 2) ---");
  const result = validateArchitecture({
    architecture_id: "test",
    region: "la-north-2",
    deployment_mode: "terraform",
    components: [
      { service: "vpc", name: "vpc", cidr: "10.0.0.0/16" },
      { service: "elb_backend_attachment", name: "elb-backend", elb_name: "public-elb" }
    ]
  });

  const elbBackendStatus = result.componentStatus.find(c => c.service === "elb_backend_attachment");
  assert(elbBackendStatus?.status === "READY", "elb_backend_attachment is READY (phase 2)");
}

function testPhase2GeneratesRealResources() {
  console.log("\n--- Test: Phase 2 services generate real Terraform resources ---");
  const files = generateTerraform({
    architecture_id: "test",
    region: "la-north-2",
    deployment_mode: "terraform",
    components: [
      { service: "vpc", name: "vpc", cidr: "10.0.0.0/16" },
      { service: "subnet", name: "sub", cidr: "10.0.1.0/24" },
      { service: "security_group", name: "sg" },
      { service: "rds_mysql", name: "mydb", flavor: "rds.mysql.n1.large.2", storage_type: "CLOUDSSD", storage_gb: 100 },
      { service: "obs", name: "mybucket" }
    ]
  });

  const mainTf = files["main.tf"];
  assert(mainTf.includes('resource "huaweicloud_rds_instance"'), "RDS resource is generated (not placeholder)");
  assert(mainTf.includes('resource "huaweicloud_obs_bucket"'), "OBS resource is generated (not placeholder)");
  assert(!mainTf.includes("PLACEHOLDER"), "No PLACEHOLDER comments for phase 2 services");
}

function testUnsupportedServiceSkippedInMainTf() {
  console.log("\n--- Test: Unsupported service generates UNSUPPORTED comment ---");
  const files = generateTerraform({
    architecture_id: "test",
    region: "la-north-2",
    deployment_mode: "terraform",
    components: [
      { service: "vpc", name: "vpc", cidr: "10.0.0.0/16" },
      { service: "cce_cluster", name: "my-cluster" }
    ]
  });

  const mainTf = files["main.tf"];
  assert(mainTf.includes("UNSUPPORTED"), "main.tf contains UNSUPPORTED comment");
  assert(mainTf.includes("cce_cluster"), "Unsupported service name is mentioned");
}

async function main() {
  console.log("=== Unsupported Components Tests ===");

  testUnsupportedServiceReturnsUnsupported();
  testRdsMysqlReturnsReady();
  testObsReturnsReady();
  testElbBackendAttachmentReturnsReady();
  testPhase2GeneratesRealResources();
  testUnsupportedServiceSkippedInMainTf();

  console.log(`\n=== Results: ${passed} passed, ${failed} failed ===`);
  process.exit(failed > 0 ? 1 : 0);
}

main();
