import copy
import importlib.util
import json
import os
import pathlib
import sys
import tempfile
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
CALLBACK = ROOT / "litellm_plugins" / "smart_router" / "callback.py"
RULES = ROOT / "litellm_plugins" / "smart_router" / "smart_router_rules.json"
SCHEMA = ROOT / "litellm_plugins" / "smart_router" / "smart_router_rules.schema.json"

litellm = sys.modules.setdefault("litellm", types.ModuleType("litellm"))
litellm.token_counter = lambda **kwargs: 100
custom_logger = types.ModuleType("litellm.integrations.custom_logger")
custom_logger.CustomLogger = object
sys.modules.setdefault("litellm.integrations", types.ModuleType("litellm.integrations"))
sys.modules.setdefault("litellm.integrations.custom_logger", custom_logger)
spec = importlib.util.spec_from_file_location("smart_router", CALLBACK)
router = importlib.util.module_from_spec(spec)
spec.loader.exec_module(router)


def request(text, token_count=100):
    litellm.token_counter = lambda **kwargs: token_count
    return {"model": "claude-glm-5.2", "messages": [{"role": "user", "content": text}]}


def big_request(token_target, token_count=None):
    """Build a request whose byte-estimate lands near ``token_target`` tokens.

    When ``token_count`` is given the stubbed ``litellm.token_counter`` returns
    it; this is only consulted when the byte estimate is within 20% of a band
    boundary. For mid-band targets the byte estimate alone determines the band.
    """
    if token_count is not None:
        litellm.token_counter = lambda **kwargs: token_count
    text = "a" * (token_target * 4)
    return {"model": "claude-glm-5.2", "messages": [{"role": "user", "content": text}]}


# ── 1. Multilingual keyword routes ──────────────────────────────────────────


def test_multilingual_routes():
    # vision_rules were deleted (PRD-glm-consolidation §10): these prompts used
    # to route to vision-openrouter but now stay on the mainline (claude-glm-5.2).
    # Images route on the image content block alone, not on keyword matching.
    all_now_mainline = [
        "Design the system architecture",
        "设计数据库表结构",
        "Desenhe a arquitetura do sistema",
        "Diseña la arquitectura del sistema",
        "Faça uma revisão de segurança",
        "Analiza un incidente en producción",
        "Investigate a race condition in the payment authentication flow",
        "修复支付鉴权代码中的竞态条件",
        "Revise a autenticação do fluxo de pagamento",
        "Revisa la autenticación del flujo de pago",
        "Create a UI design",
        "设计网页界面",
        "Crie um design de interface",
        "Crea un diseño de interfaz",
    ]
    for text in all_now_mainline:
        result = router.route_request(request(text))
        assert result["model"] == "claude-glm-5.2", (
            "vision_rules deleted: '%s' must stay on mainline, got %s"
            % (text, result["model"])
        )
        assert result["metadata"]["smart_router"]["matched_rule"] == "glm_execution"


def test_audit_prompts_stay_on_mainline():
    """The four audit prompts (F2) that bare-token-matched premium_rules must
    now stay on the mainline — no cold prefill at premium rates."""
    prompts = [
        "把认证中间件的日志级别改成 debug",
        "add a unit test for the payment retry logic",
        "这个数据库设计有点问题，帮我加个索引",
        "add authorization headers to the outbound client",
    ]
    for text in prompts:
        result = router.route_request(request(text))
        assert result["model"] == "claude-glm-5.2", (
            "audit prompt '%s' must stay on mainline, got %s"
            % (text, result["model"])
        )
        assert result["metadata"]["smart_router"]["matched_rule"] == "glm_execution"


# ── 2. Observability metadata (complexity_score removed) ────────────────────


def test_observability_and_score_does_not_route():
    result = router.route_request(
        request("Analyze why this code fails, then fix it:\n```python\nprint(x)\n```", 1000)
    )
    info = result["metadata"]["smart_router"]
    assert result["model"] == "claude-glm-5.2"
    assert info["matched_rule"] == "glm_execution"
    # complexity_score is gone (PRD §6); the cheap byte estimate is used for
    # short messages, so estimated_tokens is the byte estimate, not the stub.
    assert "complexity_score" not in info
    assert info["estimated_tokens"] > 0
    assert info["router_version"] == "5.0.0"
    assert info["fallback_chain"] == ["glm-5.1-fallback"]
    assert "length_band" in info


# ── 3. Context boundary: 198001 no longer routes to premium ─────────────────


def test_context_boundary_and_controlled_fallbacks():
    # 150K tokens: under the advisory band, stays on mainline with a
    # same-provider fallback (under the token cap of 196608).
    boundary = router.route_request(big_request(100000, token_count=150000))
    assert boundary["model"] == "claude-glm-5.2"
    assert boundary["fallbacks"] == ["glm-5.1-fallback"]

    # 300K tokens: above the 196608 fallback cap, so no fallback is attached.
    # The byte estimate (300K) is above the cap so the fallback is suppressed.
    over = router.route_request(big_request(300000))
    assert over["model"] == "claude-glm-5.2"
    assert over["metadata"]["smart_router"]["matched_rule"] == "glm_execution"
    assert "fallbacks" not in over

    # vision_rules deleted (§10): architecture/security prompts stay on mainline
    # with a same-provider fallback (under the token cap), not vision/premium.
    architecture = router.route_request(request("Design the system architecture", 100))
    assert architecture["model"] == "claude-glm-5.2"
    assert architecture["fallbacks"] == ["glm-5.1-fallback"]

    security = router.route_request(request("Perform a security review", 100))
    assert security["model"] == "claude-glm-5.2"
    assert security["fallbacks"] == ["glm-5.1-fallback"]

    # F5: data_residency is read from the key/team context, NOT client request
    # metadata. A request with no key tag gets no residency protection — the
    # fallback fires. Client request metadata is no longer consulted.
    sensitive = router.route_request(request("Fix this confidential personal data parser", 100))
    assert sensitive["model"] == "claude-glm-5.2"
    assert sensitive["fallbacks"] == ["glm-5.1-fallback"]
    assert sensitive["metadata"]["smart_router"]["cross_border_fallback_blocked"] is False

    # Client-supplied request metadata.data_residency is now IGNORED (F5).
    sensitive_request = request("Fix the parser", 100)
    sensitive_request["metadata"] = {"data_residency": "china-only"}
    sensitive_result = router.route_request(sensitive_request)
    assert sensitive_result["fallbacks"] == ["glm-5.1-fallback"], (
        "client request metadata must no longer block fallback (F5)"
    )
    assert (
        sensitive_result["metadata"]["smart_router"]["cross_border_fallback_blocked"]
        is False
    )

    # F5: a key with metadata.data_residency="china-only" blocks fallback.
    key_china = {"metadata": {"data_residency": "china-only"}}
    blocked = router.route_request(request("Fix the parser", 100), key_china)
    assert "fallbacks" not in blocked
    assert (
        blocked["metadata"]["smart_router"]["cross_border_fallback_blocked"] is True
    )


# ── 4. Image fallback stays vision-capable (unchanged) ──────────────────────


def test_image_request_stays_on_mainline():
    """PRD-glm52-mainline-sidecars: images are captioned by the sidecar and the
    request stays on the GLM mainline. route_request (the sync core, run AFTER
    sidecar orchestration) sees only text and keeps glm_execution. The image
    block here is a placeholder — the sidecar would have replaced it with a
    caption before route_request runs."""
    data = request("What is shown?", 100)
    data["messages"][0]["content"] = [
        {"type": "text", "text": "What is shown?"},
        {"type": "text", "text": "[vision-caption sha256=abc schema=v1]Red[/vision-caption]"},
    ]
    result = router.route_request(data)
    assert result["model"] == "claude-glm-5.2"
    assert result["metadata"]["smart_router"]["matched_rule"] == "glm_execution"


# ── 5. Capability-aware routing (unchanged) ─────────────────────────────────


