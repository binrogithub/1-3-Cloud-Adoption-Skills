class ClaudeThinkingFilter {
  name = "claude-thinking-filter";
  logger = null;

  stripClaudeOnlyControls(body) {
    if (!body || typeof body !== "object") return body;

    delete body.thinking;
    delete body.context_management;

    if (body.output_config && typeof body.output_config === "object") {
      delete body.output_config.effort;
      if (Object.keys(body.output_config).length === 0) {
        delete body.output_config;
      }
    }

    // Strip reasoning_effort if not a valid OpenRouter value
    const VALID_REASONING_EFFORT = new Set(["xhigh", "high", "medium", "low", "minimal", "none"]);
    if (body.reasoning_effort !== undefined && !VALID_REASONING_EFFORT.has(body.reasoning_effort)) {
      delete body.reasoning_effort;
    }

    const stripContent = (message) => {
      if (!message || !Array.isArray(message.content)) return;
      message.content = message.content.filter((item) => {
        const type = item && item.type;
        return type !== "thinking" && type !== "redacted_thinking";
      });
      if (message.content.length === 0) message.content = "";
    };

    if (Array.isArray(body.messages)) body.messages.forEach(stripContent);
    if (Array.isArray(body.input)) body.input.forEach(stripContent);

    return body;
  }

  async transformRequestIn(body) {
    return this.stripClaudeOnlyControls(body);
  }

  async transformResponseOut(response) {
    if (!response || !response.body) return response;

    const decoder = new TextDecoder();
    const encoder = new TextEncoder();
    const blockTypes = new Map();
    const suppressedBlocks = new Set();
    let buffer = "";

    const emitSse = (controller, eventName, data) => {
      if (eventName) controller.enqueue(encoder.encode(`event: ${eventName}\n`));
      controller.enqueue(encoder.encode(`data: ${JSON.stringify(data)}\n\n`));
    };

    const processEvent = (controller, rawEvent) => {
      const lines = rawEvent.split(/\r?\n/);
      let eventName = "";
      const dataLines = [];
      for (const line of lines) {
        if (line.startsWith("event:")) eventName = line.slice(6).trim();
        if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
      }

      if (dataLines.length === 0) {
        controller.enqueue(encoder.encode(`${rawEvent}\n\n`));
        return;
      }

      const dataText = dataLines.join("\n");
      if (dataText === "[DONE]") {
        controller.enqueue(encoder.encode(`${rawEvent}\n\n`));
        return;
      }

      let data;
      try {
        data = JSON.parse(dataText);
      } catch {
        controller.enqueue(encoder.encode(`${rawEvent}\n\n`));
        return;
      }

      if (data.type === "content_block_start") {
        const blockType = data.content_block && data.content_block.type;
        blockTypes.set(data.index, blockType);
        if (blockType === "thinking" || blockType === "redacted_thinking") {
          suppressedBlocks.add(data.index);
          return;
        }
      }

      if (
        data.type === "content_block_delta" &&
        (data.delta?.type === "thinking_delta" ||
          data.delta?.type === "signature_delta") &&
        blockTypes.get(data.index) !== "thinking"
      ) {
        return;
      }

      if (suppressedBlocks.has(data.index)) {
        if (data.type === "content_block_stop") {
          suppressedBlocks.delete(data.index);
          blockTypes.delete(data.index);
        }
        return;
      }

      if (data.type === "content_block_stop") {
        blockTypes.delete(data.index);
      }

      emitSse(controller, eventName, data);
    };

    const stream = new TransformStream({
      transform(chunk, controller) {
        buffer += decoder.decode(chunk, { stream: true });
        let boundary;
        while ((boundary = buffer.search(/\r?\n\r?\n/)) !== -1) {
          const rawEvent = buffer.slice(0, boundary);
          const match = buffer.slice(boundary).match(/^\r?\n\r?\n/);
          buffer = buffer.slice(boundary + (match ? match[0].length : 2));
          processEvent(controller, rawEvent);
        }
      },
      flush(controller) {
        buffer += decoder.decode();
        if (buffer.trim()) processEvent(controller, buffer.trimEnd());
      },
    });

    return new Response(response.body.pipeThrough(stream), {
      status: response.status,
      statusText: response.statusText,
      headers: response.headers,
    });
  }
}

module.exports = ClaudeThinkingFilter;
