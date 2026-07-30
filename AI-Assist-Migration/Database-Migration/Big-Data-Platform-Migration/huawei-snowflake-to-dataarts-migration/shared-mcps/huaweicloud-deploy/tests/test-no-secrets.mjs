import { generateTerraform } from "../terraform-generator.mjs";
import { validateArchitecture } from "../architecture-validator.mjs";

const SENSITIVE_PATTERNS = [
  "access_key", "secret_key", "password=", "token=",
  "HW_ACCESS_KEY", "HW_SECRET_KEY", "AK", "SK",
  "credential"
];

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

function scanForSecrets(text, filename) {
  const findings = [];
  const lines = text.split("\n");
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();
    if (trimmed.startsWith("#")) continue;

    for (const pattern of SENSITIVE_PATTERNS) {
      if (line.includes(pattern) && !line.includes("var.") && !line.includes("environment") && !line.includes("REPLACE_") && !line.includes("TF_VAR_")) {
        findings.push({ file: filename, line: i + 1, pattern, content: trimmed });
      }
    }
  }
  return findings;
}

const SAMPLE_ARCH = {
  architecture_id: "secret-scan-test",
  region: "la-north-2",
  deployment_mode: "terraform",
  components: [
    { service: "vpc", name: "demo-vpc", cidr: "192.168.0.0/16" },
    { service: "subnet", name: "demo-subnet", cidr: "192.168.1.0/24" },
    { service: "security_group", name: "demo-sg" },
    { service: "ecs", name: "app", quantity: 2, flavor: "s6.large.2", image_name: "Ubuntu 24.04", system_disk_type: "GPSSD", system_disk_size_gb: 40 },
    { service: "elb", name: "public-elb", type: "shared", listener_port: 80, backend_port: 80 },
    { service: "eip", name: "public-eip", bandwidth_mbps: 10 }
  ]
};

async function testNoSecretsInGeneratedFiles() {
  console.log("\n--- Test: No secrets in any generated Terraform files ---");
  const files = generateTerraform(SAMPLE_ARCH);
  let totalFindings = [];

  for (const [filename, content] of Object.entries(files)) {
    const findings = scanForSecrets(content, filename);
    totalFindings.push(...findings);
  }

  assert(totalFindings.length === 0, `No secrets found in generated files (found ${totalFindings.length})`);
  if (totalFindings.length > 0) {
    for (const f of totalFindings) {
      console.log(`    LEAK: ${f.file}:${f.line} - pattern "${f.pattern}" in: ${f.content}`);
    }
  }
}

async function testNoSecretsInInputValidation() {
  console.log("\n--- Test: Input with secrets is rejected ---");
  const archWithSecret = {
    ...SAMPLE_ARCH,
    components: [
      ...SAMPLE_ARCH.components,
      { service: "ecs", name: "leaky", flavor: "s6.large.2", image_name: "Ubuntu 24.04", system_disk_type: "GPSSD", system_disk_size_gb: 40, access_key: "AKIAIOSFODNN7EXAMPLE" }
    ]
  };

  const result = validateArchitecture(archWithSecret);
  assert(!result.valid, "Architecture with secret in input is rejected");
  assert(result.errors.some(e => e.includes("Secret") || e.includes("secret")), "Error mentions secret detection");
}

async function testProvidersTfUsesEnvVars() {
  console.log("\n--- Test: providers.tf uses env vars, not hardcoded credentials ---");
  const files = generateTerraform(SAMPLE_ARCH);
  const providersTf = files["providers.tf"];

  assert(!providersTf.match(/access_key\s*=\s*"/), "No hardcoded access_key");
  assert(!providersTf.match(/secret_key\s*=\s*"/), "No hardcoded secret_key");
  assert(providersTf.includes("environment variables"), "Mentions environment variables in comment");
}

async function testVariablesTfMarksSensitive() {
  console.log("\n--- Test: variables.tf marks sensitive variables ---");
  const files = generateTerraform(SAMPLE_ARCH);
  const variablesTf = files["variables.tf"];

  assert(variablesTf.includes("sensitive"), "Password variable is marked sensitive");
  assert(variablesTf.includes("ecs_admin_password"), "Password variable exists");
}

async function testTfvarsExampleIsSafe() {
  console.log("\n--- Test: terraform.tfvars.example is safe to commit ---");
  const files = generateTerraform(SAMPLE_ARCH);
  const tfvars = files["terraform.tfvars.example"];

  assert(!tfvars.includes("AKIA"), "No AWS-style key in tfvars.example");
  const uncommented = tfvars.split("\n").filter(l => l.trim() && !l.trim().startsWith("#"));
  assert(!uncommented.some(l => l.match(/password\s*=\s*"/)), "No real password value in tfvars.example");
  assert(tfvars.includes("NEVER commit"), "Contains warning about committing secrets");
}

async function main() {
  console.log("=== No-Secrets Tests ===");

  await testNoSecretsInGeneratedFiles();
  await testNoSecretsInInputValidation();
  await testProvidersTfUsesEnvVars();
  await testVariablesTfMarksSensitive();
  await testTfvarsExampleIsSafe();

  console.log(`\n=== Results: ${passed} passed, ${failed} failed ===`);
  process.exit(failed > 0 ? 1 : 0);
}

main();
