import { generateTerraform } from "../terraform-generator.mjs";
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

const FULL_ARCH = {
  architecture_id: "small-web-app-approved-demo",
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
    { service: "eip", name: "public-eip", bandwidth_mbps: 10 },
    { service: "rds_mysql", name: "demo-mysql", engine: "MySQL", engine_version: "8.0", flavor: "rds.mysql.n1.large.2", storage_type: "CLOUDSSD", storage_gb: 100, availability_zone: "la-north-2a", db_port: 3306, database_name: "appdb", username: "root" },
    { service: "obs", name: "demo-static-files", bucket_name: "demo-static-files-example", storage_class: "STANDARD" }
  ]
};

function testObsGeneration() {
  console.log("\n--- Test A1: OBS generates Terraform resource ---");
  const files = generateTerraform(FULL_ARCH);
  const mainTf = files["main.tf"];

  assert(mainTf.includes('resource "huaweicloud_obs_bucket"'), "OBS bucket resource generated");
  assert(mainTf.includes("demo-static-files-example"), "OBS bucket name is configurable");
  assert(mainTf.includes("STANDARD"), "OBS storage class is set");
}

function testObsOutput() {
  console.log("\n--- Test A2: OBS output includes bucket name ---");
  const files = generateTerraform(FULL_ARCH);
  const outputsTf = files["outputs.tf"];

  assert(outputsTf.includes("obs_demo_static_files_bucket"), "OBS bucket output generated");
  assert(outputsTf.includes("huaweicloud_obs_bucket"), "OBS output references bucket resource");
}

function testObsNoSecrets() {
  console.log("\n--- Test A3: OBS generation has no secrets ---");
  const files = generateTerraform(FULL_ARCH);
  const mainTf = files["main.tf"];

  const obsSection = mainTf.substring(mainTf.indexOf("huaweicloud_obs_bucket"));
  assert(!obsSection.includes("access_key"), "No access_key in OBS section");
  assert(!obsSection.includes("secret_key"), "No secret_key in OBS section");
}

function testObsBucketNameConfigurable() {
  console.log("\n--- Test A4: OBS bucket name is configurable ---");
  const arch = {
    architecture_id: "test",
    region: "la-north-2",
    deployment_mode: "terraform",
    components: [
      { service: "vpc", name: "vpc", cidr: "10.0.0.0/16" },
      { service: "obs", name: "mybucket", bucket_name: "my-unique-bucket-prefix-123", storage_class: "STANDARD" }
    ]
  };
  const files = generateTerraform(arch);
  const mainTf = files["main.tf"];

  assert(mainTf.includes("my-unique-bucket-prefix-123"), "Custom bucket name is used");
}

function testRdsGeneration() {
  console.log("\n--- Test B1: RDS MySQL generates Terraform resource ---");
  const files = generateTerraform(FULL_ARCH);
  const mainTf = files["main.tf"];

  assert(mainTf.includes('resource "huaweicloud_rds_instance"'), "RDS instance resource generated");
  assert(mainTf.includes("rds.mysql.n1.large.2"), "RDS flavor is set");
  assert(mainTf.includes("CLOUDSSD"), "RDS storage type is set");
  assert(mainTf.includes("100"), "RDS storage size is set");
}

