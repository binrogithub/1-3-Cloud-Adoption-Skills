import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const TIMEOUT = 60000;

function assert(cond, msg) {
  if (!cond) throw new Error(`ASSERTION FAILED: ${msg}`);
}

const RUN_LIVE_API = process.env.RUN_LIVE_API === "true";
function requireLiveApi(reason) {
  if (!RUN_LIVE_API) return `SKIP_LIVE_API: ${reason}`;
  return null;
}

async function runTest() {
  const transport = new StdioClientTransport({
    command: "node",
    args: ["server.mjs"],
    env: { ...process.env }
  });

  const client = new Client({ name: "test-client", version: "1.0.0" });
  await client.connect(transport);

  const tools = await client.listTools();
  const findTool = tools.tools.find((t) => t.name === "FindEcsFlavorCandidates");
  assert(findTool, "FindEcsFlavorCandidates tool must be registered");

  const evalTool = tools.tools.find((t) => t.name === "EvaluateEcsFlavorAvailability");
  assert(evalTool, "EvaluateEcsFlavorAvailability tool must still be registered");

  let passed = 0;
  let failed = 0;
  let skipped = 0;

  async function testT(name, fn) {
    try {
      const result = await fn();
      if (result === "skip" || (typeof result === "string" && result.startsWith("SKIP_LIVE_API:"))) {
        console.log(`  SKIP: ${name} (${result})`);
        skipped++;
      } else {
        console.log(`  PASS: ${name}`);
        passed++;
      }
    } catch (e) {
      console.log(`  FAIL: ${name}: ${e.message}`);
      failed++;
    }
  }

  console.log("FindEcsFlavorCandidates tests\n");

  // T1: targets is required and must be non-empty
  await testT("T1: targets required and non-empty", async () => {
    const res = await client.callTool({
      name: "FindEcsFlavorCandidates",
      arguments: { region: "la-north-2", vcpus: 2, ram_gb: 4 }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "ERROR", "status must be ERROR when targets missing");
    assert(data.error && data.error.includes("targets"), "error must mention targets");
  });

  // T2: vcpus and ram_gb are required
  await testT("T2: vcpus and ram_gb required", async () => {
    const res = await client.callTool({
      name: "FindEcsFlavorCandidates",
      arguments: { region: "la-north-2", targets: [{ availability_zone: "la-north-2a" }] }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "ERROR", "status must be ERROR when vcpus/ram_gb missing");
    assert(data.error && data.error.includes("vcpus"), "error must mention vcpus");
  });

  // T3: Single AZ returns structured output with status and summary
  await testT("T3: single AZ returns status and summary", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for ECS flavor discovery API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "FindEcsFlavorCandidates",
      arguments: {
        region: "la-north-2",
        targets: [{ availability_zone: "la-north-2a" }],
        vcpus: 2,
        ram_gb: 4,
        timeout_ms: 30000
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.tool === "FindEcsFlavorCandidates", "tool name must match");
    assert(["OK", "PARTIAL", "ERROR"].includes(data.status), `status must be OK/PARTIAL/ERROR, got ${data.status}`);
    assert(data.summary, "summary must exist");
    assert(typeof data.summary.azs_evaluated === "number", "summary.azs_evaluated must be number");
    assert(data.summary.azs_evaluated === 1, "summary.azs_evaluated must be 1 for single AZ");
    assert(typeof data.summary.azs_with_exact_match === "number", "summary.azs_with_exact_match must be number");
    assert(typeof data.summary.azs_with_alternatives === "number", "summary.azs_with_alternatives must be number");
    assert(typeof data.summary.azs_with_only_oversized === "number", "summary.azs_with_only_oversized must be number");
    assert(typeof data.summary.azs_unavailable === "number", "summary.azs_unavailable must be number");
    assert(typeof data.summary.azs_with_discovery_error === "number", "summary.azs_with_discovery_error must be number");
    assert(typeof data.summary.total_exact_matches === "number", "summary.total_exact_matches must be number");
    assert(typeof data.summary.total_alternatives === "number", "summary.total_alternatives must be number");
    assert(typeof data.summary.total_oversized_candidates === "number", "summary.total_oversized_candidates must be number");
    assert(Array.isArray(data.results), "results must be array");
    assert(data.results.length === 1, "results must have 1 entry");
    assert(data.results[0].availability_zone === "la-north-2a", "AZ must be la-north-2a");
  });

  // T4: Multiple AZs evaluates all
  await testT("T4: multiple AZs evaluates all", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for ECS flavor discovery API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "FindEcsFlavorCandidates",
      arguments: {
        region: "la-north-2",
        targets: [
          { availability_zone: "la-north-2a" },
          { availability_zone: "la-north-2b" }
        ],
        vcpus: 2,
        ram_gb: 4,
        timeout_ms: 30000
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(["OK", "PARTIAL", "ERROR"].includes(data.status), `global status must be OK/PARTIAL/ERROR, got ${data.status}`);
    assert(data.summary.azs_evaluated === 2, "must evaluate 2 AZs");
    assert(data.results.length === 2, "results must have 2 entries");
    const azs = data.results.map((r) => r.availability_zone);
    assert(azs.includes("la-north-2a"), "must include la-north-2a");
    assert(azs.includes("la-north-2b"), "must include la-north-2b");
  });

  // T5: max_oversized_candidates limits oversized_candidates per AZ
  await testT("T5: max_oversized_candidates limits output", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for ECS flavor discovery API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "FindEcsFlavorCandidates",
      arguments: {
        region: "la-north-2",
        targets: [{ availability_zone: "la-north-2a" }],
        vcpus: 2,
        ram_gb: 4,
        include_oversized_candidates: true,
        max_oversized_candidates: 3,
        timeout_ms: 30000
      }
    });
    const data = JSON.parse(res.content[0].text);
    for (const r of data.results) {
      assert(r.oversized_candidates.length <= 3, `oversized_candidates must be <= 3, got ${r.oversized_candidates.length}`);
    }
  });

  // T6: oversized_candidates sorted by resource_jump_score ascending
  await testT("T6: oversized_candidates sorted by resource_jump_score", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for ECS flavor discovery API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "FindEcsFlavorCandidates",
      arguments: {
        region: "la-north-2",
        targets: [{ availability_zone: "la-north-2a" }],
        vcpus: 2,
        ram_gb: 4,
        include_oversized_candidates: true,
        max_oversized_candidates: 10,
        timeout_ms: 30000
      }
    });
    const data = JSON.parse(res.content[0].text);
    for (const r of data.results) {
      for (let i = 1; i < r.oversized_candidates.length; i++) {
        assert(
          r.oversized_candidates[i].resource_jump_score >= r.oversized_candidates[i - 1].resource_jump_score,
          "oversized_candidates must be sorted by resource_jump_score ascending"
        );
      }
    }
  });

  // T7: m6.16xlarge.8 never appears as normal alternative for 2 vCPU / 4 GB
  await testT("T7: m6.16xlarge.8 never in alternatives for 2vCPU/4GB", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for ECS flavor discovery API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "FindEcsFlavorCandidates",
      arguments: {
        region: "la-north-2",
        targets: [{ availability_zone: "la-north-2a" }],
        vcpus: 2,
        ram_gb: 4,
        timeout_ms: 30000
      }
    });
    const data = JSON.parse(res.content[0].text);
    for (const r of data.results) {
      const altIds = r.alternatives.map((f) => f.flavor_id);
      assert(!altIds.includes("m6.16xlarge.8"), "m6.16xlarge.8 must not appear in alternatives for 2 vCPU / 4 GB");
    }
  });

  // T8: Both AZs evaluated; la-north-2b result depends on real discovery
  await testT("T8: both AZs evaluated, la-north-2b depends on real discovery", async () => {
    const skip = requireLiveApi("requires HUAWEI_PROJECT_ID for ECS flavor discovery API");
    if (skip) return skip;
    const res = await client.callTool({
      name: "FindEcsFlavorCandidates",
      arguments: {
        region: "la-north-2",
        targets: [
          { availability_zone: "la-north-2a" },
          { availability_zone: "la-north-2b" }
        ],
        vcpus: 2,
        ram_gb: 4,
        timeout_ms: 30000
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.results.length === 2, "must have 2 AZ results");
    const az2a = data.results.find((r) => r.availability_zone === "la-north-2a");
    const az2b = data.results.find((r) => r.availability_zone === "la-north-2b");
    assert(az2a, "la-north-2a must be in results");
    assert(az2b, "la-north-2b must be in results");
    // la-north-2a should have a real status (not discovery_error in normal conditions)
    assert(az2a.status !== "discovery_error", "la-north-2a should not have discovery_error");
    // la-north-2b: we do NOT assume it has s6.large.2 as recommendable.
    // We only validate that it was evaluated and has a valid status.
    assert(
      ["available", "alternatives_available", "no_exact_match", "unavailable", "invalid_selection", "discovery_error"].includes(az2b.status),
      `la-north-2b status must be a valid AZ status, got ${az2b.status}`
    );
    // If la-north-2b is not discovery_error, it must have numeric totals
    if (az2b.status !== "discovery_error") {
      assert(typeof az2b.total_flavors_evaluated === "number", "la-north-2b total_flavors_evaluated must be number");
      assert(typeof az2b.total_recommendable_in_az === "number", "la-north-2b total_recommendable_in_az must be number");
    }
  });

  await client.close();

  console.log(`\nResults: ${passed} passed, ${failed} failed, ${skipped} skipped`);
  process.exit(failed > 0 ? 1 : 0);
}

runTest().catch((e) => {
  console.error("Test runner error:", e);
  process.exit(2);
});
