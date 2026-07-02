# How forky works (architecture deep-dive)

## The problem

Claude Code sends each process's requests to a single Anthropic Messages API endpoint. You either pay
Anthropic for every token (Opus/Sonnet) or you point it at a cheap local proxy backed by
something like GLM-5.2. But you want **both**: Opus's reasoning for design/planning, and
GLM-5.2's cheap execution for the bulk of code work. A single `ANTHROPIC_BASE_URL` can't do that.

## forky's answer

Forky is a local proxy that impersonates the Anthropic Messages API. The `claude-forky`
wrapper points Claude Code at it for that session only;
forky decides per-request which backend should handle it and translates the request format
if the backend isn't Anthropic.

```
claude-forky ──► forky :3458 ──┬──► api.anthropic.com   (OAuth, Opus/Sonnet)
                               │     [no translation needed]
                               │
                               └──► LiteLLM :4000 ──► Huawei MaaS  (GLM-5.2)
                                     [Anthropic → OpenAI translation]
```

Plain `claude` should not inherit `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`, or
`ANTHROPIC_API_KEY`; otherwise Claude Code disables Claude.ai MCP connectors.

## The routing decision

`src/route.ts`'s `decideRoute()` inspects each request and returns one of:

| Reason | Condition | Target |
|---|---|---|
| `sentinel` | `~/.forky/opus` file exists | OAuth Opus (`FORKY_PLAN_MODEL` or `FORKY_OPUS_MODEL`) |
| `opus` | model name starts with `claude-opus-` | OAuth Opus |
| `vision` | request contains an image block | OAuth Opus (`FORKY_VISION_MODEL` or `FORKY_OPUS_MODEL`) |
| `classifier` | no tools present, `claude-*` model | OAuth Sonnet |
| `execution` | everything else | exec backend (GLM-5.2) |

The `execution` case is the common one — real Claude Code agentic turns always carry tools.

Forky reads `~/dev/forky/.env` when the service starts. Set `FORKY_OPUS_MODEL`
to change the default OAuth Opus model for plan/sentinel/review/vision routes,
then restart `forky.service`. Use `FORKY_PLAN_MODEL`, `FORKY_VISION_MODEL`, or
`FORKY_REVIEW_MODEL` only when that route should differ from the shared Opus
default.

## How plan mode is detected

Plan mode (`Shift+Tab`) is a **client-side** Claude Code state — it's invisible in the API
request. Forky can't see it directly. The solution is a **hook**:

1. `~/.claude/settings.json` registers a `UserPromptSubmit` hook → `forky-hook`.
2. When the user submits a prompt in plan mode, Claude Code fires the hook with the plan
   context. The hook creates a sentinel file `~/.forky/opus`.
3. Forky sees the sentinel and routes the next request(s) to Opus.
4. A `PostToolUse` hook on `ExitPlanMode` clears the sentinel.

## How OAuth is injected

Forky reads `~/.claude/.credentials.json` (the file `claude /login` creates). It:
- Extracts the access token and refreshes it via `console.anthropic.com/v1/oauth/token`
  when it's near expiry.
- Sends the request to `api.anthropic.com` with the real bearer token.
- Sets `cache_control: ephemeral` on the last system block and last tool definition,
  enabling Anthropic's prompt caching (~80% input token savings on repeated context).
- Normalizes prompt-cache TTL order before dispatch. Anthropic rejects a later
  `ttl: "1h"` marker after any normal 5-minute marker, and Forky's added tool
  marker can otherwise trip that rule when Claude Code already supplied an
  extended-cache system marker.

The user's Pro/Max subscription covers the Opus/Sonnet turns. The exec backend (GLM-5.2)
is paid separately via Huawei MaaS.

## How Anthropic ↔ OpenAI translation works

When routing to the exec backend, forky translates the Anthropic Messages format to OpenAI
Chat Completions format:
- `system` blocks → flattened into the `system` message
- `system`/`developer` roles inside `messages` → normalized into top-level `system`
  before validation (needed for Claude Code 2.1.x)
- `tools` → OpenAI function-calling schema
- Image `content` blocks → `image_url` (though the vision branch usually catches these first)
- The response is translated back to Anthropic format for Claude Code.

## Why the vision branch exists

GLM-5.2 has no vision capability. Without the vision branch, any request containing a
screenshot (common in agentic coding — Claude Code reads the screen) would route to GLM-5.2
and fail. The `hasImageContent()` helper scans message contents and nested `tool_result.content`
for `type: "image"` blocks and reroutes those requests to Opus, which has vision.

## Why CLAUDE_CODE_AUTO_COMPACT_WINDOW=180000

MaaS's GLM-5.2 has a hard input limit of ~196608 tokens. Claude Code's default context
window assumption is 200K. Without intervention, Claude Code would happily send a 198K-token
request that MaaS rejects with a 400. Setting `CLAUDE_CODE_AUTO_COMPACT_WINDOW=180000` makes
Claude Code auto-compact at 180K, leaving ~16K headroom for one 8K output + tool results
before the next compaction trigger.

## Why claude-forky does not set ANTHROPIC_AUTH_TOKEN

Older forky setups exported `ANTHROPIC_AUTH_TOKEN=forky-local` globally. Claude Code now
disables Remote Control, `/schedule`, notification preferences, and Claude.ai MCP connectors
whenever `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_API_KEY`, or an `apiKeyHelper` is present, even
if the user is logged into Claude.ai. Forky does not need inbound auth on loopback, so the
wrapper uses only `ANTHROPIC_BASE_URL` and explicitly unsets auth-token/API-key env vars.

## Difference from ccr (claude-code-router)

| | forky | ccr |
|---|---|---|
| Ports | 3458 | 3456 |
| Auth | OAuth (Pro/Max) **and** API key | API key only |
| Plan mode | routes to Opus via OAuth | routes to whatever the config says (usually GLM) |
| Vision | routes to Opus | no special handling |
| Use case | hybrid Opus + GLM in one command | GLM-only (or other single backend) |
| Prompt caching | yes (ephemeral cache_control) | depends on backend |

Forky's key advantage: **you keep Claude OAuth for hard planning and vision while spending
GLM tokens on execution**. Ccr sends everything to one backend.

## Coexistence

Both proxies can run simultaneously — they use different ports. `claude-glm` (the ccr wrapper)
sets its own `ANTHROPIC_BASE_URL` inside the wrapper script. So:
- `claude` → Anthropic/Claude.ai OAuth + connectors
- `claude-forky` → forky → hybrid (Opus + GLM)
- `claude-glm` → ccr → GLM only