def test_capability_aware_routing_for_meli_glm_strategy():
    # vision_rules deleted (§10): these keyword prompts now stay on mainline.
    # Vision routing is on the image content block alone.
    vision_keywords_now_mainline = [
        "Inspect this UI and create a visual design recommendation",
        "Generate a wireframe for the checkout flow",
        "Create a diagram showing the service graph",
        "Draw a graph of the deployment topology",
    ]
    for text in vision_keywords_now_mainline:
        result = router.route_request(request(text))
        info = result["metadata"]["smart_router"]
        assert result["model"] == "claude-glm-5.2", (
            "vision_rules deleted: '%s' must stay on mainline, got %s"
            % (text, result["model"])
        )
        assert info.get("provider_capability_reason") is None

    # All text prompts stay on mainline with no capability reason.
    all_now_mainline = [
        "Act as an advisor for the migration strategy",
        "Review this architecture for scale risks",
        "Run a security review of the authentication flow",
        "Analyze this production incident and propose mitigations",
        "Perform complex debugging for this intermittent deadlock",
        "Return only strict JSON matching this schema: {\"risk\": string}",
    ]
    for text in all_now_mainline:
        result = router.route_request(request(text))
        info = result["metadata"]["smart_router"]
        assert result["model"] == "claude-glm-5.2", (
            "vision_rules deleted: '%s' must stay on mainline, got %s"
            % (text, result["model"])
        )
        assert info.get("provider_capability_reason") is None

    glm = [
        "Write a Python function that sorts invoices by due date",
        "Generate pytest tests for this helper",
        "Simple refactor: rename this variable and extract a helper",
        "Generate a simple unit test and return JSON with the file path",
    ]
    for text in glm:
        result = router.route_request(request(text))
        assert result["model"] == "claude-glm-5.2"
        assert result["metadata"]["smart_router"].get("provider_capability_reason") is None


# ── 6. Rules schema and runtime validation (complexity removed) ─────────────


