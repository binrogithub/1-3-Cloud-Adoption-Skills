'use strict';

const http = require('http');
const fs = require('fs');
const path = require('path');

const SHIM_SYMBOL = Symbol.for('codex-glm.responses-shim.registered');
const requestQueue = [];
let queueRunning = false;
let lastUpstreamStartMs = 0;

function jsonResponse(reply, statusCode, payload) {
  reply.code(statusCode).header('content-type', 'application/json').send(payload);
}

function bearerToken(headerValue) {
  const value = Array.isArray(headerValue) ? headerValue[0] : headerValue;
  if (!value || typeof value !== 'string') return '';
  const match = value.match(/^Bearer\s+(.+)$/i);
  return match ? match[1].trim() : value.trim();
}

function expectedToken() {
  return process.env.CLAUDE_GLM_ROUTER_KEY || process.env.CODEX_GLM_ROUTER_KEY || 'codex-glm-local';
}

function traceEnabled() {
  return process.env.CODEX_GLM_TRACE === '1';
}

function traceDir() {
  return process.env.CODEX_GLM_TRACE_DIR || '/tmp/codex-glm-traces';
}

function traceValue(value) {
  if (Array.isArray(value)) return value.map(traceValue);
  if (!value || typeof value !== 'object') return value;
  const out = {};
  for (const [key, item] of Object.entries(value)) {
    if (/api[_-]?key|authorization|token|secret|password/i.test(key)) {
      out[key] = '[REDACTED]';
    } else {
      out[key] = traceValue(item);
    }
  }
  return out;
}

function writeTrace(label, payload) {
  if (!traceEnabled()) return;
  try {
    fs.mkdirSync(traceDir(), { recursive: true, mode: 0o700 });
    const safeLabel = label.replace(/[^a-z0-9_.-]+/gi, '_');
    const file = path.join(traceDir(), `${Date.now()}-${safeLabel}.json`);
    fs.writeFileSync(file, `${JSON.stringify(traceValue(payload), null, 2)}\n`, { mode: 0o600 });
  } catch (error) {
    console.error('codex-glm trace failed:', error.message);
  }
}

function collectText(value, parts) {
  if (value == null) return;
  if (typeof value === 'string') {
    parts.push(value);
    return;
  }
  if (Array.isArray(value)) {
    for (const item of value) collectText(item, parts);
    return;
  }
  if (typeof value !== 'object') return;

  if (typeof value.text === 'string') parts.push(value.text);
  if (typeof value.content === 'string') parts.push(value.content);
  if (typeof value.input_text === 'string') parts.push(value.input_text);
  if (typeof value.output_text === 'string') parts.push(value.output_text);
  if (Array.isArray(value.content)) collectText(value.content, parts);
  if (typeof value.output === 'string') parts.push(value.output);
  if (typeof value.result === 'string') parts.push(value.result);
  if (typeof value.summary === 'string') parts.push(value.summary);
}

function latestUserTextFromInput(input) {
  const items = Array.isArray(input) ? input : [{ role: 'user', content: input || '' }];
  for (let i = items.length - 1; i >= 0; i -= 1) {
    const item = items[i];
    if (!item || typeof item !== 'object' || item.role !== 'user') continue;
    const parts = [];
    collectText(item.content ?? item, parts);
    return parts.filter((text) => !text.includes('<system-reminder>')).join('\n');
  }
  return '';
}

function isSearchIntentInput(input) {
  return /搜索|新闻|最新|今天|今日|current|latest|today|news|search/i.test(latestUserTextFromInput(input));
}

function parseDataUrl(value) {
  if (typeof value !== 'string') return null;
  const match = value.match(/^data:([^;,]+);base64,(.+)$/);
  if (!match) return null;
  return { media_type: match[1], data: match[2] };
}

function normalizeImageBlock(block) {
  if (!block || typeof block !== 'object') return null;
  const type = block.type;
  if (type === 'image') return block;
  if (type !== 'input_image' && type !== 'image_url') return null;

  const imageUrl = block.image_url && typeof block.image_url === 'object'
    ? block.image_url.url
    : block.image_url || block.url;
  const dataUrl = parseDataUrl(imageUrl);
  if (dataUrl) {
    return {
      type: 'image',
      source: {
        type: 'base64',
        media_type: block.media_type || dataUrl.media_type,
        data: dataUrl.data,
      },
    };
  }
  if (imageUrl) {
    return { type: 'image_url', image_url: typeof block.image_url === 'object' ? block.image_url : { url: imageUrl } };
  }
  if (block.data) {
    return {
      type: 'image',
      source: {
        type: 'base64',
        media_type: block.media_type || block.mime_type || 'image/png',
        data: block.data,
      },
    };
  }
  return null;
}

