'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');

const shim = require('../scripts/codex-glm-ccr-responses-shim.cjs')._internals;
const fixture = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/responses-tool-request.json'), 'utf8'));

const body = shim.anthropicBodyFromResponses(fixture);
assert.strictEqual(body.model, 'glm-5.1');
// apply_patch is filtered out upstream since GLM cannot use it correctly
assert.strictEqual(body.tools.length, 2);
assert.strictEqual(body.tools[0].name, 'lookup_symbol');
assert.strictEqual(body.tools[1].name, 'exec_command');
assert.deepStrictEqual(body.tool_choice, { type: 'auto' });
assert.strictEqual(body.messages[0].role, 'user');
assert.match(body.messages[0].content, /Find the main entrypoint/);
assert.strictEqual(body.messages[1].role, 'assistant');
assert.strictEqual(body.messages[1].content[0].type, 'tool_use');
assert.strictEqual(body.messages[1].content[0].name, 'lookup_symbol');
assert.deepStrictEqual(body.messages[1].content[0].input, { name: 'main' });
assert.strictEqual(body.messages[2].role, 'user');
assert.strictEqual(body.messages[2].content[0].type, 'tool_result');
assert.strictEqual(body.messages[2].content[0].tool_use_id, 'call_lookup_1');

const execCommandItem = shim.responseItemFromToolUse({
  id: 'call_shell_1',
  name: 'exec_command',
  input: { cmd: 'pwd' },
}, 'fallback');
assert.strictEqual(execCommandItem.type, 'function_call');
assert.strictEqual(execCommandItem.name, 'exec_command');
assert.ok(execCommandItem.arguments.includes('pwd'));

const localShellLegacyItem = shim.responseItemFromToolUse({
  id: 'call_shell_2',
  name: 'local_shell',
  input: { command: 'ls', working_directory: '/tmp' },
}, 'fallback');
assert.strictEqual(localShellLegacyItem.type, 'function_call');
assert.strictEqual(localShellLegacyItem.name, 'exec_command');

const patchItem = shim.responseItemFromToolUse({
  id: 'call_patch_1',
  name: 'apply_patch',
  input: { patch: '*** Begin Patch\n*** End Patch\n' },
}, 'fallback');
assert.strictEqual(patchItem.type, 'custom_tool_call');
assert.strictEqual(patchItem.name, 'apply_patch');
assert.strictEqual(patchItem.operation, '*** Begin Patch\n*** End Patch\n');

const fnItem = shim.responseItemFromToolUse({
  id: 'call_fn_1',
  name: 'lookup_symbol',
  input: { name: 'main' },
}, 'fallback');
assert.strictEqual(fnItem.type, 'function_call');
assert.strictEqual(fnItem.name, 'lookup_symbol');
assert.strictEqual(fnItem.arguments, '{"name":"main"}');

const redacted = shim.traceValue({
  authorization: 'Bearer secret',
  api_key: 'secret',
  nested: { token: 'secret', value: 1 },
});
assert.strictEqual(redacted.authorization, '[REDACTED]');
assert.strictEqual(redacted.api_key, '[REDACTED]');
assert.strictEqual(redacted.nested.token, '[REDACTED]');
assert.strictEqual(redacted.nested.value, 1);

const patches1 = shim.extractPatchesFromText(
  '*** Begin Patch\n*** a/file.txt\n--- b/file.txt\n+++ +hello\n*** End Patch'
);
assert.strictEqual(patches1.length, 1);
assert.ok(patches1[0].startsWith('*** Begin Patch'));

const patches2 = shim.extractPatchesFromText(
  '--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-old\n+new'
);
assert.strictEqual(patches2.length, 1);
assert.ok(patches2[0].includes('*** Begin Patch'));

const patches3 = shim.extractPatchesFromText('No patches here, just text.');
assert.strictEqual(patches3.length, 0);

const searchBody = shim.anthropicBodyFromResponses({
  model: 'glm-5.1',
  input: [{ role: 'user', content: [{ type: 'input_text', text: '搜索今天的新闻，只列1条。' }] }],
  tools: [
    {
      type: 'function',
      name: 'exec_command',
      parameters: { type: 'object', properties: { cmd: { type: 'string' } }, required: ['cmd'] },
    },
  ],
});
assert.ok(searchBody.system.includes('Live search'));
assert.strictEqual(searchBody.tools, undefined);

const imageInput = [
  {
    role: 'user',
    content: [
      { type: 'input_text', text: 'Describe this image.' },
      { type: 'input_image', image_url: 'data:image/png;base64,aGVsbG8=' },
    ],
  },
];
assert.strictEqual(shim.hasImageContent(imageInput), true);
const imageMessages = shim.responsesInputToMessages(imageInput);
assert.strictEqual(imageMessages[0].role, 'user');
assert.ok(Array.isArray(imageMessages[0].content));
assert.deepStrictEqual(imageMessages[0].content[0], { type: 'text', text: 'Describe this image.' });
assert.strictEqual(imageMessages[0].content[1].type, 'image');
assert.strictEqual(imageMessages[0].content[1].source.media_type, 'image/png');
assert.strictEqual(imageMessages[0].content[1].source.data, 'aGVsbG8=');

const remoteImageInput = [
  {
    role: 'user',
    content: [
      { type: 'input_text', text: 'What is here?' },
      { type: 'input_image', image_url: { url: 'https://example.com/image.jpg' } },
    ],
  },
];
const remoteImageMessages = shim.responsesInputToMessages(remoteImageInput);
assert.strictEqual(remoteImageMessages[0].content[1].type, 'image_url');
assert.strictEqual(remoteImageMessages[0].content[1].image_url.url, 'https://example.com/image.jpg');

console.log('shim transform tests passed');
