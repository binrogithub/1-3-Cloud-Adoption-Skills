#!/usr/bin/env node
import fs from "node:fs";

const [settingsPath, baseUrl, modelId = "glm-5.1"] = process.argv.slice(2);

if (!settingsPath || !baseUrl) {
  console.error("Usage: node merge-settings.mjs /path/to/settings.json https://endpoint/openai/v1 [model-id]");
  process.exit(2);
}

function readJson(file, fallback) {
  try {
    return JSON.parse(fs.readFileSync(file, "utf8"));
  } catch {
    return fallback;
  }
}

const settings = readJson(settingsPath, {});

settings["oaicopilot.baseUrl"] = baseUrl;
settings["oaicopilot.models"] = [
  {
    id: modelId,
    displayName: modelId,
    owned_by: "maas",
    apiMode: "openai",
    context_length: 128000,
    max_completion_tokens: 16000,
    max_tokens: 16000,
    temperature: 0,
    vision: false,
    include_reasoning_in_request: false,
  },
];
settings["oaicopilot.logLevel"] = "debug";
settings["oaicopilot.agentReadFileLine"] = 200;
settings["oaicopilot.glmToolCallCompat"] = true;

settings["github.copilot.chat.customOAIModels"] = {
  ...(settings["github.copilot.chat.customOAIModels"] ?? {}),
  [modelId]: {
    name: modelId,
    url: baseUrl,
    maxInputTokens: 128000,
    maxOutputTokens: 16000,
    toolCalling: true,
    vision: false,
    streaming: true,
  },
};

settings["github.copilot.chat.askAgent.model"] = modelId;
settings["github.copilot.chat.implementAgent.model"] = modelId;
settings["github.copilot.chat.exploreAgent.model"] = modelId;

fs.writeFileSync(settingsPath, `${JSON.stringify(settings, null, 2)}\n`);
