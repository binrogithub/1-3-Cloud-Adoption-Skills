class ClaudeWebSearchToResponses {
  constructor(options = {}) {
    this.options = options;
  }

  name = "claude-websearch-to-responses";
  logger = null;

  isSearchIntent(body) {
    const text = this.latestUserText(body).toLowerCase();
    return /搜索|新闻|最新|今天|今日|current|latest|today|news|search/.test(text);
  }

  isBashIntent(body) {
    const text = this.latestUserText(body).toLowerCase();
    return (
      /\bbash\b|\bshell\b|\bterminal\b|\bcommand\b|\brun\b|\bexecute\b|\binstall\b|\bdocker\b|\bcompose\b|\blogin\b|\.env\b|\blogs?\b|\bread\b|\bfile\b|\bcat\b|\brg\b/.test(text) ||
      /执行|运行|安装|命令|终端|排查|调查|查看|检查|日志|登录|配置|文件/.test(text)
    );
  }

  latestUserText(body) {
    const textParts = [];
    const addText = (text) => {
      if (!text || text.includes("<system-reminder>")) return;
      textParts.push(text);
    };
    const collect = (value) => {
      if (!value) return;
      if (typeof value === "string") {
        addText(value);
        return;
      }
      if (Array.isArray(value)) {
        value.forEach(collect);
        return;
      }
      if (typeof value === "object") {
        if (typeof value.text === "string") addText(value.text);
        if (typeof value.content === "string") addText(value.content);
        if (Array.isArray(value.content)) collect(value.content);
      }
    };

    const latestUserMessage = (messages) => {
      if (!Array.isArray(messages)) return undefined;
      for (let i = messages.length - 1; i >= 0; i -= 1) {
        if (messages[i] && messages[i].role === "user") return messages[i];
      }
      return undefined;
    };

    collect(latestUserMessage(body.messages));
    collect(latestUserMessage(body.input));

    return textParts.join("\n");
  }

  addSystemInstruction(body, content) {
    if (!body || !content) return;

    if (Array.isArray(body.input)) {
      body.input.unshift({ role: "system", content });
    }

    if (typeof body.system === "string") {
      body.system = `${body.system}\n\n${content}`;
    } else if (Array.isArray(body.system)) {
      body.system.push({ type: "text", text: content });
    } else if (Array.isArray(body.messages)) {
      body.system = [{ type: "text", text: content }];
    }
  }

  firstBashCommand(body) {
    const text = this.latestUserText(body);
    if (/litellm|\/root\/LiteLLM|litellm_proxy|docker-compose\.yml|\.env/i.test(text)) {
      return "cd /root/LiteLLM && printf '%s\\n' '--- .env keys ---' && sed -n '1,220p' .env | sed -E 's/(KEY|TOKEN|SECRET|PASSWORD|DATABASE_URL|SALT)=.*/\\\\1=<redacted>/I' && printf '%s\\n' '--- docker-compose.yml ---' && sed -n '1,220p' docker-compose.yml && printf '%s\\n' '--- litellm_proxy logs ---' && docker logs --tail 220 litellm_proxy 2>&1 | sed -E 's/(Authorization: Bearer |api_key=|key=|token=)[^ ,)}]+/\\\\1<redacted>/Ig'";
    }
    return null;
  }

  appendLatestUserText(body, text) {
    const appendToMessage = (message) => {
      if (!message || message.role !== "user") return false;
      if (typeof message.content === "string") {
        message.content += text;
        return true;
      }
      if (Array.isArray(message.content)) {
        message.content.push({ type: "text", text });
        return true;
      }
      return false;
    };

    for (const key of ["messages", "input"]) {
      if (!Array.isArray(body[key])) continue;
      for (let i = body[key].length - 1; i >= 0; i -= 1) {
        if (appendToMessage(body[key][i])) return;
      }
    }
  }

  normalizeTool(tool) {
    if (tool && tool.name === "Bash") {
      return {
        ...tool,
        description:
          "Run a shell command. The input object must include a non-empty command string.",
        input_schema: {
          type: "object",
          properties: {
            command: {
              type: "string",
              description: "Shell command to execute. Required and non-empty.",
            },
            description: {
              type: "string",
              description: "Brief description of what the command does.",
            },
            timeout: {
              type: "number",
              description: "Optional timeout in milliseconds.",
            },
          },
          required: ["command"],
          additionalProperties: false,
        },
      };
    }

    const fn = tool && tool.function;
    if (!fn || fn.name !== "WebSearch") {
      return tool;
    }

    return {
      ...tool,
      function: {
        ...fn,
        name: "litellm_web_search",
        description:
          "Search the web for current information using LiteLLM search tools.",
        parameters: {
          type: "object",
          properties: {
            query: {
              type: "string",
              description: "The search query to execute",
            },
          },
          required: ["query"],
        },
      },
    };
  }

  stripClaudeOnlyControls(body) {
    if (!body || typeof body !== "object") return;

    delete body.thinking;
    delete body.context_management;

    if (body.output_config && typeof body.output_config === "object") {
      delete body.output_config.effort;
      if (Object.keys(body.output_config).length === 0) {
        delete body.output_config;
      }
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
  }

  async transformRequestIn(body) {
    this.stripClaudeOnlyControls(body);

    const searchIntent = this.isSearchIntent(body);
    const bashIntent = !searchIntent && this.isBashIntent(body);
    const bashInstruction =
      "Only the Bash tool is available for this request. You must call Bash with a JSON input object that includes a non-empty command string. Never call Bash with an empty object. For file or log inspection, put the full shell pipeline in command, for example: cd /root/LiteLLM && sed -n '1,120p' docker-compose.yml && docker logs --tail 120 litellm_proxy.";

    if (body && Array.isArray(body.input)) {
      body.use_chat_completions_api = true;
    }

    if (bashIntent) {
      this.addSystemInstruction(body, bashInstruction);
      const firstCommand = this.firstBashCommand(body);
      if (firstCommand) {
        this.appendLatestUserText(
          body,
          `\n\nUse Bash to run this first command exactly:\n${firstCommand}`
        );
      }
    }

    if (!Array.isArray(body.tools)) {
      return body;
    }

    if (searchIntent) {
      body.tools = [];
    } else if (bashIntent) {
      body.tools = body.tools
        .filter((tool) => {
          const name = tool && (tool.name || (tool.function && tool.function.name));
          return name === "Bash";
        })
        .map((tool) => this.normalizeTool(tool));
    }

    return body;
  }

  async transformResponseOut(response) {
    if (!response || !response.body) return response;

    const decoder = new TextDecoder();
    const encoder = new TextEncoder();
    const pendingTools = new Map();
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

      if (
        data.type === "content_block_start" &&
        data.content_block?.type === "tool_use"
      ) {
        blockTypes.set(data.index, "tool_use");
        pendingTools.set(data.index, { eventName, data, partialJson: "" });
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
          data.delta?.type === "signature_delta")
      ) {
        if (blockTypes.get(data.index) !== "thinking") return;
      }

      if (suppressedBlocks.has(data.index)) {
        if (data.type === "content_block_stop") {
          suppressedBlocks.delete(data.index);
          blockTypes.delete(data.index);
        }
        return;
      }

      if (
        data.type === "content_block_delta" &&
        data.delta?.type === "input_json_delta" &&
        pendingTools.has(data.index)
      ) {
        pendingTools.get(data.index).partialJson += data.delta.partial_json || "";
        return;
      }

      if (data.type === "content_block_stop" && pendingTools.has(data.index)) {
        const pending = pendingTools.get(data.index);
        pendingTools.delete(data.index);
        blockTypes.delete(data.index);

        const startData = JSON.parse(JSON.stringify(pending.data));
        try {
          startData.content_block.input = pending.partialJson
            ? JSON.parse(pending.partialJson)
            : startData.content_block.input || {};
        } catch {
          startData.content_block.input = startData.content_block.input || {};
        }

        emitSse(controller, pending.eventName, startData);
        emitSse(controller, eventName, data);
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

module.exports = ClaudeWebSearchToResponses;
