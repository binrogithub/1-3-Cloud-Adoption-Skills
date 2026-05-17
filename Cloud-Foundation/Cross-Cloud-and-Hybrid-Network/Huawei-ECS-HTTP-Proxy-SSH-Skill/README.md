# Huawei ECS HTTP Proxy SSH Skill

This skill helps an AI coding agent run SSH commands on a Huawei Cloud ECS, or another Linux host, when direct SSH is blocked by a corporate network and access must go through an HTTP or HTTPS proxy using `CONNECT`.

## Scenario

Corporate workstations may be able to reach the internet only through an HTTP proxy. In that environment, direct `ssh` or TCP reachability checks can time out even when the ECS is healthy and the security group is correct for the proxy path. This skill provides a repeatable troubleshooting and execution flow for proxy-based SSH access.

## Included Assets

- `SKILL.md`: agent-facing workflow, safety rules, and troubleshooting guidance.
- `agents/openai.yaml`: runtime metadata for OpenAI-compatible agent invocation.
- `scripts/http_proxy_ssh_exec.py`: Paramiko-based helper that opens an HTTP or HTTPS proxy `CONNECT` socket and executes commands through it with host key verification on by default.

## Security Rules

- Do not commit private keys, SSH passphrases, proxy passwords, ECS credentials, API keys, or bearer tokens.
- Use placeholders for hosts, users, ports, and local key paths in documentation.
- Pass encrypted key passphrases only through the current process environment and remove them after use.
- Verify SSH host keys by default. Only bypass that check for one-off diagnostics when the user explicitly accepts the MITM risk.
- Prefer `/32` security group rules for the current client or proxy egress IP.

## Expected Outputs

- Verified proxy `CONNECT` reachability to the ECS SSH port.
- SSH banner proof for network diagnosis.
- Read-only remote command output for ECS preflight checks.
- Clear failure interpretation for direct TCP timeout, proxy 504, encrypted key errors, and corporate proxy interception pages.