function normalizeContentBlocks(content) {
  if (!Array.isArray(content)) return null;
  const blocks = [];
  for (const block of content) {
    if (typeof block === 'string') {
      if (block.trim()) blocks.push({ type: 'text', text: block });
      continue;
    }
    if (!block || typeof block !== 'object') continue;
    const image = normalizeImageBlock(block);
    if (image) {
      blocks.push(image);
      continue;
    }
    const text = block.text || block.input_text || block.output_text;
    if (typeof text === 'string' && text.trim()) {
      blocks.push({ type: 'text', text });
    }
  }
  return blocks;
}

function hasImageContent(input) {
  const items = Array.isArray(input) ? input : [{ role: 'user', content: input || '' }];
  return items.some((item) => {
    const blocks = normalizeContentBlocks(item && item.content);
    return Array.isArray(blocks) && blocks.some((block) => block.type === 'image' || block.type === 'image_url');
  });
}

function stringifyToolContent(value) {
  const parts = [];
  collectText(value, parts);
  if (parts.length > 0) return parts.join('\n');
  if (value == null) return '';
  if (typeof value === 'string') return value;
  return JSON.stringify(value);
}

function parseJsonMaybe(value) {
  if (value == null || value === '') return {};
  if (typeof value === 'object') return value;
  if (typeof value !== 'string') return { value };
  try {
    return JSON.parse(value);
  } catch {
    return { input: value };
  }
}

function responseItemType(item) {
  return String(item && item.type ? item.type : '');
}

function isToolCallItem(item) {
  const type = responseItemType(item);
  return type === 'function_call' ||
    type === 'custom_tool_call' ||
    type === 'local_shell_call' ||
    type === 'apply_patch_call' ||
    type === 'exec_command_call' ||
    type.endsWith('_tool_call');
}

function isToolResultItem(item) {
  const type = responseItemType(item);
  return type === 'function_call_output' ||
    type === 'custom_tool_call_output' ||
    type === 'local_shell_call_output' ||
    type === 'apply_patch_call_output' ||
    type === 'tool_result' ||
    type.endsWith('_tool_result');
}

function toolUseId(item) {
  return item.call_id || item.tool_call_id || item.tool_use_id || item.id || `call_${Date.now().toString(36)}`;
}

function toolCallName(item) {
  if (item.name) return String(item.name);
  const type = responseItemType(item);
  if (type === 'local_shell_call' || type === 'exec_command_call') return 'exec_command';
  if (type === 'apply_patch_call') return 'apply_patch';
  return 'function';
}

function toolCallInput(item) {
  if (item.arguments !== undefined) return parseJsonMaybe(item.arguments);
  if (item.input !== undefined) return parseJsonMaybe(item.input);
  if (item.action !== undefined) {
    const action = parseJsonMaybe(item.action);
    if (action.command || action.cmd) return { cmd: action.cmd || action.command };
    return action;
  }
  if (item.operation !== undefined) return parseJsonMaybe(item.operation);
  return {};
}

function responseToolCallToAnthropic(item) {
  return {
    type: 'tool_use',
    id: toolUseId(item),
    name: toolCallName(item),
    input: toolCallInput(item),
  };
}

function responseToolResultToAnthropic(item) {
  return {
    type: 'tool_result',
    tool_use_id: toolUseId(item),
    content: stringifyToolContent(item.output ?? item.content ?? item.result ?? item),
    is_error: item.is_error === true || item.error === true,
  };
}

