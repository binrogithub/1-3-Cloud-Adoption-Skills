import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

function assert(cond, msg) {
  if (!cond) throw new Error(`ASSERTION FAILED: ${msg}`);
}

let passed = 0;
let failed = 0;

async function testT(name, fn) {
  try {
    await fn();
    console.log(`  PASS: ${name}`);
    passed++;
  } catch (e) {
    console.log(`  FAIL: ${name}: ${e.message}`);
    failed++;
  }
}

async function makeClient(envOverrides = {}) {
  const transport = new StdioClientTransport({
    command: "node",
    args: ["server.mjs"],
    env: { ...process.env, ...envOverrides }
  });
  const client = new Client({ name: "test-client", version: "1.0.0" });
  await client.connect(transport);
  return client;
}

async function callToolSafe(client, name, args) {
  try {
    const res = await client.callTool({ name, arguments: args });
    const data = JSON.parse(res.content[0].text);
    return { ok: true, data };
  } catch (e) {
    const msg = e.message || "";
    if (msg.includes("configuration_error")) {
      return { ok: false, configurationError: true, message: msg };
    }
    return { ok: false, configurationError: false, message: msg };
  }
}

async function runUnitTests() {
  console.log("=== Unit tests: resolveProjectIdForRegion ===\n");

  await testT("TC1: explicit mapping overrides legacy", async () => {
    const client = await makeClient({
      HUAWEI_PROJECT_IDS_BY_REGION: JSON.stringify({ "la-north-2": "pid_from_mapping" }),
      HUAWEI_PROJECT_ID: "pid_legacy",
      HUAWEI_DEFAULT_REGION: "la-north-2"
    });

    const result = await callToolSafe(client, "QueryEcsFlavors", {
      region: "la-north-2", availability_zone: "la-north-2a", timeout_ms: 5000
    });
    assert(!result.configurationError,
      "Should not return configuration_error when mapping exists for la-north-2");
    await client.close();
  });

  await testT("TC2: fallback legacy for default region", async () => {
    const client = await makeClient({
      HUAWEI_PROJECT_ID: "pid_legacy",
      HUAWEI_DEFAULT_REGION: "la-north-2"
    });

    const result = await callToolSafe(client, "QueryEcsFlavors", {
      region: "la-north-2", availability_zone: "la-north-2a", timeout_ms: 5000
    });
    assert(!result.configurationError,
      "Should not return configuration_error when legacy fallback applies for default region");
    await client.close();
  });

  await testT("TC3: unmapped region returns configuration_error", async () => {
    const client = await makeClient({
      HUAWEI_PROJECT_IDS_BY_REGION: JSON.stringify({ "la-north-2": "pid_la_north_2" }),
      HUAWEI_PROJECT_ID: "pid_legacy",
      HUAWEI_DEFAULT_REGION: "la-north-2"
    });

    const result = await callToolSafe(client, "QueryEcsFlavors", {
      region: "sa-brazil-1", availability_zone: "sa-brazil-1a", timeout_ms: 5000
    });
    assert(result.ok, "Should return a result, not throw");
    assert(result.data.error === "configuration_error",
      `error must be configuration_error, got ${result.data.error}`);
    assert(result.data.message && result.data.message.includes("sa-brazil-1"),
      "message must mention the region sa-brazil-1");
    assert(!result.data.message.includes("pid_legacy"),
      "message must NOT contain the legacy project ID");
    await client.close();
  });

  await testT("TC4: invalid JSON in HUAWEI_PROJECT_IDS_BY_REGION", async () => {
    const client = await makeClient({
      HUAWEI_PROJECT_IDS_BY_REGION: "{bad json",
      HUAWEI_PROJECT_ID: "pid_legacy",
      HUAWEI_DEFAULT_REGION: "la-north-2"
    });

    const result = await callToolSafe(client, "QueryEcsFlavors", {
      region: "la-north-2", availability_zone: "la-north-2a", timeout_ms: 5000
    });
    assert(result.ok, "Should return a result, not throw");
    assert(result.data.error === "configuration_error",
      `error must be configuration_error, got ${result.data.error}`);
    assert(result.data.message && result.data.message.includes("invalid JSON"),
      "message must mention invalid JSON");
    assert(!result.data.message.includes("pid_legacy"),
      "message must NOT contain credentials or project IDs");
    await client.close();
  });

  await testT("TC5: FindEcsFlavorCandidates - unmapped region yields ERROR with discovery_error per AZ", async () => {
    const client = await makeClient({
      HUAWEI_PROJECT_IDS_BY_REGION: JSON.stringify({ "la-north-2": "pid_la_north_2" }),
      HUAWEI_PROJECT_ID: "pid_legacy",
      HUAWEI_DEFAULT_REGION: "la-north-2"
    });

    const res = await client.callTool({
      name: "FindEcsFlavorCandidates",
      arguments: {
        region: "sa-brazil-1",
        targets: [{ availability_zone: "sa-brazil-1a" }],
        vcpus: 2,
        ram_gb: 4
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "ERROR", `global status must be ERROR, got ${data.status}`);
    assert(data.results.length === 1, "must have 1 AZ result");
    assert(data.results[0].status === "discovery_error",
      `AZ status must be discovery_error, got ${data.results[0].status}`);
    assert(data.results[0].discovery_error && data.results[0].discovery_error.includes("configuration_error"),
      "discovery_error must contain configuration_error");
    assert(data.summary.azs_with_discovery_error === 1,
      "summary.azs_with_discovery_error must be 1");
    await client.close();
  });

  await testT("TC5b: FindEcsFlavorCandidates - mapped region does not block", async () => {
    const client = await makeClient({
      HUAWEI_PROJECT_IDS_BY_REGION: JSON.stringify({ "la-north-2": "pid_la_north_2" }),
      HUAWEI_DEFAULT_REGION: "la-north-2"
    });

    const result = await callToolSafe(client, "FindEcsFlavorCandidates", {
      region: "la-north-2",
      targets: [{ availability_zone: "la-north-2a" }],
      vcpus: 2,
      ram_gb: 4,
      timeout_ms: 30000
    });
    assert(!result.configurationError,
      "la-north-2 with mapping should not produce configuration_error");
    await client.close();
  });

  await testT("TC6: EvaluateEcsFlavorAvailability - unmapped region returns configuration_error", async () => {
    const client = await makeClient({
      HUAWEI_PROJECT_IDS_BY_REGION: JSON.stringify({ "la-north-2": "pid_la_north_2" }),
      HUAWEI_PROJECT_ID: "pid_legacy",
      HUAWEI_DEFAULT_REGION: "la-north-2"
    });

    const res = await client.callTool({
      name: "EvaluateEcsFlavorAvailability",
      arguments: {
        region: "sa-brazil-1",
        availability_zone: "sa-brazil-1a",
        vcpus: 2,
        ram_gb: 4
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "discovery_error",
      `status must be discovery_error, got ${data.status}`);
    assert(data.error === "configuration_error",
      `error must be configuration_error, got ${data.error}`);
    await client.close();
  });

  await testT("TC7: QueryElbFlavors - unmapped region returns configuration_error", async () => {
    const client = await makeClient({
      HUAWEI_PROJECT_IDS_BY_REGION: JSON.stringify({ "la-north-2": "pid_la_north_2" }),
      HUAWEI_PROJECT_ID: "pid_legacy",
      HUAWEI_DEFAULT_REGION: "la-north-2"
    });

    const res = await client.callTool({
      name: "QueryElbFlavors",
      arguments: { region: "sa-brazil-1" }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.error === "configuration_error",
      `error must be configuration_error, got ${data.error}`);
    await client.close();
  });

  await testT("TC8: No mapping, no HUAWEI_DEFAULT_REGION, implicit default la-north-2 works with legacy", async () => {
    const client = await makeClient({
      HUAWEI_PROJECT_ID: "pid_legacy"
    });

    const result = await callToolSafe(client, "QueryEcsFlavors", {
      region: "la-north-2", availability_zone: "la-north-2a", timeout_ms: 5000
    });
    assert(!result.configurationError,
      "Implicit default region la-north-2 should use legacy HUAWEI_PROJECT_ID");
    await client.close();
  });

  await testT("TC9: No mapping, no HUAWEI_DEFAULT_REGION, non-default region fails", async () => {
    const client = await makeClient({
      HUAWEI_PROJECT_ID: "pid_legacy"
    });

    const res = await client.callTool({
      name: "QueryEcsFlavors",
      arguments: { region: "sa-brazil-1", availability_zone: "sa-brazil-1a" }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.error === "configuration_error",
      `error must be configuration_error for non-default region without mapping, got ${data.error}`);
    await client.close();
  });

  await testT("TC10: QueryRdsFlavors - unmapped region returns configuration_error", async () => {
    const client = await makeClient({
      HUAWEI_PROJECT_IDS_BY_REGION: JSON.stringify({ "la-north-2": "pid_la_north_2" }),
      HUAWEI_PROJECT_ID: "pid_legacy",
      HUAWEI_DEFAULT_REGION: "la-north-2"
    });

    const res = await client.callTool({
      name: "QueryRdsFlavors",
      arguments: { region: "sa-brazil-1" }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.error === "configuration_error",
      `error must be configuration_error, got ${data.error}`);
    await client.close();
  });

  await testT("TC11: QueryEvsVolumeTypes - unmapped region returns configuration_error", async () => {
    const client = await makeClient({
      HUAWEI_PROJECT_IDS_BY_REGION: JSON.stringify({ "la-north-2": "pid_la_north_2" }),
      HUAWEI_PROJECT_ID: "pid_legacy",
      HUAWEI_DEFAULT_REGION: "la-north-2"
    });

    const res = await client.callTool({
      name: "QueryEvsVolumeTypes",
      arguments: { region: "sa-brazil-1" }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.error === "configuration_error",
      `error must be configuration_error, got ${data.error}`);
    await client.close();
  });

  await testT("TC12: FindEcsFlavorCandidates - invalid JSON blocks all AZs", async () => {
    const client = await makeClient({
      HUAWEI_PROJECT_IDS_BY_REGION: "{bad json",
      HUAWEI_PROJECT_ID: "pid_legacy",
      HUAWEI_DEFAULT_REGION: "la-north-2"
    });

    const res = await client.callTool({
      name: "FindEcsFlavorCandidates",
      arguments: {
        region: "la-north-2",
        targets: [{ availability_zone: "la-north-2a" }, { availability_zone: "la-north-2b" }],
        vcpus: 2,
        ram_gb: 4
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(data.status === "ERROR", `global status must be ERROR, got ${data.status}`);
    assert(data.results.length === 2, "must have 2 AZ results");
    assert(data.results.every(r => r.status === "discovery_error"),
      "all AZs must have discovery_error");
    assert(data.results.every(r => r.discovery_error && r.discovery_error.includes("configuration_error")),
      "all AZs must have configuration_error in discovery_error");
    await client.close();
  });
}

async function runIntegrationTests() {
  if (process.env.SKIP_INTEGRATION) {
    console.log("\n=== Integration tests: SKIPPED (SKIP_INTEGRATION is set) ===");
    return;
  }

  if (!process.env.HUAWEI_PROJECT_IDS_BY_REGION) {
    console.log("\n=== Integration tests: SKIPPED (HUAWEI_PROJECT_IDS_BY_REGION not set) ===");
    return;
  }

  console.log("\n=== Integration tests: real subprocess validation ===\n");

  await testT("INT1: FindEcsFlavorCandidates with real multi-region mapping", async () => {
    const client = await makeClient();

    const mapping = JSON.parse(process.env.HUAWEI_PROJECT_IDS_BY_REGION);
    const testRegion = Object.keys(mapping)[0];
    if (!testRegion) throw new Error("No regions in HUAWEI_PROJECT_IDS_BY_REGION");

    const res = await client.callTool({
      name: "FindEcsFlavorCandidates",
      arguments: {
        region: testRegion,
        targets: [{ availability_zone: `${testRegion}a` }],
        vcpus: 2,
        ram_gb: 4,
        timeout_ms: 30000
      }
    });
    const data = JSON.parse(res.content[0].text);
    assert(["OK", "PARTIAL", "ERROR"].includes(data.status),
      `status must be OK/PARTIAL/ERROR, got ${data.status}`);
    assert(data.results[0].status !== "discovery_error" || !data.results[0].discovery_error?.includes("configuration_error"),
      `${testRegion} should not have configuration_error when mapping exists`);
    await client.close();
  });
}

async function main() {
  await runUnitTests();
  await runIntegrationTests();
  console.log(`\nResults: ${passed} passed, ${failed} failed`);
  process.exit(failed > 0 ? 1 : 0);
}

main().catch((e) => {
  console.error("Test runner error:", e);
  process.exit(2);
});
