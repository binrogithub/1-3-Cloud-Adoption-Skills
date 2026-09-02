# Installation

Safe installation and validation for the Claude-MaaS Universal Delegate Router.
All commands below read the API key from **stdin**, never from argv.

## Prerequisites

- A POSIX system with `bash` and Python ≥ 3.7.
- The official `claude` CLI on PATH. The universal installer (`install.sh`)
  installs Claude Code automatically if it is missing (unless
  `--no-install-claude` is given).
- An Anthropic-compatible MaaS endpoint URL and a valid API key.

## Option 1 — Universal agent delegation (`install.sh`)

Installs Claude Code if missing, writes the MaaS client config, and installs an
additive delegation Skill + routing policy into the selected host agents. The
host agents keep their own provider and authentication.

Interactive:

```bash
./scripts/install.sh
# Prompts for an Anthropic-compatible API URL and a hidden API key.
```

Non-interactive (key on stdin, URL on argv):

```bash
printf '%s\n' "$MAAS_KEY" | ./scripts/install.sh --non-interactive \
  --api-url https://example.com/anthropic/v1/messages --agents codex,cursor
```

Flags:

| Flag | Purpose |
| --- | --- |
| `--api-url URL` | Anthropic-compatible Messages endpoint or base URL (HTTPS required; localhost allowed for tests) |
| `--model MODEL` | MaaS model (default `glm-5.2`) |
| `--agents LIST` | Comma-separated subset of `codex,copilot,cursor,opencode` (default: all) |
| `--non-interactive` | Require `--api-url`; read the key as one line on stdin |
| `--no-install-claude` | Fail instead of auto-installing missing Claude Code |
| `--skip-live-verify` | Accepted for offline automation |
| `--force` | Replace owned installation files |

The installer normalizes the URL by stripping a trailing `/v1/messages` so the
launcher config holds the base URL. It then runs `maas-delegate doctor` to
confirm the installed binary is runnable.

## Key rotation

Re-run `install.sh` with the new key. Rotation is idempotent (atomic temp-file
+ rename, 0600 preserved). Rotate after any interactive-channel key exposure.

```bash
printf '%s\n' "$NEW_MAAS_API_KEY" | ./scripts/install.sh --non-interactive \
  --api-url https://api-ap-southeast-1.modelarts-maas.com/anthropic
```

Re-running the installer is **idempotent**.

## Validation

### Offline (no key, no network)

```bash
python3 scripts/verify-skill-release.py .
```

Verifies the self-contained package: manifest/schema integrity, exact file set,
SHA-256 hashes, executable modes, and forbidden content/path patterns. A clean
run confirms the package is complete and unmodified.

### Live (requires key on stdin)

```bash
printf '%s\n' "$MAAS_API_KEY" | ./scripts/install.sh --non-interactive \
  --api-url https://api-ap-southeast-1.modelarts-maas.com/anthropic
```

The installer runs `maas-delegate doctor` to confirm the installed binary is
runnable. Exit code 0 means the install and health check passed.

## Advisory routing policy

The universal installer installs the selected host-agent Skill and its advisory
routing policy. It never changes the host provider, model, or authentication,
and it does not force delegation by keyword.