function responsesInputToMessages(input) {
  const messages = [];
  const items = Array.isArray(input) ? input : [{ role: 'user', content: input || '' }];

  for (const item of items) {
    if (!item || typeof item !== 'object') continue;
    if (isToolCallItem(item)) {
      messages.push({ role: 'assistant', content: [responseToolCallToAnthropic(item)] });
      continue;
    }
    if (isToolResultItem(item)) {
      messages.push({ role: 'user', content: [responseToolResultToAnthropic(item)] });
      continue;
    }
    const role = item.role === 'assistant' ? 'assistant' : 'user';
    const blocks = normalizeContentBlocks(item.content);
    if (blocks && blocks.length > 0) {
      if (blocks.every((block) => block.type === 'text')) {
        messages.push({ role, content: blocks.map((block) => block.text).join('\n').trim() });
      } else {
        messages.push({ role, content: blocks });
      }
      continue;
    }
    const parts = [];
    collectText(item.content ?? item, parts);
    const text = parts.join('\n').trim();
    if (text) messages.push({ role, content: text });
  }

  if (messages.length === 0) {
    messages.push({ role: 'user', content: 'Respond with a concise text answer.' });
  }
  return messages;
}

function responsesToolToAnthropic(tool) {
  if (!tool || typeof tool !== 'object') return null;
  const name = tool.name || (tool.function && tool.function.name) || '';
  // exec_command: Codex sends type:"function" name:"exec_command", or legacy type:"local_shell"
  if (name === 'exec_command' || tool.type === 'local_shell') {
    return {
      name: 'exec_command',
      description: tool.description || 'Runs a command in a PTY, returning output or a session ID for ongoing interaction.',
      input_schema: {
        type: 'object',
        properties: {
          cmd: { type: 'string', description: 'Shell command to execute.' },
          justification: { type: 'string', description: 'User-facing approval question.' },
          login: { type: 'boolean', description: 'Whether to start a login shell.' },
          session_id: { type: 'string', description: 'Existing session ID to reuse.' },
        },
        required: ['cmd'],
      },
    };
  }
  // apply_patch: Codex sends type:"custom" name:"apply_patch", or legacy type:"apply_patch"
  // Convert to structured tool so GLM can actually use it (FREEFORM doesn't work with GLM)
  if (name === 'apply_patch' || tool.type === 'apply_patch') {
    return {
      name: 'apply_patch',
      description: tool.description || 'Use the `apply_patch` tool to edit files. Provide the patch content as a string in the "patch" parameter. The patch format is: *** Begin Patch\\n*** Add File: <path>\\n+<line1>\\n+<line2>\\n*** End Patch\\nOr for updates: *** Begin Patch\\n*** Update File: <path>\\n@@\\n-<old_line>\\n+<new_line>\\n*** End Patch',
      input_schema: {
        type: 'object',
        properties: {
          patch: { type: 'string', description: 'The patch content in Codex patch format.' },
        },
        required: ['patch'],
      },
    };
  }
  // Generic function tool
  if (tool.type === 'function' || tool.type === 'custom') {
    const fn = tool.function && typeof tool.function === 'object' ? tool.function : tool;
    if (!name) return null;
    return {
      name,
      description: fn.description || tool.description || '',
      input_schema: fn.parameters || fn.input_schema || tool.parameters || tool.input_schema || { type: 'object', properties: {} },
    };
  }
  return null;
}

function responsesToolChoiceToAnthropic(toolChoice) {
  if (!toolChoice) return undefined;
  if (typeof toolChoice === 'string') {
    if (toolChoice === 'auto' || toolChoice === 'none' || toolChoice === 'any') return { type: toolChoice };
    return { type: 'tool', name: toolChoice };
  }
  if (typeof toolChoice !== 'object') return undefined;
  if (toolChoice.type === 'function' && toolChoice.function?.name) return { type: 'tool', name: toolChoice.function.name };
  if (toolChoice.type === 'tool' && toolChoice.name) return { type: 'tool', name: toolChoice.name };
  if (toolChoice.type === 'auto' || toolChoice.type === 'none' || toolChoice.type === 'any') return { type: toolChoice.type };
  return undefined;
}

