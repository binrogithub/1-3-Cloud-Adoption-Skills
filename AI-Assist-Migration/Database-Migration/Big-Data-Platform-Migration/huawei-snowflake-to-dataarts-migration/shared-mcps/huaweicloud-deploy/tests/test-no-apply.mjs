import { sanitizeCommandArgs, FORBIDDEN_COMMANDS } from "../terraform-executor.mjs";

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

function testApplyIsBlocked() {
  console.log("\n--- Test: terraform apply is blocked ---");
  let blocked = false;
  try {
    sanitizeCommandArgs(["apply"]);
  } catch (e) {
    blocked = true;
    assert(e.message.includes("BLOCKED"), "Error message says BLOCKED");
    assert(e.message.includes("phase 2"), "Error message mentions phase 2");
  }
  assert(blocked, "terraform apply throws error");
}

function testDestroyIsBlocked() {
  console.log("\n--- Test: terraform destroy is blocked ---");
  let blocked = false;
  try {
    sanitizeCommandArgs(["destroy"]);
  } catch (e) {
    blocked = true;
    assert(e.message.includes("BLOCKED"), "Error message says BLOCKED");
  }
  assert(blocked, "terraform destroy throws error");
}

function testApplyWithAutoApproveIsBlocked() {
  console.log("\n--- Test: terraform apply -auto-approve is blocked ---");
  let blocked = false;
  try {
    sanitizeCommandArgs(["apply", "-auto-approve"]);
  } catch (e) {
    blocked = true;
  }
  assert(blocked, "terraform apply -auto-approve throws error");
}

function testPlanIsAllowed() {
  console.log("\n--- Test: terraform plan is allowed ---");
  let allowed = true;
  try {
    sanitizeCommandArgs(["plan"]);
  } catch {
    allowed = false;
  }
  assert(allowed, "terraform plan does not throw");
}

function testInitIsAllowed() {
  console.log("\n--- Test: terraform init is allowed ---");
  let allowed = true;
  try {
    sanitizeCommandArgs(["init"]);
  } catch {
    allowed = false;
  }
  assert(allowed, "terraform init does not throw");
}

function testValidateIsAllowed() {
  console.log("\n--- Test: terraform validate is allowed ---");
  let allowed = true;
  try {
    sanitizeCommandArgs(["validate"]);
  } catch {
    allowed = false;
  }
  assert(allowed, "terraform validate does not throw");
}

function testFmtIsAllowed() {
  console.log("\n--- Test: terraform fmt is allowed ---");
  let allowed = true;
  try {
    sanitizeCommandArgs(["fmt"]);
  } catch {
    allowed = false;
  }
  assert(allowed, "terraform fmt does not throw");
}

function testShowIsAllowed() {
  console.log("\n--- Test: terraform show is allowed ---");
  let allowed = true;
  try {
    sanitizeCommandArgs(["show", "-json", "tfplan"]);
  } catch {
    allowed = false;
  }
  assert(allowed, "terraform show does not throw");
}

function testForbiddenCommandsList() {
  console.log("\n--- Test: FORBIDDEN_COMMANDS is correct ---");
  assert(FORBIDDEN_COMMANDS.includes("apply"), "apply is in forbidden list");
  assert(FORBIDDEN_COMMANDS.includes("destroy"), "destroy is in forbidden list");
  assert(!FORBIDDEN_COMMANDS.includes("plan"), "plan is NOT in forbidden list");
  assert(!FORBIDDEN_COMMANDS.includes("init"), "init is NOT in forbidden list");
}

async function main() {
  console.log("=== No-Apply Safety Tests ===");

  testApplyIsBlocked();
  testDestroyIsBlocked();
  testApplyWithAutoApproveIsBlocked();
  testPlanIsAllowed();
  testInitIsAllowed();
  testValidateIsAllowed();
  testFmtIsAllowed();
  testShowIsAllowed();
  testForbiddenCommandsList();

  console.log(`\n=== Results: ${passed} passed, ${failed} failed ===`);
  process.exit(failed > 0 ? 1 : 0);
}

main();
