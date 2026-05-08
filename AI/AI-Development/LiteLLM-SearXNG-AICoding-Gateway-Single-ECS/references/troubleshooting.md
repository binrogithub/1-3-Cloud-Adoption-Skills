# Troubleshooting

Every issue we have hit on this stack with the actual fix. Read this when a
deployment misbehaves; many symptoms have non-obvious root causes.

## Provisioning

### `router quota exceeded` when creating a VPC

The Huawei Cloud project has a per-region cap on VPCs. New deployments hit it
when other projects already filled the quota.

**Fix.** Reuse the default VPC and an existing subnet. Do not delete other
projects' VPCs to make room. The provisioning script must list VPCs and pick
the largest available subnet, not always create a new one.

### CSS creation fails with `COMMON disk sold out`

Specific CSS flavors require a specific disk type and a specific AZ. The
`COMMON` disk type often shows as available in docs but sold out at runtime.

**Fix.** Switch the disk type to `HIGH` (or `ULTRAHIGH`) and retry. Keep the
flavor `ess.spec-4u8g`; the disk type is the dimension that flips.

### Ubuntu image refuses `ubuntu` user; `root` works

Some Huawei Ubuntu 22.04 images bake `PermitRootLogin yes` and disable the
`ubuntu` account. The cloud-init `users` block does not override this on the
image we use.

**Fix.** Connect as `root`. The provisioning script must record the working
username in the state file (`ssh_user: root`).

### `REMOTE HOST IDENTIFICATION HAS CHANGED!` after rebuild

EIPs are sometimes recycled to a new ECS with the same address. The host key
is fresh and `~/.ssh/known_hosts` flags it as a possible MITM.

**Fix.** `ssh-keygen -f ~/.ssh/known_hosts -R <ip>` and reconnect with
`-o StrictHostKeyChecking=accept-new`.

### `cloud-init` install step did not run

Heredoc-heavy `cloud-init` `runcmd` or `write_files` blocks parse fine in a
linter but trip the in-image cloud-init parser.

**Fix.** Bring the host up bare. Push install scripts over SSH afterwards.
Treat cloud-init as "create one user, drop one keypair" only.

## LiteLLM

### `Unable to find Prisma binaries. Please run 'prisma generate' first.`

Pip installs the Prisma Python package but does not fetch the platform-specific
query engine. LiteLLM's `--use_prisma_db_push` runs Prisma only after the
client is generated.

**Fix.**

```
SCHEMA=$(find /opt/litellm-venv -name schema.prisma | head -1)
export PATH=/opt/litellm-venv/bin:$PATH
/opt/litellm-venv/bin/prisma generate --schema "$SCHEMA"
/opt/litellm-venv/bin/prisma db push --schema "$SCHEMA" --accept-data-loss --skip-generate
```

`db push` actually downloads the engine and creates tables. Order matters.

### `prisma.engine.errors.NotConnectedError: Not connected to the query engine`

Several causes share this single error message. Check them in order.

1. **Prisma client was generated but the engine binary is unreadable.**
   `prisma generate` bakes the absolute engine path into the generated client
   (e.g., `/root/.cache/prisma-python/.../query-engine-debian-openssl-3.0.x`).
   When the LiteLLM service runs as `litellm`, that path is `0700` and
   unreadable.

   **Fix.** Either:
   - `chmod -R o+rX /root/.cache/prisma-python` (quick), or
   - regenerate as the `litellm` user with `HOME=/opt/litellm` (cleaner).

2. **The `prisma` CLI is not on `PATH` for the systemd service.**
   LiteLLM's startup runs `subprocess.run(["prisma"], capture_output=True)`.
   Under systemd the default `PATH` is `/usr/sbin:/usr/bin:/sbin:/bin` and
   `/opt/litellm-venv/bin/prisma` is not visible.

   **Fix.** Add to `/etc/litellm/litellm.env`:
   `PATH=/opt/litellm-venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin`.

3. **Prisma's config loader cannot read `pyproject.toml`** because the cwd
   resolves into a directory the service user cannot access.

   **Fix.** Set `HOME=/opt/litellm` in `/etc/litellm/litellm.env`. Set
   `WorkingDirectory=/opt/litellm` in the unit. The `litellm` user owns
   `/opt/litellm`.

4. **`PRISMA_QUERY_ENGINE_BINARY`** points at a stale binary after a LiteLLM
   upgrade (engine SHA changed).

   **Fix.** Re-run `prisma generate`, then update the env var to the new
   `query-engine-debian-openssl-3.0.x` path.

### LiteLLM service is `active` but `:4000` has no listener

LiteLLM is in startup. Watch `journalctl -u litellm.service -f`. If you see
`Application startup complete.` the listener appears within seconds. If you
see Prisma traceback loops, the schema/engine is not bootstrapped.

### `/health` shows `unhealthy_endpoints` for the model you wired

The mapped upstream model id is wrong. Confirm with a direct MaaS call from
the ECS:

```
/opt/litellm-venv/bin/python -c "
from openai import OpenAI
c = OpenAI(api_key=open('/etc/litellm/litellm.env').read().split('HUAWEI_MAAS_API_KEY=')[1].split()[0],
           base_url='https://api-ap-southeast-1.modelarts-maas.com/openai/v1')
print(c.chat.completions.create(model='glm-5.1',
      messages=[{'role':'user','content':'hi'}]).choices[0].message.content)
"
```

If that works and the LiteLLM proxied call fails, the typo is in
`config.yaml > model_list[*].litellm_params.model`. Use `openai/glm-5.1`,
not `glm-5.1`.

### `/model/info` shows zero token cost

