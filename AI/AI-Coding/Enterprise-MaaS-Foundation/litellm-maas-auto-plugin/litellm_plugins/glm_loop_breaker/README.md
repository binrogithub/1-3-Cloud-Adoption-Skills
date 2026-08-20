# GLM Loop Breaker

Request-side LiteLLM callback. It detects when an agent has fallen into a
repeating tool-call cycle and forces the model out of it.

GLM self-reinforces off its own context: once the history holds a few identical
agent iterations, the model stops exploring and reproduces them verbatim. With
provider thinking disabled and `temperature: 0`, repeating the most similar span
already in context is the deterministic best continuation, so the client cannot
escape on its own.

The breaker:

- fingerprints assistant tool calls by name and arguments, ignoring call ids;
- detects repeating cycles of period 1–3 at the tail of the history, not just
  consecutive duplicates;
- classifies the requested model into a family (`glm`, `anthropic_sonnet`,
  `anthropic_haiku`, `other`) and, on a detected cycle:
  - on the **glm** family, raises `temperature` to a floor and sets `top_p`
    once a cycle repeats `GLM_LOOP_TRIGGER` times;
  - on **anthropic_sonnet** / **anthropic_haiku**, detects the cycle and records
    the audit metadata but **does not set `temperature` or `top_p`** — Sonnet and
    Haiku reject non-default sampling parameters with a 400;
- appends a redirect instruction once it repeats `GLM_LOOP_NUDGE_TRIGGER` times,
  injected **once per session** (not once per looping turn) so a long loop does
  not accumulate copies that waste tokens and dilute the signal. The nudge is a
  user message, not a sampling parameter, so it is safe on every family;
- leaves callers that already sample above the floor untouched (glm family only);
- reads both OpenAI `tool_calls` and Anthropic `tool_use` content blocks;
- records `metadata.glm_loop_breaker` (including `model_family`) so interventions
  are countable in spend logs;
- fails open — any internal error passes the request through unmodified.

## This is the second line of defence

The primary fix is to **keep provider thinking enabled on GLM routes**. Measured
against a live glm-5.2 route from a context seeded with three loop iterations:

| Condition | Runs that looped |
| --- | --- |
| thinking disabled | 12 / 12 |
| thinking enabled | 1 / 6 |
| temperature 0.0 / 0.3 / 1.0 | 3/3 · 2/3 · 0/3 |

`anthropic_reasoning_filter` is what makes thinking-on safe for Claude Code
clients: it keeps thinking enabled upstream and strips the blocks from the
response. Deploy that first. Use this breaker for the residual case, and for
deployments that disable thinking deliberately to control cost or latency.

See `docs/PRD-glm-loop-breaker.md` for the full root-cause analysis.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `GLM_LOOP_MODEL_PATTERN` | `glm\|coding-\|claude-` | Regex for which model names to **guard at all** (detect the cycle) |
| `GLM_FAMILY_PATTERN` | `glm\|coding-\|claude-opus` | Regex for the **glm** family — gets the sampling override |
| `ANTHROPIC_SONNET_PATTERN` | `claude-sonnet` | Regex for the **anthropic_sonnet** family — no sampling override |
| `ANTHROPIC_HAIKU_PATTERN` | `claude-haiku` | Regex for the **anthropic_haiku** family — no sampling override |
| `GLM_LOOP_TRIGGER` | `3` | Cycle repetitions before acting |
| `GLM_LOOP_NUDGE_TRIGGER` | `4` | Repetitions before also injecting the instruction |
| `GLM_LOOP_MAX_PERIOD` | `3` | Longest cycle length detected |
| `GLM_LOOP_TEMP_FLOOR` | `0.7` | Temperature forced on a looping **glm** request |
| `GLM_LOOP_TOP_P` | `0.95` | `top_p` set alongside it (glm family only) |

### Model families and the sampling override

This deployment serves three families behind `claude-*` aliases:

| Family | Pattern (default) | Upstream | Sampling override |
| --- | --- | --- | --- |
| `glm` | `glm\|coding-\|claude-opus` | Huawei MaaS GLM-5.2 | yes — temperature floor + top_p |
| `anthropic_sonnet` | `claude-sonnet` | OpenRouter (real Sonnet) | **no** — Sonnet rejects non-default sampling with a 400 |
| `anthropic_haiku` | `claude-haiku` | OpenRouter (real Haiku) | **no** — Haiku rejects non-default sampling with a 400 |

`claude-opus-*` is the GLM compatibility alias, not a real Anthropic model.
`claude-sonnet-*` and `claude-haiku-*` are real Anthropic models via OpenRouter.

The breaker detects the cycle in the request history on **every** family
`GLM_LOOP_MODEL_PATTERN` matches — a loop laid down on GLM survives a user
switch to sonnet/haiku because the history travels with the request. But the
sampling override (`temperature`/`top_p`) is gated on the family classifier and
applies **only to glm**. On sonnet/haiku the cycle is detected, the audit
metadata is recorded, and the nudge is appended (it is a user message, not a
sampling parameter), but `temperature` and `top_p` are left untouched. This
prevents the live 400 where a user hits a tool loop on GLM, switches to sonnet
to get unstuck, and their first sonnet request is rejected.

Family classification order is haiku → sonnet → glm, so `claude-haiku-4-5` is
not misclassified by the sonnet or glm pattern. Each pattern is
env-configurable; matching is on the alias the caller requested, so check it
against your own `model_list`.

`GLM_LOOP_MODEL_PATTERN` is kept for backward compat as the broad guard-scope
gate. The family patterns decide what the guard *does*.

## Observability

Every intervention logs at WARNING:

```
glm_loop_breaker: model=glm-5.2 family=glm cycle period=2 reps=3 temperature 0 -> 0.7 nudged=False
glm_loop_breaker: model=claude-sonnet-4-5 family=anthropic_sonnet cycle period=2 reps=5 temperature 0 -> 0 nudged=True
```

## Tests

```bash
python3 tests/test_glm_loop_breaker.py
```
