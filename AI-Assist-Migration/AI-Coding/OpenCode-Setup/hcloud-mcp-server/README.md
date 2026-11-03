# hcloud-mcp-server

An MCP (Model Context Protocol) server that exposes Huawei Cloud infrastructure through **150 structured tools** plus a generic `hcloud_cli` catch-all — for AI assistants to discover and manage Huawei Cloud resources.

> **150 tools · 34 services · 1 server** — ECS, VPC, CCE, RDS, VPN, OBS, IAM, and 27 more.

## How It Works

The server registers **150 tools**: 149 structured read-only tools for infrastructure discovery + 1 generic `hcloud_cli` for write operations and anything not covered by structured tools.

```
hcloud_list_servers(region="la-north-2")           → structured tool, type-safe
hcloud_list_vpn_gateways(region="la-north-2")      → new VPN v5 tools
hcloud_list_drs_jobs(region="la-north-2")           → new DRS tools
hcloud_cli("IAM CreateCustomPolicy --name=...")    → generic CLI for writes
```

Structured tools provide type-safe parameters, JSON schema validation, and MCP annotations (`readOnlyHint=True`). The generic `hcloud_cli` handles write operations with a safety layer (dry-run by default, `confirm=true` for execution).

## Features

- **150 tools** — 149 structured read-only + 1 generic CLI catch-all
- **35 services covered** — ECS, VPC, EIP, EVS, IAM, ELB, RDS, CCE, AS, OBS, DNS, KMS, CES, IMS, NAT, DCS, DDS, SMN, VPN, DRS, SWR, OMS, SMS, CBR, CCI, MRS, DWS, GaussDB, ER, CFW, CodeArts, DataArts, Organizations, LTS, BSS
- **MCP annotations** — `readOnlyHint=True` on structured tools, `destructiveHint=True` on `hcloud_cli`, `title` on all tools
- **Output truncation** — large responses truncated to 50KB with pagination hint
- **Safety layer** — destructive operations require `confirm=true`; default is dry-run mode
- **Help deduplication** — older API versions hidden from `--help` output
- **Configurable** — timeout, binary path, safety settings

## Requirements

- Python 3.10+
- [hcloud CLI (KooCLI)](https://support.huaweicloud.com/intl/en-us/productdesc-hcli/hcli_01.html) installed and configured with authentication

### Install KooCLI

```bash
curl -LO https://ap-southeast-3-hwcloudcli.obs.ap-southeast-3.myhuaweicloud.com/cli/latest/huaweicloud-cli-linux-amd64.tar.gz
tar xzf huaweicloud-cli-linux-amd64.tar.gz
sudo mv hcloud /usr/local/bin/
hcloud --version
```

### Configure credentials

```bash
hcloud configure set --cli-mode=AKSK --cli-region=la-north-2 --cli-agree-privacy-statement=true
hcloud configure set --cli-access-key=YOUR_AK --cli-secret-key=YOUR_SK
hcloud configure set --cli-region=la-north-2
echo y | hcloud IAM ListCustomPolicies   # verify (first run needs privacy agreement)
```

Get your AK/SK from the Huawei Cloud console: **My Credentials → Access Keys**.

## Installation

### Option A: From GitHub (recommended)

```bash
git clone https://github.com/binrogithub/hcloud-mcp-server.git
cd hcloud-mcp-server
pip install --upgrade pip setuptools   # needed on older systems (e.g. Ubuntu 22.04)
pip install .
```

### Option B: From source tarball

```bash
curl -LO http://huaweilatam.com/downloads/hcloud-mcp-server.tar.gz
tar xzf hcloud-mcp-server.tar.gz
cd hcloud-mcp-server
pip install --upgrade pip setuptools   # needed on older systems (e.g. Ubuntu 22.04)
pip install .
```

### Verify

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
