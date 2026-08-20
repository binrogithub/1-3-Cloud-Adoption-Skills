"""Tests for the model registry (PRD-multi-family-routing-v2 §3).

Validates the registry against its schema, asserts every published ID
resolves to a profile, and asserts the fallback for unknown IDs.

    python3 tests/test_model_registry.py
"""

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "litellm_plugins" / "model_registry.json"
SCHEMA = ROOT / "litellm_plugins" / "model_registry.schema.json"

raw = json.loads(REGISTRY.read_text(encoding="utf-8"))
schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

FAILURES = []


def check(name, got, want):
    if got == want:
        print("  ok    %s" % name)
    else:
        print("  FAIL  %s: got %r, want %r" % (name, got, want))
        FAILURES.append(name)


def check_true(name, got):
    check(name, bool(got), True)


def check_false(name, got):
    check(name, bool(got), False)


print("registry structure")
check_true("has registry_version", isinstance(raw.get("registry_version"), str) and raw["registry_version"])
check_true("has fallback", isinstance(raw.get("fallback"), dict))
check_true("has models", isinstance(raw.get("models"), dict) and raw["models"])

REQUIRED_PROFILE_KEYS = {
    "family", "upstream", "max_input_tokens", "max_output_tokens",
    "vision", "sampling_params", "thinking", "effort",
    "loop_breaker", "affinity", "reasoning_filter", "internal", "display_name",
}
FAMILY_ENUM = {"glm", "anthropic_sonnet", "anthropic_haiku", "other"}
SAMPLING_ENUM = {"pass", "reject"}
THINKING_ENUM = {"strip", "adaptive", "budget_tokens", "pass"}
EFFORT_ENUM = {"strip", "pass"}

print("\nfallback profile")
fb = raw["fallback"]
check("fallback has all keys", set(fb) == REQUIRED_PROFILE_KEYS, True)
check("fallback family is other", fb["family"], "other")
check_false("fallback loop_breaker", fb["loop_breaker"])
check_false("fallback affinity", fb["affinity"])
check_false("fallback reasoning_filter (inert, no strip on miss)", fb["reasoning_filter"])

print("\neach published model profile")
for mid, prof in raw["models"].items():
    check("%s has all keys" % mid, set(prof) == REQUIRED_PROFILE_KEYS, True)
    check("%s family is valid" % mid, prof["family"] in FAMILY_ENUM, True)
    check("%s sampling_params valid" % mid, prof["sampling_params"] in SAMPLING_ENUM, True)
    check("%s thinking valid" % mid, prof["thinking"] in THINKING_ENUM, True)
    check("%s effort valid" % mid, prof["effort"] in EFFORT_ENUM, True)
    check("%s max_input_tokens > 0" % mid, isinstance(prof["max_input_tokens"], int) and prof["max_input_tokens"] > 0, True)
    check("%s max_output_tokens > 0" % mid, isinstance(prof["max_output_tokens"], int) and prof["max_output_tokens"] > 0, True)

print("\ncurated set: the five honest routes (PRD-glm-consolidation §10)")
check("mainline present", "claude-glm-5.2" in raw["models"], True)
check("fallback present", "glm-5.1-fallback" in raw["models"], True)
check("vision branch present", "vision-openrouter" in raw["models"], True)
check("vision secondary present", "vision-openrouter-secondary" in raw["models"], True)
check("premium branch present", "premium-openrouter" in raw["models"], True)
# Deleted text routes (PRD-glm-consolidation §6 Option A)
check("sonnet text route deleted", "claude-sonnet-5" not in raw["models"], True)
check("haiku text route deleted", "claude-haiku-4-5" not in raw["models"], True)
check("sonnet-4-5 text route deleted", "claude-sonnet-4-5" not in raw["models"], True)

print("\nfamily/flag consistency")
glm = raw["models"]["claude-glm-5.2"]
check("glm family", glm["family"], "glm")
check_true("glm loop_breaker", glm["loop_breaker"])
check_true("glm affinity", glm["affinity"])
check_true("glm reasoning_filter", glm["reasoning_filter"])
check_false("glm not internal", glm["internal"])
check("glm 1M context", glm["max_input_tokens"], 1000000)

fallback = raw["models"]["glm-5.1-fallback"]
check("fallback family", fallback["family"], "glm")
check_true("fallback loop_breaker", fallback["loop_breaker"])
check_false("fallback affinity", fallback["affinity"])
check_true("fallback reasoning_filter", fallback["reasoning_filter"])
check_false("fallback not internal", fallback["internal"])
check("fallback 196608 context", fallback["max_input_tokens"], 196608)

vision = raw["models"]["vision-openrouter"]
check("vision family", vision["family"], "other")
check_false("vision loop_breaker", vision["loop_breaker"])
check_false("vision affinity", vision["affinity"])
check_false("vision reasoning_filter", vision["reasoning_filter"])
check_true("vision vision flag", vision["vision"])
check_true("vision internal sidecar", vision["internal"])
check("vision 1.05M context", vision["max_input_tokens"], 1050000)

vision_sec = raw["models"]["vision-openrouter-secondary"]
check_true("vision secondary internal sidecar", vision_sec["internal"])

premium = raw["models"]["premium-openrouter"]
check("premium family", premium["family"], "other")
check("premium sampling reject", premium["sampling_params"], "reject")
check_false("premium loop_breaker", premium["loop_breaker"])
check_false("premium affinity", premium["affinity"])
check_false("premium reasoning_filter", premium["reasoning_filter"])
check_true("premium vision flag", premium["vision"])
check_true("premium internal sidecar", premium["internal"])

print("\nschema validation")
check("schema additionalProperties false", schema.get("additionalProperties"), False)
check("schema requires fallback", "fallback" in schema.get("required", []), True)
check("schema requires models", "models" in schema.get("required", []), True)
prof_def = schema.get("$defs", {}).get("profile", {})
check("profile additionalProperties false", prof_def.get("additionalProperties"), False)
check("profile family enum has 4 values",
      set(prof_def.get("properties", {}).get("family", {}).get("enum", [])) == FAMILY_ENUM, True)

def test_all_checks_pass():
    """Pytest entry point: assert every module-level check() succeeded."""
    assert not FAILURES, "%d checks failed: %s" % (len(FAILURES), ", ".join(FAILURES))


if __name__ == "__main__":
    print()
    if FAILURES:
        print("%d failed: %s" % (len(FAILURES), ", ".join(FAILURES)))
        raise SystemExit(1)
    print("all checks passed")