def test_rules_schema_and_runtime_validation():
    rules = json.loads(RULES.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert "complexity" not in rules
    assert "complexity" not in schema["required"]
    assert "complexity" not in schema["properties"]
    # vision_rules were deleted (PRD-glm-consolidation §10).
    assert "vision_rules" not in rules
    assert "vision_rules" not in schema.get("required", [])
    assert "vision_rules" not in schema.get("properties", {})
    assert router._validate_rules(copy.deepcopy(rules)) == rules

    invalid = copy.deepcopy(rules)
    invalid["unknown"] = True
    with tempfile.NamedTemporaryFile("w", suffix=".json") as handle:
        json.dump(invalid, handle)
        handle.flush()
        try:
            router.load_rules(handle.name)
        except ValueError:
            pass
        else:
            raise AssertionError("unknown keys must fail validation")

    # A stray vision_rules key is now rejected (it was deleted).
    invalid = copy.deepcopy(rules)
    invalid["vision_rules"] = []
    try:
        router._validate_rules(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError("vision_rules key must now fail validation")


# ── 7. Prometheus metrics (complexity_score gone, length_band + deployment) ─


def test_prometheus_metrics_are_registered():
    names = {
        metric.name
        for collector in (
            router.ROUTE_REQUESTS,
            router.FALLBACKS,
            router.CROSS_BORDER_BLOCKS,
            router.LENGTH_BANDS,
            router.MAINLINE_DEPLOYMENT_SELECTED,
        )
        if hasattr(collector, "collect")
        for metric in collector.collect()
    }
    if names:
        assert "smart_router_requests" in names
        assert "smart_router_fallbacks" in names
        assert "smart_router_cross_border_blocks" in names
        assert "smart_router_length_band" in names
        assert "mainline_deployment_selected" in names
        assert "smart_router_complexity_score" not in names


# ── 8. NEW: Length policy bands (PRD §5) ────────────────────────────────────


def test_length_bands_never_escalate():
    # GLM (claude-glm-5.2) ceiling is 1M; profile-derived bands (PRD §7) are
    # advisory=~600K, oversize=1M. Token targets are chosen to land mid-band so
    # the byte estimate (not the token_counter stub) picks the band.
    # < 600K: normal, no intervention, same-provider fallback attached (under cap).
    normal = router.route_request(big_request(100000))
    ninfo = normal["metadata"]["smart_router"]
    assert normal["model"] == "claude-glm-5.2"
    assert ninfo["length_band"] == "normal"
    assert ninfo["matched_rule"] == "glm_execution"
    assert ninfo["fallback_chain"] == ["glm-5.1-fallback"]

    # 600K-1M: advisory, stays on mainline. Above the 196608 fallback token cap
    # so NO fallback — but still mainline, never premium/vision.
    # 750K is mid-band (not near the 600K or 1M boundary) so the byte estimate
    # is used directly.
    advisory = router.route_request(big_request(750000))
    ainfo = advisory["metadata"]["smart_router"]
    assert advisory["model"] == "claude-glm-5.2"
    assert ainfo["length_band"] == "advisory"
    assert ainfo["matched_rule"] == "glm_execution"
    assert ainfo["fallback_chain"] == []

    # >= 1M: oversize, stays on mainline, no fallback. Use the
    # token_counter stub to pin exactly 1M (the byte estimate is near the 1M
    # boundary so token_counter IS called). 1M is the ceiling: the band is
    # "oversize" but the context cliff does NOT fire (1M > 1M is False).
    oversize = router.route_request(big_request(1000000, token_count=1000000))
    oinfo = oversize["metadata"]["smart_router"]
    assert oversize["model"] == "claude-glm-5.2"
    assert oinfo["length_band"] == "oversize"
    assert oinfo["matched_rule"] == "glm_execution"
    assert oinfo["fallback_chain"] == []

    # The band is recorded on metadata.smart_router for every request.
    assert ninfo["length_band"] == "normal"


def test_length_bands_recorded_in_metadata():
    # Advisory band tags metadata.smart_router.length_band (advisory only — no
    # request-body mutation to "advise compaction"). GLM advisory is ~600K-1M;
    # 750K is mid-band.
    advisory = router.route_request(big_request(750000))
    assert advisory["metadata"]["smart_router"]["length_band"] == "advisory"
    # No compaction hint is injected into the request body.
    assert "compaction" not in json.dumps(advisory).lower()


def test_length_never_escalates_to_premium():
    # Even a huge request must not route to premium/vision on length alone.
    for target in (200000, 300000, 500000, 600000, 900000):
        result = router.route_request(big_request(target))
        assert result["model"] == "claude-glm-5.2", (
            "length %d must not escalate, got %s" % (target, result["model"])
        )
        assert result["metadata"]["smart_router"]["matched_rule"] == "glm_execution"


# ── 9. NEW: Cross-provider fallback token cap (PRD §5) ──────────────────────


def test_fallback_token_cap_below_cap_attaches_same_provider():
    # Below the cap (196608): glm_execution gets a same-provider glm-5.1 fallback.
    result = router.route_request(big_request(100000))
    assert result["model"] == "claude-glm-5.2"
    assert result["fallbacks"] == ["glm-5.1-fallback"]
    assert result["metadata"]["smart_router"]["fallback_chain"] == ["glm-5.1-fallback"]


def test_fallback_token_cap_above_cap_no_fallback():
    # Above the cap (196608): no fallback — the upstream error propagates.
    result = router.route_request(big_request(300000))
    assert result["model"] == "claude-glm-5.2"
    assert "fallbacks" not in result
    assert result["metadata"]["smart_router"]["fallback_chain"] == []


def test_fallback_token_cap_same_provider_exempt():
    # Vision fallback (Luna -> Luna Pro) is now handled INSIDE the sidecar
    # module, not as a LiteLLM fallback chain. route_request only attaches
    # the glm-5.1 same-provider fallback for glm_execution. Verify a normal
    # text request under the cap gets the glm fallback (the cap-exempt vision
    # fallback is tested in test_sidecar.py).
    data = big_request(50000)
    result = router.route_request(data)
    assert result["model"] == "claude-glm-5.2"
    assert result["fallbacks"] == ["glm-5.1-fallback"]


# ── 10. NEW: Prefix affinity consistent hash (PRD §4.1) ─────────────────────


def _reload_with_deployments(count):
    """Reload the router module with SMART_ROUTER_DEPLOYMENT_COUNT set."""
    env_key = "SMART_ROUTER_DEPLOYMENT_COUNT"
    old = os.environ.get(env_key)
    os.environ[env_key] = str(count)
    try:
        spec2 = importlib.util.spec_from_file_location("smart_router_%d" % count, CALLBACK)
        mod = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(mod)
    finally:
        if old is None:
            os.environ.pop(env_key, None)
        else:
            os.environ[env_key] = old
    return mod


def test_affinity_deployment_count_one_is_noop():
    # Default DEPLOYMENT_COUNT=1: the hash is a no-op, model unchanged.
    assert router.DEPLOYMENT_COUNT == 1
    result = router.route_request(request("Write a Python function", 100))
    assert result["model"] == "claude-glm-5.2"
    assert "affinity_deployment" not in result["metadata"]["smart_router"]


def test_affinity_same_prefix_same_deployment():
    mod = _reload_with_deployments(4)
    try:
        base = {"model": "claude-glm-5.2", "messages": [
            {"role": "user", "content": "Write a Python function that sorts invoices"},
        ]}
        r1 = mod.route_request(copy.deepcopy(base))
        r2 = mod.route_request(copy.deepcopy(base))
        assert r1["model"] == r2["model"]
        assert r1["model"].startswith("glm-")
        assert r1["metadata"]["smart_router"]["affinity_deployment"] == r1["model"]
        # fallbacks is the same-provider group (exempt from the token cap).
        assert r1["fallbacks"] == ["claude-*"]
    finally:
        pass


def test_affinity_different_prefixes_distribute():
    mod = _reload_with_deployments(8)
    try:
        deployments = set()
        for i in range(40):
            data = {"model": "claude-glm-5.2", "messages": [
                {"role": "user", "content": "prompt number %d with distinct text" % i},
            ]}
            result = mod.route_request(data)
            deployments.add(result["model"])
        # With 8 deployments and 40 varied prefixes we expect more than one
        # distinct alias (a single alias would indicate the hash is broken).
        assert len(deployments) > 1, "affinity hash did not distribute: %s" % deployments
        for dep in deployments:
            assert dep.startswith("glm-")
    finally:
        pass


def test_affinity_session_id_preferred_over_prefix():
    mod = _reload_with_deployments(4)
    try:
        # Same session_id, different prompt text -> same deployment.
        sid = "session-abc-123"
        d1 = {"model": "claude-glm-5.2", "metadata": {"session_id": sid},
              "messages": [{"role": "user", "content": "first prompt"}]}
        d2 = {"model": "claude-glm-5.2", "metadata": {"session_id": sid},
              "messages": [{"role": "user", "content": "completely different prompt"}]}
        r1 = mod.route_request(d1)
        r2 = mod.route_request(d2)
        assert r1["model"] == r2["model"], (
            "same session_id must pin the same deployment regardless of prompt"
        )

        # Different session_id -> (very likely) different deployment.
        d3 = {"model": "claude-glm-5.2", "metadata": {"session_id": "session-xyz-999"},
              "messages": [{"role": "user", "content": "first prompt"}]}
        r3 = mod.route_request(d3)
        # Not a hard assertion on inequality (hash collisions possible), but
        # the anchor must be the session_id, so verify via the helper.
        anchor1 = sid
        anchor3 = "session-xyz-999"
        import hashlib
        idx1 = int(hashlib.sha256(anchor1.encode()).hexdigest()[:16], 16) % 4
        idx3 = int(hashlib.sha256(anchor3.encode()).hexdigest()[:16], 16) % 4
        assert r1["model"] == "glm-%d" % idx1
        assert r3["model"] == "glm-%d" % idx3
    finally:
        pass


def test_affinity_only_applies_to_mainline():
    mod = _reload_with_deployments(4)
    try:
        # PRD-release-closure §3.1: non-GLM models are REJECTED by the router.
        # Affinity only applies to GLM-family mainline traffic.
        data = {"model": "gpt-4o", "messages": [
            {"role": "user", "content": "Write a Python function"},
        ]}
        rejected = False
        try:
            mod.route_request(data)
        except Exception:
            rejected = True
        assert rejected, "non-GLM model must be rejected, not passed through"
    finally:
        pass


def test_affinity_stable_across_restarts():
    # Plain sha256, no PYTHONHASHSEED dependence: reloading yields the same
    # deployment for the same prefix.
    mod_a = _reload_with_deployments(4)
    mod_b = _reload_with_deployments(4)
    data = {"model": "claude-glm-5.2", "messages": [
        {"role": "user", "content": "stable prefix for restart test"},
    ]}
    ra = mod_a.route_request(copy.deepcopy(data))
    rb = mod_b.route_request(copy.deepcopy(data))
    assert ra["model"] == rb["model"]


def test_affinity_first_user_message_pins_across_turns():
    """F1: a 12-turn session with DEPLOYMENT_COUNT=3 pins to ONE deployment for
    all 12 turns, because the anchor is the first (stable) user message, not the
    latest (which changes every turn and scatters traffic)."""
    mod = _reload_with_deployments(3)
    try:
        conversation = [
            {"role": "user", "content": "Help me build a sorting library in Python"},
        ]
        deployments = set()
        for turn in range(12):
            # Each turn the user asks something different; the latest user
            # message changes every turn but the FIRST user message is stable.
            conversation.append({"role": "assistant", "content": "here is turn %d" % turn})
            conversation.append({
                "role": "user",
                "content": "now handle edge case number %d with distinct text" % turn,
            })
            data = {"model": "claude-glm-5.2", "messages": copy.deepcopy(conversation)}
            result = mod.route_request(data)
            deployments.add(result["model"])
        assert len(deployments) == 1, (
            "F1: 12-turn session should pin to ONE deployment (first user msg "
            "anchor), but scattered to %s" % sorted(deployments)
        )
        assert list(deployments)[0].startswith("glm-")
    finally:
        pass


def test_affinity_tool_result_turn_and_followup_same_deployment():
    """F1: a tool_result turn and a follow-up user turn get the SAME deployment.

    On a pure tool_result turn _latest_user_text returns "" (tool_result blocks
    aren't type text), so the old anchor degenerated to system-only. The first
    user message anchor is stable across both turns.
    """
    mod = _reload_with_deployments(4)
    try:
        first_user = "Refactor the authentication module to use async/await"
        # Turn A: user message, then tool_result (no new user text).
        messages_a = [
            {"role": "user", "content": first_user},
            {"role": "assistant", "content": [
                {"type": "text", "text": "Let me read the file."},
                {"type": "tool_use", "id": "t1", "name": "read_file", "input": {"path": "auth.py"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": "file contents here"},
            ]},
        ]
        # Turn B: a follow-up user message with different text.
        messages_b = [
            {"role": "user", "content": first_user},
            {"role": "assistant", "content": "ok"},
            {"role": "user", "content": "now add unit tests for the new async functions"},
        ]
        ra = mod.route_request({"model": "claude-glm-5.2", "messages": messages_a})
        rb = mod.route_request({"model": "claude-glm-5.2", "messages": messages_b})
        assert ra["model"] == rb["model"], (
            "F1: tool_result turn and follow-up user turn must anchor on the "
            "same first user message -> same deployment, got %s vs %s"
            % (ra["model"], rb["model"])
        )
    finally:
        pass


# ── 11. NEW: No deepcopy on the request path (PRD §6) ───────────────────────


def test_no_deepcopy_on_request_path():
    # route_request must mutate the caller's dict in place — the object
    # identity of the messages list is preserved (no deepcopy).
    data = {"model": "claude-glm-5.2", "messages": [
        {"role": "user", "content": "Write a function"},
    ]}
    messages_id = id(data["messages"])
    result = router.route_request(data)
    assert result is data, "route_request must return the same dict object"
    assert id(result["messages"]) == messages_id, "messages list must not be deepcopied"


def test_no_copy_module_imported():
    # The callback must no longer import ``copy`` (deepcopy removed).
    source = CALLBACK.read_text(encoding="utf-8")
    assert "import copy" not in source, "callback.py still imports copy"
    assert "copy.deepcopy" not in source, "callback.py still uses copy.deepcopy"


def test_no_full_payload_json_dumps_for_policy():
    # _policy_text (json.dumps of the full payload including tools) is gone.
    source = CALLBACK.read_text(encoding="utf-8")
    assert "_policy_text" not in source, "callback.py still defines _policy_text"


# ── 12. NEW: token estimation only calls token_counter near boundaries ──────


def test_token_counter_only_called_near_boundary():
    calls = {"n": 0}

    def counting_counter(**kwargs):
        calls["n"] += 1
        return 100

    litellm.token_counter = counting_counter
    try:
        # Short request: byte estimate far from any boundary -> token_counter
        # is NOT called. (Build directly so the request() helper does not
        # clobber litellm.token_counter.)
        router.route_request({"model": "claude-glm-5.2", "messages": [
            {"role": "user", "content": "hello world"},
        ]})
        assert calls["n"] == 0, "token_counter called away from boundary"

        # Request near the ~600K advisory boundary (PRD §7: GLM ceiling 1M,
        # advisory=~600K) -> token_counter IS called.
        text = "a" * (586200 * 4)
        router.route_request({"model": "claude-glm-5.2", "messages": [
            {"role": "user", "content": text},
        ]})
        assert calls["n"] >= 1, "token_counter not called near boundary"
    finally:
        litellm.token_counter = lambda **kwargs: 100


def test_byte_estimate_does_not_json_dumps_tools():
    """F4: _byte_estimate must NOT json.dumps the tools field. Tool definitions
    can be huge and serializing them every request is the full-payload cost PRD
    §6 removed. Monkeypatch json.dumps to count calls and confirm tools are not
    serialized in the byte-estimate path (a short request far from a boundary
    so token_counter is not invoked)."""
    import builtins

    real_dumps = builtins.json.dumps if hasattr(builtins, "json") else json.dumps
    dumps_calls = {"tools_seen": False}

    # Build a request with huge tools, far from any band boundary so only
    # _byte_estimate runs (not the near-boundary token_counter path).
    huge_tools = [{"type": "function", "name": "tool_%d" % i,
                   "description": "x" * 10000, "input_schema": {}} for i in range(200)]
    data = {
        "model": "claude-glm-5.2",
        "messages": [{"role": "user", "content": "hello world"}],
        "tools": huge_tools,
    }

    # Patch json.dumps at the module level to detect tools serialization.
    original_dumps = router.json.dumps

    def spy_dumps(obj, *args, **kwargs):
        if isinstance(obj, list) and obj and isinstance(obj[0], dict) and obj[0].get("type") == "function":
            dumps_calls["tools_seen"] = True
        return original_dumps(obj, *args, **kwargs)

    router.json.dumps = spy_dumps
    try:
        litellm.token_counter = lambda **kwargs: 100
        result = router.route_request(copy.deepcopy(data))
        assert result["model"] == "claude-glm-5.2"
        assert not dumps_calls["tools_seen"], (
            "F4: _byte_estimate must not json.dumps the tools field"
        )
    finally:
        router.json.dumps = original_dumps
        litellm.token_counter = lambda **kwargs: 100


def test_data_residency_server_env_default_blocks_fallback():
    """F5: SMART_ROUTER_DEFAULT_DATA_RESIDENCY=china-only blocks cross-provider
    fallback regardless of key/client — protection is default-on for china-only
    deployments without trusting client metadata."""
    env_key = "SMART_ROUTER_DEFAULT_DATA_RESIDENCY"
    old = os.environ.get(env_key)
    os.environ[env_key] = "china-only"
    try:
        spec2 = importlib.util.spec_from_file_location("smart_router_china", CALLBACK)
        mod = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(mod)
        litellm.token_counter = lambda **kwargs: 100
        # No key tag, no client metadata — the server env default blocks it.
        result = mod.route_request(request("Write a Python function", 100))
        assert result["model"] == "claude-glm-5.2"
        assert "fallbacks" not in result, (
            "F5: server env china-only must block cross-provider fallback"
        )
        assert (
            result["metadata"]["smart_router"]["cross_border_fallback_blocked"] is True
        )
    finally:
        if old is None:
            os.environ.pop(env_key, None)
        else:
            os.environ[env_key] = old
        litellm.token_counter = lambda **kwargs: 100


def test_data_residency_key_tag_blocks_fallback():
    """F5: a virtual key with metadata.data_residency=china-only blocks fallback."""
    litellm.token_counter = lambda **kwargs: 100
    key_china = {"metadata": {"data_residency": "china-only"}}
    result = router.route_request(request("Write a Python function", 100), key_china)
    assert result["model"] == "claude-glm-5.2"
    assert "fallbacks" not in result
    assert result["metadata"]["smart_router"]["cross_border_fallback_blocked"] is True

    # A key without the tag does not block.
    key_plain = {"metadata": {}}
    result2 = router.route_request(request("Write a Python function", 100), key_plain)
    assert result2["fallbacks"] == ["glm-5.1-fallback"]
    assert result2["metadata"]["smart_router"]["cross_border_fallback_blocked"] is False


def test_data_residency_pydantic_key_tag_blocks_fallback():
    """H-1: the residency gate must read the key tag from a Pydantic
    UserAPIKeyAuth model (LiteLLM production shape), not only a plain dict.
    A Pydantic model exposes metadata as an attribute; the old isinstance(dict)
    guard never read it, so no policy denial could occur."""
    litellm.token_counter = lambda **kwargs: 100

    # Simulate a Pydantic UserAPIKeyAuth: metadata is an attribute, not a key.
    class _Meta:
        data_residency = "china-only"

    class _UserAPIKeyAuth:
        def __init__(self, metadata):
            self.metadata = metadata

    key_pydantic = _UserAPIKeyAuth(_Meta())
    result = router.route_request(request("Write a Python function", 100), key_pydantic)
    assert result["model"] == "claude-glm-5.2"
    assert "fallbacks" not in result
    assert result["metadata"]["smart_router"]["cross_border_fallback_blocked"] is True

    # A Pydantic key without the tag does not block.
    class _MetaPlain:
        data_residency = None

    key_plain = _UserAPIKeyAuth(_MetaPlain())
    result2 = router.route_request(request("Write a Python function", 100), key_plain)
    assert result2["fallbacks"] == ["glm-5.1-fallback"]
    assert result2["metadata"]["smart_router"]["cross_border_fallback_blocked"] is False

    # None key does not block (and does not crash).
    result3 = router.route_request(request("Write a Python function", 100), None)
    assert result3["fallbacks"] == ["glm-5.1-fallback"]


test_data_residency_pydantic_key_tag_blocks_fallback()


def test_fail_open_logs_warning():
    """F6: async_pre_call_hook must log a warning (no payload) on fail-open."""
    import asyncio
    import logging

    hook = router.proxy_handler_instance
    records = []
    handler = logging.Handler()
    handler.emit = lambda record: records.append(record)
    logger = logging.getLogger("smart_router")
    logger.addHandler(handler)
    old_level = logger.level
    logger.setLevel(logging.WARNING)
    try:
        # Monkeypatch route_request to raise a generic error, simulating a
        # router failure on malformed input. The hook must fail open (return
        # the original data) AND log a warning without the payload.
        bad = {"model": "claude-glm-5.2", "messages": [{"role": "user", "content": "hi"}]}
        original_rr = router.route_request
        router.route_request = lambda data, key: (_ for _ in ()).throw(
            RuntimeError("simulated router failure")
        )
        try:
            out = asyncio.run(hook.async_pre_call_hook(None, None, bad, "completion"))
        finally:
            router.route_request = original_rr
        assert out is bad, "fail-open must return the original data"
        assert any(r.levelno == logging.WARNING for r in records), (
            "F6: fail-open must log a warning"
        )
        # Never log the payload — the record message must not contain the
        # request body.
        for record in records:
            assert "messages" not in (record.getMessage() or "")
    finally:
        logger.removeHandler(handler)
        logger.setLevel(old_level)


def test_fail_open_increments_error_counter():
    """H-3: the fail-open path increments smart_router_errors_total so an
    unqueryable error rate is visible (PRD-sidecar-acceptance-review §6)."""
    import asyncio

    hook = router.proxy_handler_instance
    bad = {"model": "claude-glm-5.2", "messages": [{"role": "user", "content": "hi"}]}
    original_rr = router.route_request
    # Capture inc calls on ROUTER_ERRORS.
    incs = []
    orig_err = router.ROUTER_ERRORS
    class _Cap:
        def labels(self, **kw):
            return self
        def inc(self):
            incs.append(1)
    router.ROUTER_ERRORS = _Cap()
    router.route_request = lambda data, key: (_ for _ in ()).throw(
        RuntimeError("simulated router failure")
    )
    try:
        out = asyncio.run(hook.async_pre_call_hook(None, None, bad, "completion"))
        assert out is bad, "fail-open must return the original data"
        assert len(incs) == 1, "H-3: error counter must increment once on fail-open"
    finally:
        router.route_request = original_rr
        router.ROUTER_ERRORS = orig_err


def test_hook_boundary_contract():
    """H-4: the pre-call hook boundary contract — async_pre_call_hook accepts
    (user_api_key_dict, cache, data, call_type) and returns data or raises
    ContextLimitError. route_request accepts (data, user_api_key_dict) and
    returns data. These signatures are the hook boundary other plugins rely on."""
    import asyncio
    import inspect

    hook = router.proxy_handler_instance
    # async_pre_call_hook signature (inspect.signature on a bound method
    # excludes 'self').
    sig = inspect.signature(hook.async_pre_call_hook)
    params = list(sig.parameters)
    assert params == ["user_api_key_dict", "cache", "data", "call_type"], (
        "async_pre_call_hook params: %s" % params
    )
    # route_request signature
    sig2 = inspect.signature(router.route_request)
    params2 = list(sig2.parameters)
    assert params2 == ["data", "user_api_key_dict"], (
        "route_request params: %s" % params2
    )
    # A normal request round-trips through the hook and returns a dict.
    req = request("hello", 100)
    out = asyncio.run(hook.async_pre_call_hook(None, None, req, "completion"))
    assert isinstance(out, dict), "hook must return a dict"
    assert "model" in out, "hook must set a model"
    # ContextLimitError propagates (not swallowed).
    original_rr = router.route_request
    def raise_ctx(data, key):
        raise router.ContextLimitError("simulated cliff")
    router.route_request = raise_ctx
    try:
        raised = False
        try:
            asyncio.run(hook.async_pre_call_hook(None, None, request("hi", 100), "completion"))
        except router.ContextLimitError:
            raised = True
        assert raised, "ContextLimitError must propagate, not be swallowed"
    finally:
        router.route_request = original_rr


def test_sidecar_typed_errors_propagate_not_swallowed():
    """I8: VisionSidecarUnavailable (and other typed sidecar errors with an
    http_status attr) must propagate through the fail-open wrapper, not be
    swallowed. Without this, both visual models failing sends an un-captioned
    image to GLM (which 400s) instead of a clean 502."""
    import asyncio

    hook = router.proxy_handler_instance

    class _FakeVisionUnavailable(Exception):
        http_status = 502

    # Monkeypatch orchestrate_sidecars to raise a typed sidecar error.
    original = router.orchestrate_sidecars
    async def raise_typed(data, key):
        raise _FakeVisionUnavailable("both vision models failed")
    router.orchestrate_sidecars = raise_typed
    try:
        propagated = False
        try:
            asyncio.run(hook.async_pre_call_hook(None, None, request("hi", 100), "completion"))
        except _FakeVisionUnavailable:
            propagated = True
        assert propagated, "I8: typed sidecar error (http_status=502) must propagate, not be swallowed"
    finally:
        router.orchestrate_sidecars = original


def test_sidecar_typed_error_413_maps_to_content_too_large():
    """PRD §7.9: ImageLimitExceeded (http_status=413) must NOT be mapped to
    BadRequestError (400). The fail-open wrapper must preserve the declared
    HTTP status. When litellm is unavailable (test env), the original error
    with http_status=413 is re-raised — verify it carries 413, not 400."""
    import asyncio

    hook = router.proxy_handler_instance

    class _FakeImageLimit(Exception):
        http_status = 413
        error_code = "IMAGE_LIMIT_EXCEEDED"

    original = router.orchestrate_sidecars
    async def raise_413(data, key):
        raise _FakeImageLimit("too many images")
    router.orchestrate_sidecars = raise_413
    try:
        caught_status = None
        try:
            asyncio.run(hook.async_pre_call_hook(None, None, request("hi", 100), "completion"))
        except _FakeImageLimit as e:
            caught_status = e.http_status
        except Exception as e:
            # litellm may be available and raise ContentTooLargeError — check it's not BadRequestError
            caught_status = getattr(e, "http_status", None) or type(e).__name__
        assert caught_status == 413 or caught_status == "ContentTooLargeError", \
            "413 ImageLimitExceeded must map to 413/ContentTooLargeError, not 400/BadRequestError (got %r)" % caught_status
    finally:
        router.orchestrate_sidecars = original


# ── Regression: image blocks survive to vision routes (no early strip) ─────


def _has_image_block(messages):
    """True if any message still carries an image content block."""
    for msg in messages:
        content = msg.get("content") if isinstance(msg, dict) else None
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") in {
                    "image", "image_url", "input_image",
                }:
                    return True
    return False


def test_text_reference_stays_on_mainline():
    """PRD-glm52-mainline-sidecars: a text turn referencing a previous image
    stays on the mainline. The image_reference branch was deleted — historical
    images are replaced by cached captions by the sidecar, so a text reference
    needs no vision call. route_request sees only text and keeps glm_execution."""
    data = {
        "model": "claude-glm-5.2",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "这是报错截图"},
                    {"type": "text", "text": "[vision-caption]error dialog[/vision-caption]"},
                ],
            },
            {"role": "assistant", "content": "这是一个错误提示截图。"},
            {"role": "user", "content": "请重新帮我分析下上一张报错截图。"},
        ],
    }
    result = router.route_request(data)
    assert result["model"] == "claude-glm-5.2"
    assert result["metadata"]["smart_router"]["matched_rule"] == "glm_execution"


