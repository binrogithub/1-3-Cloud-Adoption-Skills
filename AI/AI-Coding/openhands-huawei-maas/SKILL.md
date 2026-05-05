---
name: openhands-huawei-maas
description: Configure, run, verify, or troubleshoot OpenHands with Huawei Cloud MaaS / ModelArts MaaS through an OpenAI-compatible endpoint. Use when Codex needs to install OpenHands CLI or uv, run OpenHands locally with Docker or CLI, set LLM_API_KEY/LLM_BASE_URL/LLM_MODEL, use MaaS models such as glm-5.1 or qwen coder models, verify MaaS connectivity, or explain how OpenHands replaces GitHub Copilot-style agent workflows with Huawei MaaS.
---

# OpenHands Huawei MaaS

## Core Pattern

Use OpenHands as the coding agent/runtime and Huawei Cloud MaaS as the OpenAI-compatible LLM backend.

```text
OpenHands Web GUI / CLI
  -> LiteLLM OpenAI-compatible provider
  -> Huawei Cloud MaaS / ModelArts MaaS /openai/v1
  -> model such as glm-5.1
```

Do not treat MaaS as an OpenHands plugin. OpenHands calls it through the standard LLM environment variables:

```bash
LLM_API_KEY
LLM_BASE_URL
LLM_MODEL
```

Use the `openai/` prefix in `LLM_MODEL` so OpenHands/LiteLLM routes the call through an OpenAI-compatible provider.

## Safe Defaults

- Never print or write raw MaaS API keys into files, logs, final answers, shell history snippets, or examples.
- Prefer reading keys from existing environment variables.
- If a key must be reused from shell history at the user's request, extract it into a process variable and do not echo it.
- Show only masked key status such as `LLM_API_KEY_SET=yes`.
- Use the region-specific MaaS endpoint that matches the user's enabled model.

Common MaaS base URLs:

```bash
# Chinese mainland
https://api.modelarts-maas.com/openai/v1

# International / CN-Hong Kong
https://api-ap-southeast-1.modelarts-maas.com/openai/v1
```

Common model values:

```bash
openai/glm-5.1
openai/qwen3-coder-480b-a35b-instruct
```

Only use models enabled in the user's MaaS region.

## Local Docker GUI

Use Docker when the user wants the OpenHands browser UI or the host does not already have the CLI.

```bash
export HUAWEI_MAAS_API_KEY='...'
export HUAWEI_MAAS_BASE_URL='https://api-ap-southeast-1.modelarts-maas.com/openai/v1'
export HUAWEI_MAAS_MODEL='openai/glm-5.1'

docker run -d --pull=always \
  -e AGENT_SERVER_IMAGE_REPOSITORY=ghcr.io/openhands/agent-server \
  -e AGENT_SERVER_IMAGE_TAG=1.19.1-python \
  -e LOG_ALL_EVENTS=true \
  -e LLM_API_KEY="$HUAWEI_MAAS_API_KEY" \
  -e LLM_BASE_URL="$HUAWEI_MAAS_BASE_URL" \
  -e LLM_MODEL="$HUAWEI_MAAS_MODEL" \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v ~/.openhands:/.openhands \
  -p 3000:3000 \
  --add-host host.docker.internal:host-gateway \
  --name openhands-app \
  docker.openhands.dev/openhands/openhands:1.7
```

Open:

```text
http://localhost:3000
```

Verify the container received non-secret settings:

```bash
docker exec openhands-app sh -lc \
  'printf "LLM_BASE_URL=%s\nLLM_MODEL=%s\nLLM_API_KEY_SET=%s\n" "$LLM_BASE_URL" "$LLM_MODEL" "$(test -n "$LLM_API_KEY" && echo yes || echo no)"'
```

## CLI Installation

Use OpenHands CLI when the user wants terminal workflows, headless automation, JSON output, or command-line replacement for Copilot-style coding tasks.

Install `uv` first. Prefer the official installer; if `curl` is broken or certificates are unavailable, use `pip3 install --user uv`.

```bash
pip3 install --user uv
export PATH="$HOME/.local/bin:$PATH"
uv tool install openhands --python 3.12
```

Persist PATH when needed:

```bash
printf '\nexport PATH="$HOME/.local/bin:$PATH"\n' >> ~/.bashrc
```

Run interactive CLI:

```bash
export LLM_API_KEY="$HUAWEI_MAAS_API_KEY"
export LLM_BASE_URL='https://api-ap-southeast-1.modelarts-maas.com/openai/v1'
export LLM_MODEL='openai/glm-5.1'

openhands --override-with-envs
```

Run headless:

```bash
openhands --override-with-envs --headless -t 'Analyze this repository and propose a cloud modernization plan.'
```

Run headless JSON:

```bash
openhands --override-with-envs --headless --json -t 'Reply with OK only.'
```

Use `--override-with-envs`; otherwise OpenHands may ignore `LLM_API_KEY`, `LLM_BASE_URL`, and `LLM_MODEL` in favor of stored settings.

## MaaS Connectivity Smoke Test

Before blaming OpenHands, test MaaS directly from the same runtime when possible.

From the OpenHands Docker container:

```bash
docker exec -i openhands-app python3 - <<'PY'
import json, os, urllib.request

base = os.environ["LLM_BASE_URL"].rstrip("/")
model = os.environ["LLM_MODEL"].removeprefix("openai/")
key = os.environ["LLM_API_KEY"]

req = urllib.request.Request(
    base + "/chat/completions",
    data=json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "Reply OK only"}],
        "temperature": 0,
        "max_completion_tokens": 8,
    }).encode(),
    headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
    method="POST",
)

with urllib.request.urlopen(req, timeout=60) as r:
    print("maas_ok", r.status, model)
PY
```

Expected:

```text
maas_ok 200 glm-5.1
```

## Common Troubleshooting

- `401` or authentication error: confirm the MaaS API key is active and injected as `LLM_API_KEY`.
- `404`, model not found, or deployment not found: confirm the MaaS region and model name; remove the `openai/` prefix only for direct MaaS API tests, not for OpenHands/LiteLLM config.
- OpenHands ignores env vars: add `--override-with-envs` for CLI.
- Docker sandbox errors: confirm Docker is running and `/var/run/docker.sock` is mounted.
- `curl` or `git-remote-https` fails with OpenSSL/LDAP symbol errors: use Python `urllib` for API smoke tests and warn that HTTPS git clone may be affected until system libraries are fixed.
- Interactive terminal renders poorly: use `--headless --json` or set `TTY_INTERACTIVE=1` only if an interactive TTY is actually available.

## User-Facing Summary Template

When reporting success, include only non-secret status:

```text
OpenHands: running
URL: http://localhost:3000
LLM_BASE_URL: <region MaaS endpoint>
LLM_MODEL: openai/<model>
MaaS API Key: injected, not printed
MaaS connectivity: maas_ok 200 <model>
```
