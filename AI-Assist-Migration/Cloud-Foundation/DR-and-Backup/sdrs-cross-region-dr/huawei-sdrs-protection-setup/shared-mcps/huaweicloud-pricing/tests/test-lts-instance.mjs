import assert from 'assert';

const RUN_LIVE = process.env.RUN_LIVE_API === 'true';
const BASE = 'http://127.0.0.1:3001';

async function callTool(name, args) {
  const resp = await fetch(`${BASE}/mcp`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call', params: { name, arguments: args } })
  });
  const data = await resp.json();
  return data;
}

async function testRenderLogFlow() {
  console.log('T1: Render LTS log flow product_infos');
  const result = await callTool('RenderProductInfosFromTemplate', {
    service: 'lts',
    template_id: 'lts-log-flow-payg',
    region: 'la-north-2',
    parameters: { quantity: 1, traffic_gb: 200 }
  });
  assert(result.result, 'Render should return result');
  console.log('  PASS');
}

async function testRenderLogIndex() {
  console.log('T2: Render LTS log index product_infos');
  const result = await callTool('RenderProductInfosFromTemplate', {
    service: 'lts',
    template_id: 'lts-log-index-payg',
    region: 'la-north-2',
    parameters: { quantity: 1, traffic_gb: 300 }
  });
  assert(result.result, 'Render should return result');
  console.log('  PASS');
}

async function testRenderLogStorage() {
  console.log('T3: Render LTS log storage product_infos');
  const result = await callTool('RenderProductInfosFromTemplate', {
    service: 'lts',
    template_id: 'lts-log-storage-payg',
    region: 'la-north-2',
    parameters: { quantity: 1, storage_gb: 500 }
  });
  assert(result.result, 'Render should return result');
  console.log('  PASS');
}

async function testLiveLogFlow() {
  if (!RUN_LIVE) { console.log('T4: SKIP (RUN_LIVE_API not set)'); return; }
  console.log('T4: Live BSS/OCE LTS log flow pricing');
  const result = await callTool('EstimateTemplateOnDemandPrice', {
    service: 'lts',
    template_id: 'lts-log-flow-payg',
    region: 'la-north-2',
    parameters: { quantity: 1, traffic_gb: 100 }
  });
  const text = JSON.stringify(result);
  assert(text.includes('5'), '100 GB log flow should cost ~USD 5.00');
  console.log('  PASS');
}

async function testLiveLogIndex() {
  if (!RUN_LIVE) { console.log('T5: SKIP (RUN_LIVE_API not set)'); return; }
  console.log('T5: Live BSS/OCE LTS log index pricing');
  const result = await callTool('EstimateTemplateOnDemandPrice', {
    service: 'lts',
    template_id: 'lts-log-index-payg',
    region: 'la-north-2',
    parameters: { quantity: 1, traffic_gb: 100 }
  });
  const text = JSON.stringify(result);
  assert(text.includes('8'), '100 GB log index should cost ~USD 8.00');
  console.log('  PASS');
}

async function testLiveLogStorage() {
  if (!RUN_LIVE) { console.log('T6: SKIP (RUN_LIVE_API not set)'); return; }
  console.log('T6: Live BSS/OCE LTS log storage pricing');
  const result = await callTool('EstimateTemplateOnDemandPrice', {
    service: 'lts',
    template_id: 'lts-log-storage-payg',
    region: 'la-north-2',
    parameters: { quantity: 1, storage_gb: 100 }
  });
  const text = JSON.stringify(result);
  assert(text.includes('0.0125'), '100 GB log storage should cost ~USD 0.0125');
  console.log('  PASS');
}

async function main() {
  console.log('=== LTS Template Tests ===');
  await testRenderLogFlow();
  await testRenderLogIndex();
  await testRenderLogStorage();
  await testLiveLogFlow();
  await testLiveLogIndex();
  await testLiveLogStorage();
  console.log('=== All LTS tests passed ===');
}

main().catch(e => { console.error(e); process.exit(1); });
