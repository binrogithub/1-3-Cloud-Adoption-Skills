import { validateArchitecture } from "../architecture-validator.mjs";

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

function testRejectsMissingFields() {
  console.log("\n--- Test: Rejects architecture with missing fields ---");
  const result = validateArchitecture({});
  assert(!result.valid, "Empty object is invalid");
  assert(result.errors.some(e => e.includes("architecture_id")), "Error for missing architecture_id");
  assert(result.errors.some(e => e.includes("region")), "Error for missing region");
  assert(result.errors.some(e => e.includes("deployment_mode")), "Error for missing deployment_mode");
  assert(result.errors.some(e => e.includes("components")), "Error for missing components");
}

function testRejectsInvalidDeploymentMode() {
  console.log("\n--- Test: Rejects invalid deployment_mode ---");
  const result = validateArchitecture({
    architecture_id: "test",
    region: "la-north-2",
    deployment_mode: "pulumi",
    components: [{ service: "vpc", name: "vpc", cidr: "10.0.0.0/16" }]
  });
  assert(!result.valid, "Pulumi deployment_mode is rejected");
  assert(result.errors.some(e => e.includes("deployment_mode")), "Error mentions deployment_mode");
}

function testRejectsEmptyComponents() {
  console.log("\n--- Test: Rejects empty components array ---");
  const result = validateArchitecture({
    architecture_id: "test",
    region: "la-north-2",
    deployment_mode: "terraform",
    components: []
  });
  assert(!result.valid, "Empty components is invalid");
}

function testRejectsComponentMissingService() {
  console.log("\n--- Test: Rejects component without service field ---");
  const result = validateArchitecture({
    architecture_id: "test",
    region: "la-north-2",
    deployment_mode: "terraform",
    components: [{ name: "foo" }]
  });
  assert(!result.valid, "Component without service is rejected");
}

function testRejectsDuplicateNames() {
  console.log("\n--- Test: Rejects duplicate component names ---");
  const result = validateArchitecture({
    architecture_id: "test",
    region: "la-north-2",
    deployment_mode: "terraform",
    components: [
      { service: "vpc", name: "dup", cidr: "10.0.0.0/16" },
      { service: "subnet", name: "dup", cidr: "10.0.1.0/24" }
    ]
  });
  assert(!result.valid, "Duplicate names rejected");
  assert(result.errors.some(e => e.includes("Duplicate")), "Error mentions duplicate");
}

function testRejectsEcsMissingFlavor() {
  console.log("\n--- Test: Rejects ECS missing required flavor ---");
  const result = validateArchitecture({
    architecture_id: "test",
    region: "la-north-2",
    deployment_mode: "terraform",
    components: [
      { service: "vpc", name: "vpc", cidr: "10.0.0.0/16" },
      { service: "ecs", name: "myecs", image_name: "Ubuntu", system_disk_type: "GPSSD", system_disk_size_gb: 40 }
    ]
  });
  assert(!result.valid, "ECS without flavor is rejected");
}

function testWarnsNoVpc() {
  console.log("\n--- Test: Warns when no VPC defined ---");
  const result = validateArchitecture({
    architecture_id: "test",
    region: "la-north-2",
    deployment_mode: "terraform",
    components: [
      { service: "ecs", name: "myecs", flavor: "s6.large.2", image_name: "Ubuntu", system_disk_type: "GPSSD", system_disk_size_gb: 40 }
    ]
  });
  assert(result.warnings.some(w => w.includes("VPC")), "Warning about missing VPC");
}

function testAcceptsValidMinimalArchitecture() {
  console.log("\n--- Test: Accepts valid minimal architecture ---");
  const result = validateArchitecture({
    architecture_id: "test",
    region: "la-north-2",
    deployment_mode: "terraform",
    components: [
      { service: "vpc", name: "vpc", cidr: "10.0.0.0/16" },
      { service: "subnet", name: "sub", cidr: "10.0.1.0/24" },
      { service: "security_group", name: "sg" },
      { service: "ecs", name: "ecs1", flavor: "s6.large.2", image_name: "Ubuntu 24.04", system_disk_type: "GPSSD", system_disk_size_gb: 40 },
      { service: "eip", name: "eip1" }
    ]
  });
  assert(result.valid, "Valid minimal architecture passes");
  assert(result.errors.length === 0, "No errors");
}

async function main() {
  console.log("=== Validation Tests ===");

  testRejectsMissingFields();
  testRejectsInvalidDeploymentMode();
  testRejectsEmptyComponents();
  testRejectsComponentMissingService();
  testRejectsDuplicateNames();
  testRejectsEcsMissingFlavor();
  testWarnsNoVpc();
  testAcceptsValidMinimalArchitecture();

  console.log(`\n=== Results: ${passed} passed, ${failed} failed ===`);
  process.exit(failed > 0 ? 1 : 0);
}

main();