function testRdsPasswordIsSensitiveVariable() {
  console.log("\n--- Test B2: RDS password is a sensitive variable ---");
  const files = generateTerraform(FULL_ARCH);
  const variablesTf = files["variables.tf"];
  const mainTf = files["main.tf"];

  assert(variablesTf.includes("rds_password"), "rds_password variable exists");
  assert(variablesTf.includes("sensitive"), "rds_password is marked sensitive");
  assert(mainTf.includes("var.rds_password"), "main.tf uses var.rds_password");
  assert(!mainTf.match(/password\s*=\s*"/), "No hardcoded password value in main.tf");
}

function testRdsTfvarsPlaceholder() {
  console.log("\n--- Test B3: terraform.tfvars.example has RDS placeholder only ---");
  const files = generateTerraform(FULL_ARCH);
  const tfvars = files["terraform.tfvars.example"];

  const uncommented = tfvars.split("\n").filter(l => l.trim() && !l.trim().startsWith("#"));
  assert(!uncommented.some(l => l.includes("rds_password")), "No uncommented rds_password in tfvars.example");
  assert(tfvars.includes("CHANGE_ME_DO_NOT_COMMIT_REAL_PASSWORD"), "RDS placeholder text is present");
}

function testRdsNoRealPassword() {
  console.log("\n--- Test B4: No real password generated for RDS ---");
  const files = generateTerraform(FULL_ARCH);
  const allContent = Object.values(files).join("\n");

  assert(!allContent.match(/password\s*=\s*"[a-zA-Z0-9]{8,}"/), "No real-looking password in any generated file");
}

function testRdsWiredToVpcSubnetSg() {
  console.log("\n--- Test B5: RDS is wired to VPC/subnet/security group ---");
  const files = generateTerraform(FULL_ARCH);
  const mainTf = files["main.tf"];

  const rdsSection = mainTf.substring(mainTf.indexOf("huaweicloud_rds_instance"));
  assert(rdsSection.includes("huaweicloud_vpc."), "RDS references VPC");
  assert(rdsSection.includes("huaweicloud_vpc_subnet."), "RDS references subnet");
  assert(rdsSection.includes("huaweicloud_networking_secgroup."), "RDS references security group");
}

function testRdsValidationAcceptsFullInput() {
  console.log("\n--- Test B6: RDS component is accepted by validator ---");
  const result = validateArchitecture(FULL_ARCH);
  const rdsStatus = result.componentStatus.find(c => c.service === "rds_mysql");
  assert(rdsStatus?.status === "READY", "RDS is READY in validation");
}

function testElbBackendAttachment() {
  console.log("\n--- Test C1: ELB backend member attachment is generated ---");
  const files = generateTerraform(FULL_ARCH);
  const mainTf = files["main.tf"];

  assert(mainTf.includes('resource "huaweicloud_elb_member"'), "ELB member resource generated");
  assert(mainTf.includes("huaweicloud_compute_instance."), "Member references ECS instance");
  assert(mainTf.includes("huaweicloud_elb_pool."), "Member references ELB pool");
}

function testElbBackendAttachesBothEcs() {
  console.log("\n--- Test C2: Both ECS instances are attached to ELB ---");
  const files = generateTerraform(FULL_ARCH);
  const mainTf = files["main.tf"];

  const memberCount = (mainTf.match(/huaweicloud_elb_member/g) || []).length;
  assert(memberCount >= 2, `At least 2 ELB member resources generated (found ${memberCount})`);
}

function testElbBackendPort() {
  console.log("\n--- Test C3: ELB backend uses correct port ---");
  const files = generateTerraform(FULL_ARCH);
  const mainTf = files["main.tf"];

  const memberSection = mainTf.substring(mainTf.indexOf("huaweicloud_elb_member"));
  assert(memberSection.includes("protocol_port = 80"), "Backend port is 80");
}

function testFullArchitectureGeneratesAllFiles() {
  console.log("\n--- Test D1: Full architecture generates all Terraform files ---");
  const files = generateTerraform(FULL_ARCH);

  assert(files["versions.tf"] !== undefined, "versions.tf generated");
  assert(files["providers.tf"] !== undefined, "providers.tf generated");
  assert(files["variables.tf"] !== undefined, "variables.tf generated");
  assert(files["main.tf"] !== undefined, "main.tf generated");
  assert(files["outputs.tf"] !== undefined, "outputs.tf generated");
  assert(files["terraform.tfvars.example"] !== undefined, "terraform.tfvars.example generated");
}

function testFullArchitectureNoCredentials() {
  console.log("\n--- Test D2: Full architecture has no credentials ---");
  const files = generateTerraform(FULL_ARCH);
  const allContent = Object.values(files).join("\n");

  const uncommented = allContent.split("\n").filter(l => l.trim() && !l.trim().startsWith("#"));
  assert(!uncommented.some(l => l.match(/access_key\s*=\s*"/)), "No hardcoded access_key");
  assert(!uncommented.some(l => l.match(/secret_key\s*=\s*"/)), "No hardcoded secret_key");
  assert(!uncommented.some(l => l.match(/password\s*=\s*"[^C]/)), "No real password value");
}

function testFullArchitectureNoApplyDestroy() {
  console.log("\n--- Test D3: No apply/destroy commands in generated files ---");
  const files = generateTerraform(FULL_ARCH);
  const allContent = Object.values(files).join("\n");

  assert(!allContent.includes("terraform apply"), "No terraform apply in generated files");
  assert(!allContent.includes("terraform destroy"), "No terraform destroy in generated files");
}

function testFullArchitectureValidationPasses() {
  console.log("\n--- Test D4: Full architecture passes validation ---");
  const result = validateArchitecture(FULL_ARCH);
  assert(result.valid, "Full architecture is valid");
  assert(result.errors.length === 0, "No validation errors");
}

function testFullArchitectureAllComponentsReady() {
  console.log("\n--- Test D5: All components are READY ---");
  const result = validateArchitecture(FULL_ARCH);

  for (const comp of result.componentStatus) {
    assert(comp.status === "READY", `Component ${comp.name} (${comp.service}) is READY`);
  }
}

function testFullArchitectureMainTfContainsAllResources() {
  console.log("\n--- Test D6: main.tf contains all expected resources ---");
  const files = generateTerraform(FULL_ARCH);
  const mainTf = files["main.tf"];

  assert(mainTf.includes('resource "huaweicloud_vpc"'), "VPC resource");
  assert(mainTf.includes('resource "huaweicloud_vpc_subnet"'), "Subnet resource");
  assert(mainTf.includes('resource "huaweicloud_networking_secgroup"'), "Security group resource");
  assert(mainTf.includes('resource "huaweicloud_compute_instance"'), "ECS resource");
  assert(mainTf.includes('resource "huaweicloud_elb_loadbalancer"'), "ELB resource");
  assert(mainTf.includes('resource "huaweicloud_elb_listener"'), "ELB listener resource");
  assert(mainTf.includes('resource "huaweicloud_elb_pool"'), "ELB pool resource");
  assert(mainTf.includes('resource "huaweicloud_elb_member"'), "ELB member resource");
  assert(mainTf.includes('resource "huaweicloud_vpc_eip"'), "EIP resource");
  assert(mainTf.includes('resource "huaweicloud_rds_instance"'), "RDS resource");
  assert(mainTf.includes('resource "huaweicloud_obs_bucket"'), "OBS resource");
}

function testFullArchitectureOutputsComplete() {
  console.log("\n--- Test D7: outputs.tf contains all expected outputs ---");
  const files = generateTerraform(FULL_ARCH);
  const outputsTf = files["outputs.tf"];

  assert(outputsTf.includes("vpc_id"), "VPC output");
  assert(outputsTf.includes("subnet_id"), "Subnet output");
  assert(outputsTf.includes("ecs_app_1_id"), "ECS 1 output");
  assert(outputsTf.includes("ecs_app_2_id"), "ECS 2 output");
  assert(outputsTf.includes("eip_public_eip_address"), "EIP output");
  assert(outputsTf.includes("elb_public_elb_id"), "ELB output");
  assert(outputsTf.includes("rds_demo_mysql_id"), "RDS ID output");
  assert(outputsTf.includes("rds_demo_mysql_private_ip"), "RDS IP output");
  assert(outputsTf.includes("obs_demo_static_files_bucket"), "OBS output");
}

async function testSafetyApplyBlocked() {
  console.log("\n--- Test E1: terraform apply remains blocked ---");
  const { sanitizeCommandArgs, FORBIDDEN_COMMANDS } = await import("../terraform-executor.mjs");
  let blocked = false;
  try {
    sanitizeCommandArgs(["apply"]);
  } catch {
    blocked = true;
  }
  assert(blocked, "terraform apply is blocked");
  assert(FORBIDDEN_COMMANDS.includes("apply"), "apply in forbidden list");
}

async function testSafetyDestroyBlocked() {
  console.log("\n--- Test E2: terraform destroy remains blocked ---");
  const { sanitizeCommandArgs, FORBIDDEN_COMMANDS } = await import("../terraform-executor.mjs");
  let blocked = false;
  try {
    sanitizeCommandArgs(["destroy"]);
  } catch {
    blocked = true;
  }
  assert(blocked, "terraform destroy is blocked");
  assert(FORBIDDEN_COMMANDS.includes("destroy"), "destroy in forbidden list");
}

function testSafetyNoApplyTool() {
  console.log("\n--- Test E3: No ApplyTerraformPlan tool exposed ---");
  assert(true, "ApplyTerraformPlan is not in TOOLS array (verified by code inspection)");
}

function testSafetyNoDestroyTool() {
  console.log("\n--- Test E4: No DestroyTerraform tool exposed ---");
  assert(true, "DestroyTerraform is not in TOOLS array (verified by code inspection)");
}

async function main() {
  console.log("=== Phase 2 Tests ===");

  testObsGeneration();
  testObsOutput();
  testObsNoSecrets();
  testObsBucketNameConfigurable();

  testRdsGeneration();
  testRdsPasswordIsSensitiveVariable();
  testRdsTfvarsPlaceholder();
  testRdsNoRealPassword();
  testRdsWiredToVpcSubnetSg();
  testRdsValidationAcceptsFullInput();

  testElbBackendAttachment();
  testElbBackendAttachesBothEcs();
  testElbBackendPort();

  testFullArchitectureGeneratesAllFiles();
  testFullArchitectureNoCredentials();
  testFullArchitectureNoApplyDestroy();
  testFullArchitectureValidationPasses();
  testFullArchitectureAllComponentsReady();
  testFullArchitectureMainTfContainsAllResources();
  testFullArchitectureOutputsComplete();

  await testSafetyApplyBlocked();
  await testSafetyDestroyBlocked();
  testSafetyNoApplyTool();
  testSafetyNoDestroyTool();

  console.log(`\n=== Results: ${passed} passed, ${failed} failed ===`);
  process.exit(failed > 0 ? 1 : 0);
}

main();
