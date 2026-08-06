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
- raises `temperature` to a floor and sets `top_p` once a cycle repeats
  `GLM_LOOP_TRIGGER` times;
- appends a redirect instruction once it repeats `GLM_LOOP_NUDGE_TRIGGER` times;
- leaves callers that already sample above the floor untouched;
- reads both OpenAI `tool_calls` and Anthropic `tool_use` content blocks;
- records `metadata.glm_loop_breaker` so interventions are countable in spend logs;
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
| `GLM_LOOP_MODEL_PATTERN` | `glm\|coding-` | Regex for which model names to guard |
| `GLM_LOOP_TRIGGER` | `3` | Cycle repetitions before acting |
| `GLM_LOOP_NUDGE_TRIGGER` | `4` | Repetitions before also injecting the instruction |
| `GLM_LOOP_MAX_PERIOD` | `3` | Longest cycle length detected |
| `GLM_LOOP_TEMP_FLOOR` | `0.7` | Temperature forced on a looping request |
| `GLM_LOOP_TOP_P` | `0.95` | `top_p` set alongside it |

The default model pattern also covers `*-coding-*` aliases such as `coding-auto`
and `meli-coding-fast`, which resolve to a GLM upstream under a name containing
no "glm". Matching is on the alias the caller requested, so check it against your
own `model_list`.

## Observability

Every intervention logs at WARNING:

```
glm_loop_breaker: model=glm-5.2 cycle period=2 reps=3 temperature 0 -> 0.7 nudged=False
```

## Tests

```bash
python3 tests/test_glm_loop_breaker.py
```
