/**
 * Custom router for claude-code-router (CCR).
 * Loaded only when config.json sets:
 *   "CUSTOM_ROUTER_PATH": "/root/.claude-code-router/custom-router.js"
 *
 * ALLOW (pass-through) policy — these model names are never rejected:
 *   - any model matching /^claude-/  — required so Claude Code's internal
 *     calls always go through: foreground alias (claude-opus-4-6,
 *     claude-opus-*), background small models (claude-haiku-*,
 *     claude-3-5-haiku-*, ...), possible claude-sonnet-*;
 *   - the known-model list: glm-5.1, claude-glm1, anon-model-a,
 *     anon-model-b, Anonymous-Model, plus the short alias "opus";
 *   - requests without a string `model` field.
 *   Allowed models keep their existing behavior: the legacy explicit
 *   routes below are used only if their provider actually exists in the
 *   current config (see routeIfAvailable); otherwise the router returns
 *   null and CCR's built-in logic applies (Router.default / background /
 *   longContext — currently huawei-maas,glm-5.1).
 *
 * REJECT policy — any other (unknown / mistyped) model name is rejected
 * by returning a deliberately non-existent provider route:
 *   "unknown-model-rejected[<model>] valid: ...,<model>"
 * CCR then fails the request with a readable JSON error:
 *   HTTP 404 {"error":{"message":"Provider 'unknown-model-rejected[...]
 *   valid: glm-5.1|claude-glm1|...' not found..."}}
 * The error is per-request and does not affect subsequent requests.
 *
 * Why a fake provider instead of throwing an Error: this CCR version
 * wraps the custom router call in try/catch and, on a thrown error, only
 * logs "failed to load custom router: <msg>" and silently falls back to
 * built-in routing (verified experimentally and in dist/cli.js) — so a
 * throw can never reject a request.
 */

const fs = require("fs");

const KNOWN_MODELS = [
  "glm-5.1",
  "claude-glm1",
  "anon-model-a",
  "anon-model-b",
  "Anonymous-Model",
  "opus",
];

function providerExists(config, name) {
  return !!(
    config &&
    Array.isArray(config.Providers) &&
    config.Providers.some((p) => p && p.name === name)
  );
}

// Use a legacy explicit route only if its provider is still configured;
// otherwise fall back to CCR's built-in routing (return null).
function routeIfAvailable(config, route) {
  return providerExists(config, route.split(",")[0]) ? route : null;
}

module.exports = async function router(req, config) {
  const model = req.body && req.body.model;

  // No string model field: leave the decision to CCR's built-in routing.
  if (typeof model !== "string") {
    return null;
  }

  if (model === "Anonymous-Model") {
    let route;
    try {
      const assignment = fs
        .readFileSync(
          process.env.HOME + "/.claude-code-router/.session-model",
          "utf8"
        )
        .trim();
      route =
        assignment === "a"
          ? "LiteLLM Provider,anon-model-a"
          : "LiteLLM Provider,anon-model-b";
    } catch {
      route = "LiteLLM Provider,anon-model-b";
    }
    return routeIfAvailable(config, route);
  }

  if (model === "glm-5.1") {
    return routeIfAvailable(config, "LiteLLM Anthropic Adapter,glm-5.1");
  }

  if (model === "claude-glm1") {
    return routeIfAvailable(config, "LiteLLM Anthropic Adapter,claude-glm1");
  }

  if (
    model === "claude-opus-4-6" ||
    model === "opus" ||
    model.startsWith("claude-opus-")
  ) {
    return routeIfAvailable(
      config,
      "LiteLLM Anthropic Adapter,claude-opus-4-6"
    );
  }

  // Allowlist: claude-* aliases and known model names fall through to
  // CCR's built-in routing (Router.default / background / longContext).
  if (/^claude-/.test(model) || KNOWN_MODELS.includes(model)) {
    return null;
  }

  // Unknown / mistyped model name: route to a provider that cannot exist
  // so CCR returns a readable 404 JSON error instead of silently
  // answering via Router.default. (Throwing is swallowed by CCR.)
  const safe = model.replace(/,/g, ";");
  return (
    "unknown-model-rejected[" +
    safe +
    "] valid: glm-5.1|claude-glm1|anon-model-a|anon-model-b|Anonymous-Model|claude-*," +
    safe
  );
};
