# hcloud-mcp-server

An MCP (Model Context Protocol) server that exposes the Huawei Cloud CLI (`hcloud`) as a single tool that AI assistants can navigate interactively — just like a human would.

## How It Works

The server registers **one tool**: `hcloud_cli`. The AI navigates hcloud using `--help` at each level:

```
hcloud_cli("--help")                        → list all services
hcloud_cli("IAM --help")                    → list IAM operations
hcloud_cli("IAM ListCustomPolicies --help") → show parameters
hcloud_cli("IAM ListCustomPolicies")        → execute
```

This mirrors how a human discovers and uses the CLI, requires only 1 tool definition in the LLM context (~300 tokens), and works within any model's context window.

## Features

- **Single tool** — minimal context footprint, works with any model size
- **Interactive discovery** — AI navigates `--help` menus naturally
- **Safety layer** — destructive operations (Delete, Detach, Revoke, etc.) require `confirm=true`; default is dry-run mode
- **Structured output** — JSON output forced automatically (`--cli-output=json`)
- **Configurable** — timeout, binary path, safety settings

## Requirements

- Python 3.10+
- [hcloud CLI](https://support.huaweicloud.com/intl/en-us/productdesc-hcli/hcli_01.html) installed and configured with authentication

## Installation

```bash
pip install hcloud-mcp-server
```

Or from source:

```bash
git clone <repo-url>
cd hcloud-mcp-server
pip install -e .
```

Verify:

```bash
hcloud-mcp --help
```

## Running

```bash
# Start the MCP server (stdio transport)
hcloud-mcp

# With a config file
hcloud-mcp --config /path/to/config.json

# With debug logging
hcloud-mcp --debug
```

## Configuration

### Config file

Create a JSON config file (see `config.example.json`):

```json
{
  "execution": {
    "timeout_seconds": 30,
    "cli_output": "json",
    "hcloud_binary": "hcloud"
  }
}
```

### Environment variables

| Variable | Description |
|----------|-------------|
| `HCLOUD_MCP_CONFIG` | Path to config JSON file |

## Tool Reference

### `hcloud_cli`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `command` | string | Yes | hcloud CLI arguments (everything after `hcloud`) |
| `confirm` | boolean | No | Set `true` to execute destructive operations (default: `false` = dry-run) |

**Navigation flow:**

1. `command="--help"` — list all available services
2. `command="<Service> --help"` — list operations for a service
3. `command="<Service> <Operation> --help"` — show parameters and descriptions
4. `command="<Service> <Operation> --param1=value1"` — execute the operation

**Parameter format:** Always use `--param=value` (equals sign required by hcloud).

**Safety:** Operations containing `Delete`, `Remove`, `Revoke`, `Detach`, `Disassociate`, `Cancel`, or `Force` are classified as destructive. Without `confirm=true`, they run with `--dryrun` first.

## Adding to AI Tools

The hcloud MCP server uses standard **stdio transport**, compatible with any MCP client.

### opencode

Add to `~/.opencode/opencode.json`:

```json
{
  "mcp": {
    "hcloud": {
      "type": "local",
      "command": ["hcloud-mcp"],
      "enabled": true
    }
  }
}
```

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "hcloud": {
      "command": "hcloud-mcp",
      "args": []
    }
  }
}
```

### Cursor

Add to `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "hcloud": {
      "command": "hcloud-mcp",
      "args": []
    }
  }
}
```

### VS Code (GitHub Copilot)

Add to `.vscode/mcp.json`:

```json
{
  "servers": {
    "hcloud": {
      "type": "stdio",
      "command": "hcloud-mcp",
      "args": []
    }
  }
}
```

### Windsurf

Add to `~/.windsurf/mcp.json`:

```json
{
  "mcpServers": {
    "hcloud": {
      "command": "hcloud-mcp",
      "args": []
    }
  }
}
```

### Goose

Add to `~/.config/goose/config.yaml`:

```yaml
extensions:
  hcloud:
    type: stdio
    command: hcloud-mcp
    args: []
```

### Any MCP Client (generic)

| Setting | Value |
|---------|-------|
| Command | `hcloud-mcp` |
| Args | `[]` |
| Transport | stdio |

## Example AI Session

```
User: How many custom IAM policies do I have?

AI: Let me check your IAM policies.

→ hcloud_cli(command="--help")
  [sees IAM in the service list]

→ hcloud_cli(command="IAM --help")
  [sees ListCustomPolicies in the operations list]

→ hcloud_cli(command="IAM ListCustomPolicies --help")
  [sees no required parameters]

→ hcloud_cli(command="IAM ListCustomPolicies")
  { "total_number": 2, "roles": [...] }

AI: You have 2 custom IAM policies.
```

```
User: Delete the policy with ID abc123

AI: This is a destructive operation. Let me run it in dry-run mode first.

→ hcloud_cli(command="IAM DeleteCustomPolicy --role_id=abc123")
  ⚠️ DRY RUN — no changes made.
  Set confirm=true to execute for real.

→ hcloud_cli(command="IAM DeleteCustomPolicy --role_id=abc123", confirm=true)
  ✅ Executed (confirmed destructive operation):
  { "message": "Delete success" }

AI: The policy has been deleted.
```

## Development

```bash
# Install in editable mode
pip install -e .

# Run tests
pytest tests/ -v

# Run with debug logging
hcloud-mcp --debug
```

## Troubleshooting

**Server fails to start:**
- Ensure `hcloud` is installed and in PATH: `which hcloud`
- Verify auth: `hcloud IAM ListCustomPolicies`

**Tool calls return errors:**
- Check hcloud profile: `hcloud configure list`
- Enable debug logging: `hcloud-mcp --debug`

**AI doesn't know how to use the tool:**
- The tool description includes navigation instructions
- Remind the AI: "Use hcloud_cli with --help to discover operations"