You forgot `input_cost_per_token` / `output_cost_per_token` on the
`model_list` entry. Budgets will not enforce. Add the validated values.

## SearXNG / MCP

### MCP returns 200 OK but `tools/list` is empty

The FastMCP process started, but the `@mcp.tool` registration failed silently
(usually an import error in the tool body). Check `journalctl -u
searxng-mcp.service`.

### `ModuleNotFoundError: No module named 'fastmcp.server.auth.providers.bearer'`

Path moved between FastMCP releases.

**Fix.** `from fastmcp.server.auth import StaticTokenVerifier`.

### MCP fails with `406 Not Acceptable`

Client did not send `Accept: application/json,text/event-stream`. Both must
be present, comma-separated, no spaces. FastMCP's HTTP transport rejects
plain `application/json`.

### SearXNG returns HTML even with `format=json`

`search.formats` in `settings.yml` does not include `json`.

**Fix.** Add `- json` to the formats list and restart the container.

### SearXNG `results: []` for everything

Engine rate limits or captcha gating. Unrelated to your config. Wait a few
minutes, or disable noisy engines in `settings.yml`.

## ccr / claude-glm

### ccr returns `401 Unauthorized` from upstream

`$LITELLM_VIRTUAL_KEY` is empty in ccr's process. Two causes:

1. The wrapper's env file (`~/.config/claude-glm/env`) does not export
   `LITELLM_VIRTUAL_KEY`.
2. ccr was started from a different shell that did not source the env file.

**Fix.** Always start ccr through the wrapper, or at least source the env
file in the same shell. The wrapper guards against this by refusing to start
ccr when the var is empty.

### ccr returns 200 but model id in chunks is `glm-5.1`, not `huawei-glm-5.1`

ccr is hitting MaaS directly. The Provider `api_base_url` is wrong; verify
it is `http://<ECS_PUBLIC_IP>:4000/v1/chat/completions`.

### `claude-glm` shows the model picker

The wrapper did not inject `--model`. Inspect the wrapper's `inject_model`
logic; subcommands like `agents`, `auth`, `mcp`, `update` deliberately skip
injection.

### `claude-glm` works once, fails after sleep

The LiteLLM Postgres connection pool dropped. LiteLLM's auto-reconnect handles
this, but the first call after a long idle can show a one-off retry. Watch
`journalctl -u litellm.service`. No action needed.

### `400 the prompt length N must less than the maximum input length 196608`

GLM-5.1's hard input ceiling is **196608 tokens**. The error surfaces from
LiteLLM as a 400 with the upstream message `Inference failed: the prompt
length N must less than the maximum input length 196608`. This is the model
limit, not a LiteLLM, ccr, or network fault. ccr will not retry it; Claude
Code shows it as `API Error: 400 Error from provider(litellm,...)`.

Two settings combine to make this trip in long coding sessions:

1. The wrapper exports `DISABLE_COMPACT=true`, which turns Claude Code's
   automatic conversation compaction off. The session keeps growing past the
   model's window.
2. `CLAUDE_CODE_MAX_CONTEXT_TOKENS=190000` leaves only ~6.6k headroom under
   the 196608 cap, so tool definitions, system prompt, and the next user
   turn easily overflow.

**Fix.**

- Wrapper defaults: set `DISABLE_COMPACT=false` and
  `CLAUDE_CODE_MAX_CONTEXT_TOKENS=180000` (~8% headroom).
- For an existing stuck session, run `/compact` (Claude Code summarizes
  history in place) or `/clear` (fresh session) before continuing.
- Single oversize requests (e.g., dumping a whole repository in one turn)
  cannot be compacted away. Split the task.

`longContextThreshold` in `~/.claude-code-router/config.json` only matters
if a separate long-context Provider exists. We point all four router slots
at the same `litellm,huawei-glm-5.1`, so that field has no effect on this
error.

## Security group

### Laptop's outbound IP changes mid-session

Mobile networks, VPNs, and ISP rebalancing. Symptom: SSH/curl to the ECS
times out from the laptop. In `claude-glm` this surfaces as a long stall
followed by `Retrying in 10s · attempt N/10 · API_TIMEOUT_MS=...`, because
ccr's call to LiteLLM at `:4000` is being silently dropped by the SG.

**Fix.** Get the new IP (`curl -s https://ifconfig.me`). Add a new SG rule
for the new `/32` on the affected ports (typically 22, 4000, 8788) and remove
the stale rule. Do not relax to `0.0.0.0/0`. When `claude-glm` retries
loop on `API_TIMEOUT_MS=...`, check `curl ifconfig.me` first; almost every
mid-session "retry storm" is an IP drift, not a server-side fault.

### SSH works but `:4000` does not

Two SG rules are needed (port 22 and port 4000). Adding only one is the
common typo. List rules and verify both are present for the same CIDR.

## State drift

### State file says resources `DELETED` but they exist in the console

A previous session recorded `DELETED` for an earlier batch with the same
prefix. New resources created later under a longer prefix did not update the
state. Always re-query the cloud (ECS, CSS, OBS list APIs) before trusting
the local state file.

### Multiple SSH keypairs in `~/.ssh/`

Failed runs leave behind `gov-rag-<TIMESTAMP>` keypairs. Identify the live
one by listing keypairs in the cloud and matching the public-key line. Delete
the orphans only after confirming nothing in the cloud references them.

### MCP token in three places drifts

If you rotate the bearer token, you must update three locations: the systemd
unit `Environment=MCP_TOKEN=`, the laptop's local copy, and the entry in
`~/.claude-glm-config/.claude.json`. Forgetting one yields silent failures.
A short script that writes all three is worth it for shared environments.
