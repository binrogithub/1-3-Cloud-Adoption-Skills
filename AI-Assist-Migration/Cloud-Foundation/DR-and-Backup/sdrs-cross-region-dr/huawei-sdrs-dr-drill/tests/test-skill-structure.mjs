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

assert(skillMd.includes("name: huawei-sdrs-dr-drill"), "SKILL.md frontmatter name must be huawei-sdrs-dr-drill");
assert(skillMd.includes("status: EXPERIMENTAL"), "SKILL.md status must be EXPERIMENTAL");
assert(skillMd.includes("risk_level: high"), "SKILL.md risk_level must be high");
assert(skillMd.includes("requires_explicit_approval: true"), "SKILL.md must require explicit approval");
assert(skillMd.includes("dr_drill_only"), "SKILL.md must declare dr_drill_only scope");
assert(skillMd.includes("DR DRILL") && skillMd.includes("PRODUCTION FAILOVER"), "SKILL.md must state DR DRILL != PRODUCTION FAILOVER");
assert(!skillMd.includes("planned failover") || skillMd.includes("MUST NOT perform"), "SKILL.md must NOT claim to perform planned failover");
assert(skillMd.includes("huawei-sdrs-protection-setup"), "SKILL.md must reference prerequisite skill huawei-sdrs-protection-setup");
assert(skillMd.includes("GAP-SDR-001"), "SKILL.md must document GAP-SDR-001");
assert(skillMd.includes("# Rules"), "SKILL.md must have Rules section");
assert(skillMd.includes("# Prerequisites"), "SKILL.md must have Prerequisites section");
assert(skillMd.includes("# Troubleshooting"), "SKILL.md must have Troubleshooting section");

assert(existsSync(join(skillDir, "assets", "metadata", "skill.yaml")), "skill.yaml must exist");
assert(existsSync(join(skillDir, "assets", "metadata", "mcp-dependencies.yaml")), "mcp-dependencies.yaml must exist");

const mcpDeps = readFileSync(join(skillDir, "assets", "metadata", "mcp-dependencies.yaml"), "utf8");
assert(mcpDeps.includes("shared/mcps/"), "mcp-dependencies.yaml must use shared/mcps paths");

if (errors.length > 0) {
  console.error("FAILURES:");
  errors.forEach((e) => console.error("  - " + e));
  process.exit(1);
}

console.log("PASS: huawei-sdrs-dr-drill structure test (" + errors.length + " errors)");