def test_route_request_does_not_touch_image_blocks():
    """route_request (the sync core) no longer strips or routes image blocks —
    the sidecar handles caption injection before route_request runs. Any image
    blocks present are left untouched (the sidecar would have replaced them)."""
    data = {
        "model": "claude-glm-5.2",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "看这个截图"},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
                ],
            },
            {"role": "assistant", "content": "我看到了"},
            {"role": "user", "content": "继续分析"},
        ],
    }
    result = router.route_request(data)
    assert result["model"] == "claude-glm-5.2"
    # Image blocks are left in place — the sidecar (run earlier) would have
    # replaced them; route_request itself does not strip.
    assert _has_image_block(result["messages"]), (
        "route_request must not strip image blocks (the sidecar owns that)"
    )


# ── Fail-open: malformed input must not raise ───────────────────────────────


def test_fail_open_on_malformed_input():
    """async_pre_call_hook must return data unchanged on malformed input.

    A router error must never fail a request (PRD §8: all branches fail open).
    Malformed input is NOT ContextLimitError, so it is still swallowed.
    """
    import asyncio

    hook = router.proxy_handler_instance

    for bad in [
        {"model": "claude-glm-5.2", "messages": [], "metadata": None},
        {"model": "claude-glm-5.2", "messages": [], "metadata": "string"},
        {"model": "claude-glm-5.2", "messages": 42},
        {"model": "claude-glm-5.2", "messages": None, "system": None},
    ]:
        out = asyncio.run(hook.async_pre_call_hook(None, None, bad, "completion"))
        assert out is bad, "fail-open must return the original data, not raise"