function anthropicBodyFromResponses(body) {
  const systemParts = [];
  collectText(body.instructions, systemParts);
  const tools = Array.isArray(body.tools) ? body.tools.map(responsesToolToAnthropic).filter(Boolean) : [];
  const searchIntent = isSearchIntentInput(body.input);
  const imageIntent = hasImageContent(body.input);
  if (searchIntent) {
    systemParts.push('Live search, when configured, is handled before the model call by the LiteLLM proxy. Use injected search results when present, include source URLs, and do not call search, fetch, or shell tools for this search request.');
  }
  if (imageIntent) {
    systemParts.push('This request contains image content. Preserve the image blocks for the upstream vision route; do not describe missing image access unless the upstream model reports an error.');
  }
  // GLM-5.1 cannot generate correct apply_patch format; add system hint to use exec_command instead
  if (tools.some(t => t.name === 'apply_patch')) {
    systemParts.push('IMPORTANT: To create or edit files, use the exec_command tool with shell commands (e.g., cat > file << EOF ... EOF, sed, etc.). Do NOT use the apply_patch tool — it is not supported.');
  }
  // Remove apply_patch from tools sent upstream since GLM cannot use it correctly
  const upstreamTools = searchIntent ? [] : tools.filter(t => t.name !== 'apply_patch');
  if (upstreamTools.length === 0) {
    systemParts.push('Return a plain text assistant response. Do not call tools.');
  }

  const anthropicBody = {
    model: body.model || process.env.MAAS_MODEL || 'glm-5.1',
    max_tokens: Number(process.env.MAAS_MAX_OUTPUT_TOKENS || body.max_output_tokens || 8192),
    stream: true,
    system: systemParts.join('\n\n').trim(),
    messages: responsesInputToMessages(body.input),
  };
  if (upstreamTools.length > 0) anthropicBody.tools = upstreamTools;
  const toolChoice = responsesToolChoiceToAnthropic(body.tool_choice);
  if (toolChoice) anthropicBody.tool_choice = toolChoice;
  return anthropicBody;
}

