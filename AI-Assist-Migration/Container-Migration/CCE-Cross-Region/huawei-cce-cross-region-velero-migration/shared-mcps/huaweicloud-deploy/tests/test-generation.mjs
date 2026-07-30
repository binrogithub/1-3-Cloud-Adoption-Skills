import { generateTerraform } from "../terraform-generator.mjs";
import { validateArchitecture } from "../architecture-validator.mjs";
import { writeFile, readFile, mkdir, rm } from "node:fs/promises";
import { join } from "node:path";
import { existsSync } from "node:fs";

const TEST_WORKDIR = "/tmp/deploy-mcp-test-generation";
const SAMPLE_ARCH = {
  architecture_id: "small-web-app-demo",
  region: "la-north-2",
  deployment_mode: "terraform",
  components: [
    { service: "vpc", name: "demo-vpc", cidr: "192.168.0.0/16" },
    { service: "subnet", name: "demo-subnet", cidr: "192.168.1.0/24", gateway_ip: "192.168.1.1" },
    {
      service: "security_group", name: "demo-sg",
      rules: [
        { direction: "ingress", protocol: "tcp", port: 80, remote_ip_prefix: "0.0.0.0/0" },
        { direction: "ingress", protocol: "tcp", port: 22, remote_ip_prefix: "CUSTOM_ADMIN_CIDR_REQUIRED" }
      ]
    },
    { service: "ecs", name: "app", quantity: 2, flavor: "s6.large.2", image_name: "Ubuntu 24.04", system_disk_type: "GPSSD", system_disk_size_gb: 40 },
    { service: "elb", name: "public-elb", type: "shared", listener_port: 80, backend_port: 80 },
    { service: "eip", name: "public-eip", bandwidth_mbps: 10 }
  ]
};

const REQUIRED_FILES = ["versions.tf", "providers.tf", "variables.tf", "main.tf", "outputs.tf", "terraform.tfvars.example"];

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

async function testGenerationProducesExpectedFiles() {
  console.log("\n--- Test: Generation produces expected files ---");
  const files = generateTerraform(SAMPLE_ARCH);

  for (const required of REQUIRED_FILES) {
    assert(files[required] !== undefined, `File "${required}" is generated`);
    assert(files[required].length > 0, `File "${required}" is not empty`);
  }

  assert(Object.keys(files).length === REQUIRED_FILES.length, `Exactly ${REQUIRED_FILES.length} files generated`);
}

async function testValidationAcceptsValidArchitecture() {
  console.log("\n--- Test: Validation accepts valid architecture ---");
  const result = validateArchitecture(SAMPLE_ARCH);
  assert(result.valid === true, "Valid architecture passes validation");
  assert(result.errors.length === 0, "No errors for valid architecture");
}

async function testGeneratedMainTfContainsAllResources() {
  console.log("\n--- Test: main.tf contains all expected resources ---");
  const files = generateTerraform(SAMPLE_ARCH);
  const mainTf = files["main.tf"];

  assert(mainTf.includes('resource "huaweicloud_vpc"'), "Contains VPC resource");
  assert(mainTf.includes('resource "huaweicloud_vpc_subnet"'), "Contains subnet resource");
  assert(mainTf.includes('resource "huaweicloud_networking_secgroup"'), "Contains security group resource");
  assert(mainTf.includes('resource "huaweicloud_compute_instance"'), "Contains ECS resource");
  assert(mainTf.includes('resource "huaweicloud_elb_loadbalancer"'), "Contains ELB resource");
  assert(mainTf.includes('resource "huaweicloud_vpc_eip"'), "Contains EIP resource");
}

async function testEcsQuantityGeneratesMultipleInstances() {
  console.log("\n--- Test: ECS quantity=2 generates two instances ---");
  const files = generateTerraform(SAMPLE_ARCH);
  const mainTf = files["main.tf"];

  assert(mainTf.includes('"app-1"'), "Contains app-1 instance");
  assert(mainTf.includes('"app-2"'), "Contains app-2 instance");
}

async function testOutputsTfContainsExpectedOutputs() {
  console.log("\n--- Test: outputs.tf contains expected outputs ---");
  const files = generateTerraform(SAMPLE_ARCH);
  const outputsTf = files["outputs.tf"];

  assert(outputsTf.includes("vpc_id"), "Contains vpc_id output");
  assert(outputsTf.includes("subnet_id"), "Contains subnet_id output");
  assert(outputsTf.includes("ecs_app_1_id"), "Contains ecs_app_1_id output");
  assert(outputsTf.includes("ecs_app_2_id"), "Contains ecs_app_2_id output");
  assert(outputsTf.includes("eip_public_eip_address"), "Contains EIP address output");
  assert(outputsTf.includes("elb_public_elb_id"), "Contains ELB ID output");
}

async function testVersionsTfHasCorrectProvider() {
  console.log("\n--- Test: versions.tf has correct provider ---");
  const files = generateTerraform(SAMPLE_ARCH);
  const versionsTf = files["versions.tf"];

  assert(versionsTf.includes("huaweicloud/huaweicloud"), "Contains correct provider source");
  assert(versionsTf.includes(">= 1.5.0"), "Contains terraform version constraint");
}

async function testProvidersTfNoHardcodedCredentials() {
  console.log("\n--- Test: providers.tf has no hardcoded credentials ---");
  const files = generateTerraform(SAMPLE_ARCH);
  const providersTf = files["providers.tf"];

  assert(!providersTf.includes("access_key"), "No access_key in providers.tf");
  assert(!providersTf.includes("secret_key"), "No secret_key in providers.tf");
  assert(providersTf.includes("region = var.region"), "Uses variable for region");
}

async function testTfvarsExampleNoSecrets() {
  console.log("\n--- Test: terraform.tfvars.example has no secrets ---");
  const files = generateTerraform(SAMPLE_ARCH);
  const tfvars = files["terraform.tfvars.example"];

  const uncommentedLines = tfvars.split("\n").filter(l => l.trim() && !l.trim().startsWith("#"));
  assert(!uncommentedLines.some(l => l.includes("password")), "No uncommented password line in tfvars.example");
  assert(tfvars.includes("REPLACE_WITH_STRONG_PASSWORD") || tfvars.includes("TF_VAR_ecs_admin_password"), "Password is placeholder or env var reference");
}

async function testWriteAndReadFiles() {
  console.log("\n--- Test: Write files to disk and read back ---");
  const files = generateTerraform(SAMPLE_ARCH);
  await mkdir(TEST_WORKDIR, { recursive: true });

  for (const [filename, content] of Object.entries(files)) {
    await writeFile(join(TEST_WORKDIR, filename), content, "utf-8");
  }

  const mainTf = await readFile(join(TEST_WORKDIR, "main.tf"), "utf-8");
  assert(mainTf.includes("huaweicloud_vpc"), "Written main.tf is readable and correct");

  await rm(TEST_WORKDIR, { recursive: true, force: true });
}

async function main() {
  console.log("=== Generation Tests ===");

  await testGenerationProducesExpectedFiles();
  await testValidationAcceptsValidArchitecture();
  await testGeneratedMainTfContainsAllResources();
  await testEcsQuantityGeneratesMultipleInstances();
  await testOutputsTfContainsExpectedOutputs();
  await testVersionsTfHasCorrectProvider();
  await testProvidersTfNoHardcodedCredentials();
  await testTfvarsExampleNoSecrets();
  await testWriteAndReadFiles();

  console.log(`\n=== Results: ${passed} passed, ${failed} failed ===`);
  process.exit(failed > 0 ? 1 : 0);
}

main();