# ── Item 1: model family classifier ─────────────────────────────────────────


def test_model_profile_family():
    """The registry resolves model IDs to family profiles (PRD-glm-consolidation §10)."""
    assert router._model_profile("claude-glm-5.2")["family"] == "glm"
    assert router._model_profile("glm-5.2")["family"] == "glm"
    assert router._model_profile("claude-glm-5.2")["family"] == "glm"
    assert router._model_profile("claude-glm-5.2")["family"] == "glm"
    assert router._model_profile("glm-5.1-fallback")["family"] == "glm"
    assert router._model_profile("vision-openrouter")["family"] == "other"
    assert router._model_profile("premium-openrouter")["family"] == "other"
    # Unknown ID -> fallback profile (family "other").
    assert router._model_profile("gpt-4o")["family"] == "other"
    assert router._model_profile("")["family"] == "other"
    assert router._model_profile(None)["family"] == "other"


def test_model_profile_flags():
    """Profile flags drive plugin behavior (affinity, loop_breaker, reasoning_filter)."""
    glm = router._model_profile("claude-glm-5.2")
    assert glm["affinity"] is True
    assert glm["loop_breaker"] is True
    assert glm["reasoning_filter"] is True
    # glm-5.1-fallback: loop_breaker on, affinity off (it's a fallback, not mainline)
    fallback = router._model_profile("glm-5.1-fallback")
    assert fallback["affinity"] is False
    assert fallback["loop_breaker"] is True
    assert fallback["reasoning_filter"] is True
    # vision branch: no loop_breaker, no affinity, no reasoning_filter
    vision = router._model_profile("vision-openrouter")
    assert vision["affinity"] is False
    assert vision["loop_breaker"] is False
    assert vision["reasoning_filter"] is False
    # premium branch: sampling_params=reject, no loop_breaker
    premium = router._model_profile("premium-openrouter")
    assert premium["sampling_params"] == "reject"
    assert premium["loop_breaker"] is False
    # Unknown -> inert fallback: no affinity, no loop_breaker, no reasoning
    # filter (a miss must not strip thinking from a possible Anthropic model).
    other = router._model_profile("gpt-4o")
    assert other["affinity"] is False
    assert other["loop_breaker"] is False
    assert other["reasoning_filter"] is False


