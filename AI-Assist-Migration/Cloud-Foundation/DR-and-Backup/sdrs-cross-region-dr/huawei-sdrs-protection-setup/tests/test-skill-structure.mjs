import { readFileSync, existsSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const skillDir = join(__dirname, "..");
const scenarioDir = join(__dirname, "..", "..");

const errors = [];

function assert(condition, message) {
  if (!condition) errors.push(message);
}

function readSkillMd() {
  const path = join(skillDir, "SKILL.md");
  assert(existsSync(path), "SKILL.md must exist");
  return readFileSync(path, "utf8");
}

const skillMd = readSkillMd();

assert(skillMd.includes("name: huawei-sdrs-protection-setup"), "SKILL.md frontmatter name must be huawei-sdrs-protection-setup");
assert(skillMd.includes("status: EXPERIMENTAL"), "SKILL.md status must be EXPERIMENTAL");
assert(skillMd.includes("risk_level: high"), "SKILL.md risk_level must be high");
assert(skillMd.includes("requires_explicit_approval: true"), "SKILL.md must require explicit approval");
assert(skillMd.includes("protection_setup_only"), "SKILL.md must declare protection_setup_only scope");
assert(skillMd.includes("huawei-sdrs-dr-drill"), "SKILL.md must reference next skill huawei-sdrs-dr-drill");
assert(!skillMd.includes("STEP") || !skillMd.match(/STEP.*production failover/i), "SKILL.md must NOT include production failover as a workflow step");
assert(!skillMd.includes("execute failback"), "SKILL.md must NOT include failback execution in scope");
assert(skillMd.includes("GAP-SDR-001"), "SKILL.md must document GAP-SDR-001");
assert(skillMd.includes("GAP-SDR-002"), "SKILL.md must document GAP-SDR-002");
assert(skillMd.includes("# Rules"), "SKILL.md must have Rules section");
assert(skillMd.includes("# Prerequisites"), "SKILL.md must have Prerequisites section");
assert(skillMd.includes("PARSE INTENT") || skillMd.includes("parse_intent") || skillMd.includes("Parse") || skillMd.includes("STEP 1"), "SKILL.md must have PARSE INTENT step");
assert(skillMd.includes("# Troubleshooting"), "SKILL.md must have Troubleshooting section");

assert(existsSync(join(skillDir, "assets", "metadata", "skill.yaml")), "skill.yaml must exist in assets/metadata/");
assert(existsSync(join(skillDir, "assets", "metadata", "mcp-dependencies.yaml")), "mcp-dependencies.yaml must exist in assets/metadata/");

const mcpDeps = readFileSync(join(skillDir, "assets", "metadata", "mcp-dependencies.yaml"), "utf8");
assert(mcpDeps.includes("shared/mcps/huaweicloud-pricing"), "mcp-dependencies.yaml must reference shared/mcps path");
assert(mcpDeps.includes("shared/skills/mcp-capability-builder"), "mcp-dependencies.yaml must reference shared/skills path");

assert(existsSync(join(scenarioDir, "references")), "Scenario-level references must exist");

if (errors.length > 0) {
  console.error("FAILURES:");
  errors.forEach((e) => console.error("  - " + e));
  process.exit(1);
}

console.log("PASS: huawei-sdrs-protection-setup structure test (" + errors.length + " errors)");
