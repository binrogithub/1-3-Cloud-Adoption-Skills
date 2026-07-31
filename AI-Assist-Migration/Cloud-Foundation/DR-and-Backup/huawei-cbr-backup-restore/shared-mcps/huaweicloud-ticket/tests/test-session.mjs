import {
  saveSession,
  listServiceCategories,
  listIssueCategories,
  getTicketFormSchema,
  listRegions,
  checkCreatePrivilege,
  listTickets,
  getGlobalToken
} from "../src/ticket-api.mjs";

const FULL_COOKIES = "SessionID=MOCK_SESSION_ID; cbc-sid=MOCK_CBC_SID; HWWAFSESID=MOCK_HWWAFSESID; locale=en-us; usite=intl; agencyID=00000000-0000-0000-0000-000000000000; J_SESSION_ID=MOCK_J_SESSION_ID; cftk=MOCK_CFTK_TOKEN; J_SESSION_REGION=ap-southeast-1; SID=Set2";

async function test() {
  console.log("=== Ticket MCP Integration Test ===\n");

  const session = {
    cftk: "MOCK_CFTK_TOKEN",
    cookies: FULL_COOKIES,
    agencyId: "00000000-0000-0000-0000-000000000000",
    region: "cn-east-5",
    sourceId: "11111111-1111-1111-1111-111111111111",
    expiresAt: Date.now() + 8 * 60 * 60 * 1000
  };
  await saveSession(session);
  console.log("1. Session saved OK\n");

  console.log("2. list_service_categories:");
  const cats = await listServiceCategories(session);
  console.log(`   Total: ${cats.total}`);
  for (const c of cats.categories.filter(c => ["ECS","RDSforMySQL","OBS","VPC","ELB","EIP","Billing & Costs","Account"].some(n => c.name === n))) {
    console.log(`   - ${c.name} → id=${c.id.substring(0,8)}... sub_type=${c.sub_type_name}`);
  }

  console.log("\n3. list_issue_categories (ECS):");
  const issues = await listIssueCategories(session, "9e8913b629144ad4bfe6250cdea40f21");
  console.log(`   Total: ${issues.total}`);
  for (const i of issues.categories.slice(0, 5)) {
    console.log(`   - ${i.name}`);
  }

  console.log("\n4. get_ticket_form_schema (ECS Remote Login):");
  const schema = await getTicketFormSchema(session, "9e8913b629144ad4bfe6250cdea40f21", "14137db82bbc404d922efbb22e07dfb2", "-1");
  for (const f of schema.extends_params) {
    const optStr = f.options ? ` options=${JSON.stringify(f.options)}` : "";
    console.log(`   - ${f.name} (key=${f.key}, type=${f.type}, required=${f.required}${optStr})`);
  }

  console.log("\n5. list_regions (first 10):");
  const regions = await listRegions(session);
  console.log(`   Total: ${regions.total}`);
  for (const r of regions.regions.slice(0, 10)) {
    console.log(`   - ${r.name} (${r.id})`);
  }

  console.log("\n6. check_create_privilege:");
  const priv = await checkCreatePrivilege(session);
  console.log(`   Result: ${JSON.stringify(priv)}`);

  console.log("\n7. list_tickets:");
  const tickets = await listTickets(session);
  console.log(`   Total: ${tickets.total}, Count: ${tickets.count}`);

  console.log("\n8. PREPARE ticket payload (NOT submitting):");
  const payload = {
    business_type_id: "14137db82bbc404d922efbb22e07dfb2",
    product_category_id: "9e8913b629144ad4bfe6250cdea40f21",
    incident_sub_type_id: "-1",
    source_id: "11111111-1111-1111-1111-111111111111",
    simple_description: '<div class="osm-rich-text"><p>Cannot SSH to ECS. Connection timed out on port 22.</p></div>',
    accessory_ids: [],
    region_id: "cn-east-5",
    agreement_signed_record_id: 1688263,
    extends_map: {
      ECS_Instance_IP: "123.45.67.89",
      ECS_Instance_ID: "i-test123",
      ECS_Instance_RSP: "22",
      ECS_is_remote_port_open: "A",
      ECS_is_firewall_rules_open: "B",
      ECS_is_login_by_console: "B"
    },
    extension_map: { contactType: "0,2", remindCCEmail: "", isReceiveMsgRemind: 0 }
  };
  console.log(`   Payload ready with ${Object.keys(payload.extends_map).length} dynamic fields`);
  console.log(`   Product: ECS, Issue: Remote Login, Region: cn-east-5`);
  console.log(`   *** NOT SUBMITTED - Use create_ticket tool to submit ***`);

  console.log("\n=== ALL TESTS PASSED ===");
}

test().catch(e => {
  console.error("FAILED:", e.message);
  process.exit(1);
});
