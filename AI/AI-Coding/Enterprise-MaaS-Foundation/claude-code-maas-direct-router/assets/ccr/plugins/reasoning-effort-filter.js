class ReasoningEffortFilter {
  name = "reasoning-effort-filter";

  async transformRequestIn(body) {
    if (!body || typeof body !== "object") return body;
    const VALID = new Set(["xhigh", "high", "medium", "low", "minimal", "none"]);
    if (body.reasoning_effort !== undefined && !VALID.has(body.reasoning_effort)) {
      delete body.reasoning_effort;
    }
    // Also strip nested reasoning.effort if invalid
    if (body.reasoning && typeof body.reasoning === "object") {
      if (body.reasoning.effort !== undefined && !VALID.has(body.reasoning.effort)) {
        delete body.reasoning.effort;
        if (Object.keys(body.reasoning).length === 0) delete body.reasoning;
      }
    }
    return body;
  }
}

module.exports = ReasoningEffortFilter;