function queueIntervalMs() {
  const rps = Number(process.env.CODEX_GLM_UPSTREAM_RPS || '0');
  if (!Number.isFinite(rps) || rps <= 0) return 0;
  return Math.ceil(1000 / rps);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function enqueueUpstream(task) {
  return new Promise((resolve, reject) => {
    requestQueue.push({ task, resolve, reject });
    runQueue().catch((error) => {
      console.error('codex-glm queue failed:', error.message);
    });
  });
}

async function runQueue() {
  if (queueRunning) return;
  queueRunning = true;
  try {
    while (requestQueue.length > 0) {
      const item = requestQueue.shift();
      try {
        const interval = queueIntervalMs();
        const waitMs = Math.max(0, interval - (Date.now() - lastUpstreamStartMs));
        if (waitMs > 0) await sleep(waitMs);
        lastUpstreamStartMs = Date.now();
        item.resolve(await item.task());
      } catch (error) {
        item.reject(error);
      }
    }
  } finally {
    queueRunning = false;
    if (requestQueue.length > 0) runQueue().catch((error) => console.error('codex-glm queue failed:', error.message));
  }
}

function retryCount() {
  const value = Number(process.env.CODEX_GLM_429_RETRIES || '3');
  return Number.isFinite(value) && value >= 0 ? Math.floor(value) : 3;
}

function retryDelayMs(attempt, response) {
  const retryAfter = response && response.headers && response.headers['retry-after'];
  const retryAfterSeconds = Array.isArray(retryAfter) ? Number(retryAfter[0]) : Number(retryAfter);
  if (Number.isFinite(retryAfterSeconds) && retryAfterSeconds > 0) return retryAfterSeconds * 1000;
  const base = Number(process.env.CODEX_GLM_429_BASE_DELAY_MS || '1000');
  const jitter = Math.floor(Math.random() * 250);
  return Math.min(10000, base * Math.max(1, attempt)) + jitter;
}

async function requestJsonWithRetry(url, body, token) {
  let upstream;
  for (let attempt = 0; attempt <= retryCount(); attempt++) {
    upstream = await enqueueUpstream(() => requestJson(url, body, token));
    if (upstream.statusCode !== 429 || attempt === retryCount()) return upstream;
    upstream.resume();
    await sleep(retryDelayMs(attempt + 1, upstream));
  }
  return upstream;
}

function requestJson(url, body, token) {
  return new Promise((resolve, reject) => {
    const parsed = new URL(url);
    const payload = Buffer.from(JSON.stringify(body));
    const request = http.request({
      method: 'POST',
      hostname: parsed.hostname,
      port: parsed.port,
      path: parsed.pathname,
      headers: {
        authorization: `Bearer ${token}`,
        'content-type': 'application/json',
        accept: 'text/event-stream',
        'content-length': String(payload.length),
      },
    }, (response) => resolve(response));

    request.on('error', reject);
    request.write(payload);
    request.end();
  });
}

function writeSse(raw, eventName, payload) {
  raw.write(`event: ${eventName}\n`);
  raw.write(`data: ${JSON.stringify(payload)}\n\n`);
}

function extractPatchFromInput(input) {
  if (typeof input === 'string') return input;
  if (!input || typeof input !== 'object') return '';
  return input.patch || input.operation || input.content || '';
}

function extractCmdFromInput(input) {
  if (!input || typeof input !== 'object') return '';
  return input.cmd || input.command || '';
}

const PATCH_PATTERNS = [
  { re: /\*\*\* Begin Patch[\s\S]*?\*\*\* End Patch/, wrap: false },
  { re: /(?:^|\n)(--- [^\n]+\n\+\+\+ [^\n]+\n@@[\s\S]*?(?=\n[^ +-@]|\n$|$))/m, wrap: true },
  { re: /\*{4,} Original[\s\S]*?\*{4,} Replacement[\s\S]*?\*{4,} File:[^\n]*/m, wrap: true },
  { re: /(?:^|\n)(diff --git[\s\S]*?(?=\n\n|\n$|$))/m, wrap: true },
  { re: /\*{3,} [^\n]+\n--- [^\n]+\n\+{5,}\n[\s\S]*?(?=\n\n|\n$|$)/m, wrap: true },
  { re: /\+{4,} [^\n]+\n[+-][^\n]*([\s\S]*?(?=\n\n|\n$|$))/m, wrap: true },
];

function extractPatchesFromText(text) {
  if (!text || typeof text !== 'string') return [];
  const patches = [];
  const stripped = text.replace(/```diff\n?/g, '').replace(/```\n?/g, '');
  for (const { re, wrap } of PATCH_PATTERNS) {
    const match = stripped.match(re);
    if (match) {
      let patch = (match[1] || match[0]).trim();
      if (wrap && !patch.startsWith('*** Begin Patch')) {
        patch = '*** Begin Patch\n' + patch + '\n*** End Patch';
      }
      patches.push(patch);
    }
  }
  return patches;
}

function responseItemFromToolUse(toolUse, outputItemId) {
  const name = toolUse.name || 'function';
  const input = toolUse.input || {};
  const id = toolUse.id || outputItemId;
  if (name === 'local_shell' || name === 'exec_command') {
    const args = typeof input === 'string' ? input : JSON.stringify(input);
    return {
      id,
      type: 'function_call',
      status: 'completed',
      call_id: id,
      name: 'exec_command',
      arguments: args,
    };
  }
  if (name === 'apply_patch') {
    const patch = extractPatchFromInput(input);
    return {
      id,
      type: 'custom_tool_call',
      status: 'completed',
      call_id: id,
      name: 'apply_patch',
      operation: patch,
    };
  }
  return {
    id,
    type: 'function_call',
    status: 'completed',
    call_id: id,
    name,
    arguments: typeof input === 'string' ? input : JSON.stringify(input),
  };
}

function emitTextDelta(raw, responseId, outputItemId, delta, outputIndex, contentIndex) {
  if (!delta) return;
  writeSse(raw, 'response.output_text.delta', {
    type: 'response.output_text.delta',
    response_id: responseId,
    item_id: outputItemId,
    output_index: outputIndex,
    content_index: contentIndex,
    delta,
  });
}

function shouldStreamTextDeltas() {
  return process.env.CODEX_GLM_STREAM_DELTAS === '1';
}

function parseAnthropicEvent(rawEvent) {
  const lines = rawEvent.split(/\r?\n/);
  let eventName = '';
  const dataLines = [];
  for (const line of lines) {
    if (line.startsWith('event:')) eventName = line.slice(6).trim();
    if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart());
  }
  if (dataLines.length === 0) return null;
  const dataText = dataLines.join('\n');
  if (dataText === '[DONE]') return { eventName, data: '[DONE]' };
  try {
    return { eventName, data: JSON.parse(dataText) };
  } catch {
    return null;
  }
}

