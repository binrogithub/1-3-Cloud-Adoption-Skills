'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');

const bridge = require('../scripts/codex-forky-responses-bridge.cjs')._internals;
const fixture = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/responses-tool-request.json'), 'utf8'));

const body = bridge.anthropicBodyFromResponses(fixture);
assert.strictEqual(body.model, 'claude-sonnet-4-6');
assert.strictEqual(body.tools.length, 2);
assert.strictEqual(body.tools[0].name, 'lookup_symbol');
assert.strictEqual(body.tools[1].name, 'exec_command');
assert.deepStrictEqual(body.tool_choice, { type: 'auto' });
assert.strictEqual(body.messages[0].role, 'user');
assert.match(body.messages[0].content, /Find the main entrypoint/);
assert.strictEqual(body.messages[1].role, 'assistant');
assert.strictEqual(body.messages[1].content[0].type, 'tool_use');
assert.deepStrictEqual(body.messages[1].content[0].input, { name: 'main' });
assert.strictEqual(body.messages[2].role, 'user');
assert.strictEqual(body.messages[2].content[0].type, 'tool_result');
assert.strictEqual(body.messages[2].content[0].tool_use_id, 'call_lookup_1');

const defaultBody = bridge.anthropicBodyFromResponses({
  input: [{ role: 'user', content: [{ type: 'input_text', text: 'hi' }] }],
});
assert.strictEqual(defaultBody.model, 'claude-sonnet-4-6');
assert.match(defaultBody.system, /Return a plain text assistant response/);
assert.strictEqual(bridge.shouldRouteToForkyExecution({ input: [{ role: 'user', content: 'hi' }] }), false);
assert.strictEqual(bridge.shouldRouteToForkyExecution(fixture), true);
assert.deepStrictEqual(bridge.routeDecision({ input: [{ role: 'user', content: 'hi' }] }).route, 'codex-oauth');
assert.deepStrictEqual(bridge.routeDecision({ input: [{ role: 'user', content: 'hi' }] }).reason, 'no_tools');
assert.deepStrictEqual(bridge.routeDecision(fixture).reason, 'tools_no_image');
assert.strictEqual(bridge.isSearchIntentInput([
  { role: 'user', content: [{ type: 'input_text', text: 'Work only in the current directory and edit files.' }] },
]), false);
assert.strictEqual(bridge.isSearchIntentInput([
  { role: 'user', content: [{ type: 'input_text', text: 'Search the web for latest router news.' }] },
]), true);
assert.strictEqual(bridge.shouldRouteToForkyExecution({
  ...fixture,
  input: [
    {
      role: 'user',
      content: [
        { type: 'input_text', text: 'Describe this image.' },
        { type: 'input_image', image_url: 'data:image/png;base64,aGVsbG8=' },
      ],
    },
  ],
}), false);
assert.deepStrictEqual(bridge.routeDecision({
  ...fixture,
  input: [
    {
      role: 'user',
      content: [
        { type: 'input_text', text: 'Describe this image.' },
        { type: 'input_image', image_url: 'data:image/png;base64,aGVsbG8=' },
      ],
    },
  ],
}).reason, 'image');

const imageMessages = bridge.responsesInputToMessages([
  {
    role: 'user',
    content: [
      { type: 'input_text', text: 'Describe this image.' },
      { type: 'input_image', image_url: 'data:image/png;base64,aGVsbG8=' },
    ],
  },
]);
assert.strictEqual(imageMessages[0].content[0].type, 'text');
assert.strictEqual(imageMessages[0].content[1].type, 'image');
assert.strictEqual(imageMessages[0].content[1].source.media_type, 'image/png');
assert.strictEqual(imageMessages[0].content[1].source.data, 'aGVsbG8=');

const fnItem = bridge.responseItemFromToolUse({
  id: 'call_fn_1',
  name: 'lookup_symbol',
  input: { name: 'main' },
}, 'fallback');
assert.strictEqual(fnItem.type, 'function_call');
assert.strictEqual(fnItem.name, 'lookup_symbol');
assert.strictEqual(fnItem.arguments, '{"name":"main"}');

const patchItem = bridge.responseItemFromToolUse({
  id: 'call_patch_1',
  name: 'apply_patch',
  input: { patch: '*** Begin Patch\n*** End Patch\n' },
}, 'fallback');
assert.strictEqual(patchItem.type, 'custom_tool_call');
assert.strictEqual(patchItem.operation, '*** Begin Patch\n*** End Patch\n');

const redacted = bridge.traceValue({
  authorization: 'Bearer secret',
  nested: { token: 'secret', value: 1 },
});
assert.strictEqual(redacted.authorization, '[REDACTED]');
assert.strictEqual(redacted.nested.token, '[REDACTED]');
assert.strictEqual(redacted.nested.value, 1);

console.log('codex-forky bridge transform tests passed');