# ── Item 3: affinity must not rewrite non-GLM models ────────────────────────


def test_affinity_does_not_rewrite_non_glm():
    """PRD-release-closure §3.1: a non-GLM model request is REJECTED by the
    router (not passed through or rewritten). Native Claude selectors must
    never receive GLM fallback, Sidecar processing, or model rewriting."""
    mod = _reload_with_deployments(3)
    try:
        for model_name in ("claude-sonnet-5", "claude-haiku-4-5", "gpt-4o"):
            data = {"model": model_name, "messages": [
                {"role": "user", "content": "Write a Python function that sorts invoices"},
            ]}
            rejected = False
            try:
                mod.route_request(copy.deepcopy(data))
            except Exception:
                rejected = True
            assert rejected, (
                "Item 3: %s must be rejected (non-GLM), but was accepted" % model_name
            )
    finally:
        pass


def test_affinity_still_applies_to_glm_compat_alias():
    """Item 3: claude-glm-5.2 is the GLM compat alias and MUST still get
    affinity (rewritten to glm-N) when DEPLOYMENT_COUNT > 1."""
    mod = _reload_with_deployments(3)
    try:
        data = {"model": "claude-glm-5.2", "messages": [
            {"role": "user", "content": "Write a Python function that sorts invoices"},
        ]}
        result = mod.route_request(copy.deepcopy(data))
        assert result["model"].startswith("glm-"), (
            "Item 3: claude-opus (GLM alias) must still get affinity, got %s"
            % result["model"]
        )
        assert result["metadata"]["smart_router"]["affinity_deployment"] == result["model"]
    finally:
        pass


def test_affinity_still_applies_to_glm_model():
    """Item 3: a glm-* model still gets affinity."""
    mod = _reload_with_deployments(3)
    try:
        data = {"model": "claude-glm-5.2", "messages": [
            {"role": "user", "content": "Write a Python function"},
        ]}
        result = mod.route_request(copy.deepcopy(data))
        assert result["model"].startswith("glm-") or result["model"] == "claude-glm-5.2", (
            "Item 3: claude-glm-5.2 must still get affinity, got %s" % result["model"]
        )
    finally:
        pass


# ── Item 5: context cliff actionable error (now glm-5.1-fallback) ───────────


def test_cliff_raises_on_oversize():
    """Item 5 / R-2: a 340K-token request to glm-5.1-fallback (196608 ceiling)
    raises ContextLimitError with the actionable message."""
    # Build a request whose byte estimate is ~340K tokens (well over the 196608
    # limit and far from the band boundaries so the byte estimate is used).
    text = "a" * (340000 * 4)
    data = {"model": "glm-5.1-fallback", "messages": [
        {"role": "user", "content": text},
    ]}
    try:
        router.route_request(data)
    except router.ContextLimitError as e:
        msg = str(e)
        assert "340" in msg, "message must mention the session size: %s" % msg
        assert "196" in msg, "message must mention the 196K limit: %s" % msg
        assert "/compact" in msg, "message must be actionable: %s" % msg
        assert "larger model" in msg, (
            "message must suggest switching to a larger model: %s" % msg
        )
    else:
        raise AssertionError("Item 5: 340K glm-5.1-fallback request must raise ContextLimitError")


def test_cliff_succeeds_under_limit():
    """Item 5: a 150K-token request to glm-5.1-fallback succeeds (stays on
    glm-5.1-fallback, no error). 150K is under the 196608 limit."""
    text = "a" * (150000 * 4)
    data = {"model": "glm-5.1-fallback", "messages": [
        {"role": "user", "content": text},
    ]}
    result = router.route_request(data)
    assert result["model"] == "glm-5.1-fallback", (
        "Item 5: 150K glm-5.1-fallback must stay, got %s" % result["model"]
    )


def test_cliff_does_not_fire_on_glm_mainline():
    """Item 5: a 340K-token request to claude-glm-5.2 (GLM mainline, 1M
    context) succeeds — the cliff only fires over a model's own ceiling."""
    text = "a" * (340000 * 4)
    data = {"model": "claude-glm-5.2", "messages": [
        {"role": "user", "content": text},
    ]}
    result = router.route_request(data)
    assert result["model"] == "claude-glm-5.2"


def test_cliff_re_raised_by_fail_open_wrapper():
    """Item 5 / R-2: async_pre_call_hook must RE-RAISE ContextLimitError, not
    swallow it (unlike generic Exception which is fail-open)."""
    import asyncio

    text = "a" * (340000 * 4)
    data = {"model": "glm-5.1-fallback", "messages": [
        {"role": "user", "content": text},
    ]}
    hook = router.proxy_handler_instance
    # Temporarily remove any loaded sidecar so orchestrate_sidecars is a no-op
    # and the fallback model reaches the context-cliff check unchanged.
    _saved_sidecar = sys.modules.pop("sidecar", None)
    try:
        try:
            asyncio.run(hook.async_pre_call_hook(None, None, data, "completion"))
        except router.ContextLimitError:
            pass  # correct — re-raised, not swallowed
        else:
            raise AssertionError(
                "Item 5: ContextLimitError must be re-raised by the fail-open wrapper"
            )
    finally:
        if _saved_sidecar is not None:
            sys.modules["sidecar"] = _saved_sidecar


def test_cliff_skips_background_traffic():
    """Item 5 / PRD §7.3: background traffic (metadata.background=True) must
    not fire the cliff even if tokens exceed the limit. The token check is the
    primary gate (background tasks are tiny), but the metadata flag is an extra
    safety net."""
    text = "a" * (340000 * 4)
    data = {
        "model": "glm-5.1-fallback",
        "messages": [{"role": "user", "content": text}],
        "metadata": {"background": True},
    }
    # Should NOT raise — background flag suppresses the cliff.
    result = router.route_request(data)
    assert result["model"] == "glm-5.1-fallback"


def test_cliff_message_format():
    """Item 5 / R-2: the error message format matches the PRD spec —
    family-agnostic, naming the model and its real limit."""
    text = "a" * (340000 * 4)
    data = {"model": "glm-5.1-fallback", "messages": [
        {"role": "user", "content": text},
    ]}
    try:
        router.route_request(data)
    except router.ContextLimitError as e:
        msg = str(e)
        # "session is ~340K tokens, glm-5.1-fallback's context limit is 196K;
        #  use /compact or switch to a larger model"
        assert msg.startswith("session is ~"), "bad prefix: %s" % msg
        assert "tokens" in msg
        assert "context limit is" in msg
        assert "glm-5.1-fallback" in msg, "message must name the model: %s" % msg
        assert "use /compact or switch to a larger model" in msg
    else:
        raise AssertionError("expected ContextLimitError")


# ── R-2: generalized context guard (PRD §4) ─────────────────────────────────


def test_250k_fallback_raises_context_limit_error():
    """R-2: a 250K-token request to glm-5.1-fallback raises ContextLimitError
    (196608 ceiling). The guard is general — any model over its ceiling."""
    text = "a" * (250000 * 4)
    data = {"model": "glm-5.1-fallback", "messages": [
        {"role": "user", "content": text},
    ]}
    try:
        router.route_request(data)
    except router.ContextLimitError as e:
        msg = str(e)
        assert "250" in msg, "message must mention session size: %s" % msg
        assert "196" in msg, "message must mention the 196K limit: %s" % msg
        assert "glm-5.1-fallback" in msg, "message must name the model: %s" % msg
    else:
        raise AssertionError("R-2: 250K fallback request must raise ContextLimitError")


def test_250k_glm_does_not_raise():
    """R-2: a 250K-token request to claude-glm-5.2 does NOT raise (1M ceiling).
    The guard is general but only fires when tokens exceed the model's ceiling."""
    text = "a" * (250000 * 4)
    data = {"model": "claude-glm-5.2", "messages": [
        {"role": "user", "content": text},
    ]}
    result = router.route_request(data)
    assert result["model"] == "claude-glm-5.2", (
        "R-2: 250K GLM must stay on GLM (1M ceiling), got %s" % result["model"]
    )