async function streamAnthropicAsResponses(upstream, reply, model) {
  const responseId = `resp_${Date.now().toString(36)}`;
  const outputItemId = `msg_${Date.now().toString(36)}`;
  const raw = reply.raw;
  let buffer = '';
  let outputText = '';
  let outputIndex = 0;
  let contentIndex = 0;
  let textStarted = false;
  const toolBlocks = new Map();
  const completedToolUses = [];

  reply.hijack();
  raw.writeHead(200, {
    'content-type': 'text/event-stream; charset=utf-8',
    'cache-control': 'no-cache',
    connection: 'keep-alive',
  });

  writeSse(raw, 'response.created', {
    type: 'response.created',
    response: {
      id: responseId,
      object: 'response',
      status: 'in_progress',
      model,
      output: [],
    },
  });
  const ensureTextStarted = () => {
    if (textStarted) return;
    textStarted = true;
    writeSse(raw, 'response.output_item.added', {
      type: 'response.output_item.added',
      response_id: responseId,
      output_index: outputIndex,
      item: {
        id: outputItemId,
        type: 'message',
        status: 'in_progress',
        role: 'assistant',
        content: [],
      },
    });
    writeSse(raw, 'response.content_part.added', {
      type: 'response.content_part.added',
      response_id: responseId,
      item_id: outputItemId,
      output_index: outputIndex,
      content_index: contentIndex,
      part: { type: 'output_text', text: '' },
    });
  };

  const processEvent = (rawEvent) => {
    const parsed = parseAnthropicEvent(rawEvent);
    if (!parsed || parsed.data === '[DONE]') return;
    const data = parsed.data;
    if (data.type === 'content_block_start' && data.content_block && data.content_block.type === 'tool_use') {
      toolBlocks.set(data.index, {
        id: data.content_block.id || `call_${Date.now().toString(36)}_${data.index}`,
        name: data.content_block.name || 'function',
        input: data.content_block.input || {},
        json: '',
        hasDelta: false,
      });
      return;
    }
    if (data.type === 'content_block_delta' && data.delta && data.delta.type === 'input_json_delta') {
      const block = toolBlocks.get(data.index);
      if (block) {
        block.hasDelta = true;
        block.json += data.delta.partial_json || '';
      }
      return;
    }
    if (data.type === 'content_block_stop' && toolBlocks.has(data.index)) {
      const block = toolBlocks.get(data.index);
      toolBlocks.delete(data.index);
      completedToolUses.push({
        id: block.id,
        name: block.name,
        input: block.hasDelta ? parseJsonMaybe(block.json) : block.input,
      });
      return;
    }
    if (data.type === 'content_block_delta' && data.delta && typeof data.delta.text === 'string') {
      ensureTextStarted();
      outputText += data.delta.text;
      if (shouldStreamTextDeltas()) {
        emitTextDelta(raw, responseId, outputItemId, data.delta.text, outputIndex, contentIndex);
      }
    }
    if (data.type === 'message_delta' && data.delta && typeof data.delta.stop_reason === 'string') {
      return;
    }
  };

  for await (const chunk of upstream) {
    buffer += chunk.toString('utf8');
    let boundary;
    while ((boundary = buffer.search(/\r?\n\r?\n/)) !== -1) {
      const rawEvent = buffer.slice(0, boundary);
      const match = buffer.slice(boundary).match(/^\r?\n\r?\n/);
      buffer = buffer.slice(boundary + (match ? match[0].length : 2));
      processEvent(rawEvent);
    }
  }
  if (buffer.trim()) processEvent(buffer.trimEnd());

  if (completedToolUses.length > 0) {
    for (const toolUse of completedToolUses) {
      const toolItem = responseItemFromToolUse(toolUse, `call_${Date.now().toString(36)}_${outputIndex}`);
      writeSse(raw, 'response.output_item.added', {
        type: 'response.output_item.added',
        response_id: responseId,
        output_index: outputIndex,
        item: { ...toolItem, status: 'in_progress' },
      });
      writeSse(raw, 'response.output_item.done', {
        type: 'response.output_item.done',
        response_id: responseId,
        output_index: outputIndex,
        item: toolItem,
      });
      outputIndex += 1;
    }
    writeSse(raw, 'response.completed', {
      type: 'response.completed',
      response: {
        id: responseId,
        object: 'response',
        status: 'completed',
        model,
        output: completedToolUses.map((toolUse, index) => responseItemFromToolUse(toolUse, `call_${Date.now().toString(36)}_${index}`)),
      },
    });
    raw.write('data: [DONE]\n\n');
    raw.end();
    return;
  }

  ensureTextStarted();

  const textPatches = extractPatchesFromText(outputText);
  if (textPatches.length > 0) {
    for (const patch of textPatches) {
      const patchItem = {
        id: `call_${Date.now().toString(36)}_${outputIndex}`,
        type: 'custom_tool_call',
        status: 'completed',
        call_id: `call_${Date.now().toString(36)}_${outputIndex}`,
        name: 'apply_patch',
        operation: patch,
      };
      writeSse(raw, 'response.output_item.added', {
        type: 'response.output_item.added',
        response_id: responseId,
        output_index: outputIndex,
        item: { ...patchItem, status: 'in_progress' },
      });
      writeSse(raw, 'response.output_item.done', {
        type: 'response.output_item.done',
        response_id: responseId,
        output_index: outputIndex,
        item: patchItem,
      });
      outputIndex += 1;
    }
    writeSse(raw, 'response.completed', {
      type: 'response.completed',
      response: {
        id: responseId,
        object: 'response',
        status: 'completed',
        model,
        output: textPatches.map((patch, index) => ({
          id: `call_${Date.now().toString(36)}_${index}`,
          type: 'custom_tool_call',
          status: 'completed',
          call_id: `call_${Date.now().toString(36)}_${index}`,
          name: 'apply_patch',
          operation: patch,
        })),
      },
    });
    raw.write('data: [DONE]\n\n');
    raw.end();
    return;
  }

  writeSse(raw, 'response.content_part.done', {
    type: 'response.content_part.done',
    response_id: responseId,
    item_id: outputItemId,
    output_index: outputIndex,
    content_index: contentIndex,
    part: { type: 'output_text', text: '' },
  });
  writeSse(raw, 'response.output_item.done', {
    type: 'response.output_item.done',
    response_id: responseId,
    output_index: outputIndex,
    item: {
      id: outputItemId,
      type: 'message',
      status: 'completed',
      role: 'assistant',
      content: [{ type: 'output_text', text: outputText }],
    },
  });
  writeSse(raw, 'response.completed', {
    type: 'response.completed',
    response: {
      id: responseId,
      object: 'response',
      status: 'completed',
      model,
      output: [],
    },
  });
  raw.write('data: [DONE]\n\n');
  raw.end();
}

function registerResponsesRoute(app) {
  if (!app || app[SHIM_SYMBOL]) return app;
  app[SHIM_SYMBOL] = true;

  app.get('/v1/responses', async (request, reply) => {
    const token = bearerToken(request.headers.authorization);
    if (token !== expectedToken()) {
      return jsonResponse(reply, 401, { error: { message: 'Unauthorized', type: 'authentication_error' } });
    }
    return jsonResponse(reply, 200, { message: 'codex-glm responses shim', status: 'ok' });
  });

  app.post('/v1/responses', async (request, reply) => {
    const token = bearerToken(request.headers.authorization);
    if (token !== expectedToken()) {
      return jsonResponse(reply, 401, { error: { message: 'Unauthorized', type: 'authentication_error' } });
    }

    writeTrace('responses-request', {
      headers: {
        host: request.headers.host,
        authorization: request.headers.authorization,
      },
      body: request.body || {},
    });

    let anthropicBody;
    try {
      anthropicBody = anthropicBodyFromResponses(request.body || {});
    } catch (error) {
      return jsonResponse(reply, error.statusCode || 400, {
        error: { message: error.message, type: 'invalid_request_error' },
      });
    }
    writeTrace('anthropic-upstream-request', anthropicBody);

    const host = request.headers.host || '127.0.0.1:3457';
    const upstreamUrl = `http://${host}/v1/messages`;
    let upstream;
    try {
      upstream = await requestJsonWithRetry(upstreamUrl, anthropicBody, token);
    } catch (error) {
      return jsonResponse(reply, 502, {
        error: { message: `Failed to call CCR /v1/messages: ${error.message}`, type: 'upstream_error' },
      });
    }

    if (upstream.statusCode < 200 || upstream.statusCode >= 300) {
      let payload = '';
      for await (const chunk of upstream) payload += chunk.toString('utf8');
      writeTrace('anthropic-upstream-error', { statusCode: upstream.statusCode, payload });
      return reply.code(upstream.statusCode).header('content-type', 'application/json').send(payload || '{}');
    }

    return streamAnthropicAsResponses(upstream, reply, anthropicBody.model);
  });

  return app;
}

module.exports = {
  register: registerResponsesRoute,
  _internals: {
    anthropicBodyFromResponses,
    responseItemFromToolUse,
    responsesToolToAnthropic,
    responsesInputToMessages,
    extractPatchesFromText,
    traceValue,
    latestUserTextFromInput,
    isSearchIntentInput,
    hasImageContent,
    normalizeContentBlocks,
  },
};