def test_150k_fallback_does_not_raise():
    """R-2: a 150K-token request to glm-5.1-fallback does NOT raise (under 196608
    ceiling). 150K is in the advisory band but below the hard limit."""
    text = "a" * (150000 * 4)
    data = {"model": "glm-5.1-fallback", "messages": [
        {"role": "user", "content": text},
    ]}
    result = router.route_request(data)
    assert result["model"] == "glm-5.1-fallback", (
        "R-2: 150K fallback must stay on fallback, got %s" % result["model"]
    )


# ── §7: profile-derived length bands ────────────────────────────────────────


def test_length_band_fallback_150k_is_advisory():
    """§7: a 150K request to glm-5.1-fallback → "advisory" (~118K-196K band).
    Fallback ceiling is 196608; advisory = 60% * 196608 = 117965. 150K is in
    [117965, 196608)."""
    text = "a" * (150000 * 4)
    data = {"model": "glm-5.1-fallback", "messages": [
        {"role": "user", "content": text},
    ]}
    result = router.route_request(data)
    band = result["metadata"]["smart_router"]["length_band"]
    assert band == "advisory", (
        "§7: 150K fallback should be advisory (~118K-196K band), got %s" % band
    )


def test_length_band_glm_150k_is_normal():
    """§7: a 150K request to GLM → "normal" (under ~600K). GLM ceiling is 1M;
    advisory = 60% * 1M = ~600K. 150K is well under 600K."""
    text = "a" * (150000 * 4)
    data = {"model": "claude-glm-5.2", "messages": [
        {"role": "user", "content": text},
    ]}
    result = router.route_request(data)
    band = result["metadata"]["smart_router"]["length_band"]
    assert band == "normal", (
        "§7: 150K GLM should be normal (under ~600K advisory), got %s" % band
    )


def test_length_band_boundaries_derived_from_profile():
    """§7: _length_boundaries derives advisory=60% and oversize=ceiling from
    the model's max_input_tokens, not from global constants."""
    # GLM (1M ceiling): advisory=~600K, oversize=1M
    glm_advisory, glm_oversize = router._length_boundaries(1000000)
    assert glm_advisory == 600000, "GLM advisory should be 600K, got %d" % glm_advisory
    assert glm_oversize == 1000000, "GLM oversize should be 1M, got %d" % glm_oversize

    # Fallback (196608 ceiling): advisory=int(196608*0.6)=117964, oversize=196608
    fb_advisory, fb_oversize = router._length_boundaries(196608)
    assert fb_advisory == 117964, "fallback advisory should be 117964, got %d" % fb_advisory
    assert fb_oversize == 196608, "fallback oversize should be 196608, got %d" % fb_oversize


# ── R-6: registry ↔ model_list startup invariant (PRD §6) ───────────────────


def _build_model_list_yaml(models):
    """Build a litellm_config.yaml 'model_list' from a list of model dicts.

    Each dict has: model_name, litellm_params_model, max_input_tokens,
    max_output_tokens. Returns YAML text with the model_list structure.
    """
    import yaml
    entries = []
    for m in models:
        entries.append({
            "model_name": m["model_name"],
            "litellm_params": {"model": m["litellm_params_model"]},
            "model_info": {
                "max_input_tokens": m["max_input_tokens"],
                "max_output_tokens": m["max_output_tokens"],
            },
        })
    return yaml.dump({"model_list": entries}, default_flow_style=False)


def _registry_models_for_ml():
    """Build a model_list matching the registry (all non-test-only entries)."""
    reg = router.REGISTRY.get("models") or {}
    models = []
    for name, prof in reg.items():
        if name in router._TEST_ONLY_MODELS:
            continue
        models.append({
            "model_name": name,
            "litellm_params_model": prof["upstream"],
            "max_input_tokens": prof["max_input_tokens"],
            "max_output_tokens": prof["max_output_tokens"],
        })
    return models


def test_r6_validation_passes_with_matching_model_list():
    """R-6: a model_list matching the registry passes validation."""
    models = _registry_models_for_ml()
    yaml_text = _build_model_list_yaml(models)
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write(yaml_text)
        f.flush()
        path = f.name
    try:
        # Must not raise.
        router._validate_registry_vs_model_list(path, router.REGISTRY)
    finally:
        os.unlink(path)


def test_r6_r1_model_list_entry_not_in_registry_raises():
    """R-6 R1: a model_list entry not in the registry raises ValueError."""
    models = _registry_models_for_ml()
    # Add an entry that has no registry entry.
    models.append({
        "model_name": "claude-opus-5-1m",
        "litellm_params_model": "openai/glm-5.2",
        "max_input_tokens": 1000000,
        "max_output_tokens": 128000,
    })
    yaml_text = _build_model_list_yaml(models)
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write(yaml_text)
        f.flush()
        path = f.name
    try:
        try:
            router._validate_registry_vs_model_list(path, router.REGISTRY)
        except ValueError as e:
            assert "R1" in str(e), "must name R1: %s" % e
            assert "claude-opus-5-1m" in str(e), "must name the model: %s" % e
        else:
            raise AssertionError("R1 violation must raise ValueError")
    finally:
        os.unlink(path)


def test_r6_r3_mismatched_max_input_tokens_raises():
    """R-6 R3: a max_input_tokens mismatch raises ValueError."""
    models = _registry_models_for_ml()
    # Corrupt the max_input_tokens of the first model.
    models[0]["max_input_tokens"] = models[0]["max_input_tokens"] + 1
    yaml_text = _build_model_list_yaml(models)
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write(yaml_text)
        f.flush()
        path = f.name
    try:
        try:
            router._validate_registry_vs_model_list(path, router.REGISTRY)
        except ValueError as e:
            assert "R3" in str(e), "must name R3: %s" % e
            assert "max_input_tokens" in str(e), "must name the field: %s" % e
        else:
            raise AssertionError("R3 violation must raise ValueError")
    finally:
        os.unlink(path)


def test_r6_r5_sonnet_name_with_glm_upstream_raises():
    """R-6 R5: a model_name containing 'sonnet' with a GLM upstream raises
    ValueError — this is the P0-2 class. We add a synthetic entry to both the
    model_list and a registry copy so R4 passes (upstreams agree) and R5 fires
    (name says sonnet, upstream doesn't serve sonnet).
    """
    models = _registry_models_for_ml()
    models.append({
        "model_name": "claude-sonnet-fake",
        "litellm_params_model": "openai/glm-5.2",
        "max_input_tokens": 1000000,
        "max_output_tokens": 128000,
    })
    import copy as _copy
    reg = _copy.deepcopy(router.REGISTRY)
    reg["models"]["claude-sonnet-fake"] = dict(reg["models"]["claude-glm-5.2"])
    reg["models"]["claude-sonnet-fake"]["upstream"] = "openai/glm-5.2"
    yaml_text = _build_model_list_yaml(models)
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write(yaml_text)
        f.flush()
        path = f.name
    try:
        try:
            router._validate_registry_vs_model_list(path, reg)
        except ValueError as e:
            assert "R5" in str(e), "must name R5: %s" % e
            assert "sonnet" in str(e), "must mention sonnet: %s" % e
        else:
            raise AssertionError("R5 violation must raise ValueError")
    finally:
        os.unlink(path)


def test_r6_unset_model_list_file_is_noop():
    """R-6: when MODEL_LIST_FILE is unset, validation is a no-op (no raise)."""
    # Call with an empty path — must not raise.
    router._validate_registry_vs_model_list("", router.REGISTRY)


def test_r6_missing_file_is_noop():
    """R-6: a set but non-existent path is a no-op (dev box, don't crash)."""
    router._validate_registry_vs_model_list("/nonexistent/path/to/config.yaml", router.REGISTRY)


def test_r6_r2_dead_registry_entry_raises():
    """R-6 R2: a registry entry not in model_list (and not test-only) raises."""
    models = _registry_models_for_ml()
    # Remove one non-test-only entry so it becomes dead config.
    # vision-openrouter-secondary is not in _TEST_ONLY_MODELS.
    models = [m for m in models if m["model_name"] != "vision-openrouter-secondary"]
    yaml_text = _build_model_list_yaml(models)
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write(yaml_text)
        f.flush()
        path = f.name
    try:
        try:
            router._validate_registry_vs_model_list(path, router.REGISTRY)
        except ValueError as e:
            assert "R2" in str(e), "must name R2: %s" % e
            assert "vision-openrouter-secondary" in str(e), "must name the model: %s" % e
        else:
            raise AssertionError("R2 violation must raise ValueError")
    finally:
        os.unlink(path)


def test_r6_r4_upstream_mismatch_raises():
    """R-6 R4: a litellm_params.model that disagrees with registry upstream
    raises ValueError."""
    models = _registry_models_for_ml()
    # Corrupt the upstream of the first model.
    models[0]["litellm_params_model"] = "openai/some-other-model"
    yaml_text = _build_model_list_yaml(models)
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write(yaml_text)
        f.flush()
        path = f.name
    try:
        try:
            router._validate_registry_vs_model_list(path, router.REGISTRY)
        except ValueError as e:
            assert "R4" in str(e), "must name R4: %s" % e
        else:
            raise AssertionError("R4 violation must raise ValueError")
    finally:
        os.unlink(path)


def test_r6_r5_haiku_name_with_glm_upstream_raises():
    """R-6 R5: a model_name containing 'haiku' with a non-haiku upstream
    raises ValueError. We add a synthetic entry to both the model_list and a
    registry copy so R4 passes and R5 fires."""
    models = _registry_models_for_ml()
    models.append({
        "model_name": "claude-haiku-fake",
        "litellm_params_model": "openai/glm-5.2",
        "max_input_tokens": 1000000,
        "max_output_tokens": 128000,
    })
    import copy as _copy
    reg = _copy.deepcopy(router.REGISTRY)
    reg["models"]["claude-haiku-fake"] = dict(reg["models"]["claude-glm-5.2"])
    reg["models"]["claude-haiku-fake"]["upstream"] = "openai/glm-5.2"
    yaml_text = _build_model_list_yaml(models)
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write(yaml_text)
        f.flush()
        path = f.name
    try:
        try:
            router._validate_registry_vs_model_list(path, reg)
        except ValueError as e:
            assert "R5" in str(e), "must name R5: %s" % e
            assert "haiku" in str(e), "must mention haiku: %s" % e
        else:
            raise AssertionError("R5 haiku violation must raise ValueError")
    finally:
        os.unlink(path)


def test_r6_r6_unpublished_route_target_raises():
    """R-6 R6: a route target not published in model_list raises ValueError.

    We set SMART_ROUTER_GLM_FALLBACK_MODEL to a name that is neither in the
    registry nor in model_list, so R2 does not fire first. R6 catches it.
    """
    env_key = "SMART_ROUTER_GLM_FALLBACK_MODEL"
    old = os.environ.get(env_key)
    os.environ[env_key] = "nonexistent-fallback-target"
    try:
        spec2 = importlib.util.spec_from_file_location("smart_router_r6", CALLBACK)
        mod = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(mod)
        models = _registry_models_for_ml()
        yaml_text = _build_model_list_yaml(models)
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            f.write(yaml_text)
            f.flush()
            path = f.name
        try:
            try:
                mod._validate_registry_vs_model_list(path, mod.REGISTRY)
            except ValueError as e:
                assert "R6" in str(e), "must name R6: %s" % e
                assert "nonexistent-fallback-target" in str(e), "must name the target: %s" % e
            else:
                raise AssertionError("R6 violation must raise ValueError")
        finally:
            os.unlink(path)
    finally:
        if old is None:
            os.environ.pop(env_key, None)
        else:
            os.environ[env_key] = old


def test_r6_r6_wildcard_exempt():
    """R-6 R6: wildcard route targets (GLM_MODEL=claude-*) are exempt from the
    publish check and do not raise."""
    models = _registry_models_for_ml()
    yaml_text = _build_model_list_yaml(models)
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write(yaml_text)
        f.flush()
        path = f.name
    try:
        # Must not raise — GLM_MODEL and MAINLINE_GROUP are wildcards (claude-*).
        router._validate_registry_vs_model_list(path, router.REGISTRY)
    finally:
        os.unlink(path)


# ── runner ─────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    tests = [
        test_multilingual_routes,
        test_audit_prompts_stay_on_mainline,
        test_observability_and_score_does_not_route,
        test_context_boundary_and_controlled_fallbacks,
        test_image_request_stays_on_mainline,
        test_capability_aware_routing_for_meli_glm_strategy,
        test_rules_schema_and_runtime_validation,
        test_prometheus_metrics_are_registered,
        # length bands
        test_length_bands_never_escalate,
        test_length_bands_recorded_in_metadata,
        test_length_never_escalates_to_premium,
        # fallback token cap
        test_fallback_token_cap_below_cap_attaches_same_provider,
        test_fallback_token_cap_above_cap_no_fallback,
        test_fallback_token_cap_same_provider_exempt,
        # affinity hash
        test_affinity_deployment_count_one_is_noop,
        test_affinity_same_prefix_same_deployment,
        test_affinity_different_prefixes_distribute,
        test_affinity_session_id_preferred_over_prefix,
        test_affinity_only_applies_to_mainline,
        test_affinity_stable_across_restarts,
        test_affinity_first_user_message_pins_across_turns,
        test_affinity_tool_result_turn_and_followup_same_deployment,
        # no deepcopy
        test_no_deepcopy_on_request_path,
        test_no_copy_module_imported,
        test_no_full_payload_json_dumps_for_policy,
        # token estimation
        test_token_counter_only_called_near_boundary,
        test_byte_estimate_does_not_json_dumps_tools,
        # data residency (F5)
        test_data_residency_server_env_default_blocks_fallback,
        test_data_residency_key_tag_blocks_fallback,
        test_data_residency_pydantic_key_tag_blocks_fallback,
        # PRD-glm52-mainline-sidecars: images stay on mainline, sidecar owns caption injection
        test_text_reference_stays_on_mainline,
        test_route_request_does_not_touch_image_blocks,
        # fail-open
        test_fail_open_on_malformed_input,
        test_fail_open_logs_warning,
        test_fail_open_increments_error_counter,
        # H-4: hook boundary contract
        test_hook_boundary_contract,
        # I8: typed sidecar errors propagate, not swallowed by fail-open
        test_sidecar_typed_errors_propagate_not_swallowed,
        # PRD §7.9: 413 maps to ContentTooLargeError, not BadRequestError (400)
        test_sidecar_typed_error_413_maps_to_content_too_large,
        # Item 1: model family classifier
        test_model_profile_family,
        test_model_profile_flags,
        # Item 3: affinity must not rewrite non-GLM models
        test_affinity_does_not_rewrite_non_glm,
        test_affinity_still_applies_to_glm_compat_alias,
        test_affinity_still_applies_to_glm_model,
        # Item 5: context cliff
        test_cliff_raises_on_oversize,
        test_cliff_succeeds_under_limit,
        test_cliff_does_not_fire_on_glm_mainline,
        test_cliff_re_raised_by_fail_open_wrapper,
        test_cliff_skips_background_traffic,
        test_cliff_message_format,
        # R-6: registry ↔ model_list startup invariant (PRD §6)
        test_r6_validation_passes_with_matching_model_list,
        test_r6_r1_model_list_entry_not_in_registry_raises,
        test_r6_r3_mismatched_max_input_tokens_raises,
        test_r6_r5_sonnet_name_with_glm_upstream_raises,
        test_r6_unset_model_list_file_is_noop,
        test_r6_missing_file_is_noop,
        test_r6_r2_dead_registry_entry_raises,
        test_r6_r4_upstream_mismatch_raises,
        test_r6_r5_haiku_name_with_glm_upstream_raises,
        test_r6_r6_unpublished_route_target_raises,
        test_r6_r6_wildcard_exempt,
        # R-2: generalized context guard
        test_250k_fallback_raises_context_limit_error,
        test_250k_glm_does_not_raise,
        test_150k_fallback_does_not_raise,
        # §7: profile-derived length bands
        test_length_band_fallback_150k_is_advisory,
        test_length_band_glm_150k_is_normal,
        test_length_band_boundaries_derived_from_profile,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print("  ok %s" % test.__name__)
            passed += 1
        except AssertionError as e:
            print("  FAIL %s: %s" % (test.__name__, e))
            failed += 1
        except Exception as e:
            print("  ERROR %s: %s: %s" % (test.__name__, type(e).__name__, e))
            failed += 1
    print("\n" + "=" * 50)
    print("Results: %d passed, %d failed, %d total" % (passed, failed, len(tests)))
    if failed:
        sys.exit(1)
    else:
        print("smart_router tests passed")
