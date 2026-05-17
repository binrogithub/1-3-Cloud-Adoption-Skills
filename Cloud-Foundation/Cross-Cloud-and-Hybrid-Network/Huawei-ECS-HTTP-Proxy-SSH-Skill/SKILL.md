---
name: huawei-ecs-http-proxy-ssh
description: Use this skill when the user needs Codex to SSH into a remote Huawei Cloud ECS, or any Linux host, from a corporate network where direct SSH is blocked and access must go through an HTTP/HTTPS proxy using CONNECT. It covers checking proxy variables, proving TCP reachability, handling encrypted private keys without persisting passphrases, and executing remote commands reliably.
---

# Huawei ECS SSH Through HTTP Proxy

Use this skill when SSH to an ECS works only through a corporate HTTP proxy. Prefer this flow when direct `ssh` or `Test-NetConnection` times out but the user says HTTP proxy access is required.

## Required Inputs

- Host and SSH port, e.g. `<ecs_public_ip>:4444`.
- SSH user, usually `root` or `ubuntu`.
- Private key path.
- Known-hosts file path if the ECS host key is not already in the user's standard SSH known-hosts store.
- Proxy source:
  - Existing `HTTP_PROXY` / `HTTPS_PROXY` environment variables, or
  - explicit proxy URL.
- If the private key is encrypted, get the passphrase from the user only for the current task. Do not write it to files.

## Rules

- Never persist SSH passphrases, proxy passwords, ECS credentials, API keys, or bearer tokens in skill files or generated artifacts.
- Prefer `/32` security group rules for the current client egress IP. Do not suggest `0.0.0.0/0` unless the user explicitly accepts that risk.
- When using a passphrase, pass it through an environment variable for a single command and remove that variable immediately afterward.
- Verify SSH host keys by default. Only use `--insecure-accept-host-key` for short-lived diagnostics when the user explicitly accepts the MITM risk.
- If standard OpenSSH `ProxyCommand` hangs on Windows, use `scripts/http_proxy_ssh_exec.py`; it creates the HTTP CONNECT socket itself and hands it to Paramiko.
- Treat a proxy `302` security warning page or `netentsec` response as corporate proxy interception, not an ECS service response.

## Workflow

1. Check proxy environment:

   ```powershell
   Get-ChildItem Env:HTTP_PROXY,Env:HTTPS_PROXY,Env:ALL_PROXY -ErrorAction SilentlyContinue
   ```

2. Check whether direct TCP works. If it times out, do not conclude the ECS is down:

   ```powershell
   Test-NetConnection <ecs_public_ip> -Port <ssh_port>
   ```

3. Prove the HTTP proxy can CONNECT to the SSH port. Use the bundled script's `--probe-banner` mode:

   ```powershell
   python <skill_dir>\scripts\http_proxy_ssh_exec.py `
     --host <ecs_public_ip> --port <ssh_port> `
     --probe-banner
   ```

   Expected SSH banner example:

   ```text
   SSH-2.0-OpenSSH_...
   ```

4. Execute a read-only remote preflight command:

   ```powershell
   $env:KEY_PASSPHRASE='<temporary-passphrase-if-needed>'
   python <skill_dir>\scripts\http_proxy_ssh_exec.py `
     --host <ecs_public_ip> --port <ssh_port> `
     --user root --key C:\path\to\private_key `
     --known-hosts C:\path\to\known_hosts `
     --command "echo ssh-ok; hostname; whoami; uname -a; cat /etc/os-release | grep -E 'PRETTY|VERSION_ID'"
   Remove-Item Env:KEY_PASSPHRASE -ErrorAction SilentlyContinue
   ```

5. For long or quote-heavy remote commands, write a temporary local command file in the workspace and run:

   ```powershell
   python <skill_dir>\scripts\http_proxy_ssh_exec.py `
     --host <ecs_public_ip> --port <ssh_port> `
     --user root --key C:\path\to\private_key `
     --known-hosts C:\path\to\known_hosts `
     --command-file .\remote_check.sh
   ```

6. If the service is running on the ECS but public access fails:

   - On ECS: check `ss -tlnp`, `ufw status`, and `iptables -S INPUT`.
   - From laptop: check `Test-NetConnection <ecs_public_ip> -Port <service_port>`.
   - If ECS local checks pass and public TCP fails, ask the user to update Huawei Cloud security group rules for the current public egress IP `/32`.

## Useful Remote Checks

For Ubuntu ECS:

```bash
echo ssh-ok
hostname
whoami
uname -a
cat /etc/os-release | grep -E 'PRETTY|VERSION_ID'
nproc
free -h | head -2
df -h /
ss -tlnp
```

For Docker services:

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
systemctl is-active <service>.service
systemctl is-enabled <service>.service
journalctl -u <service>.service -n 80 --no-pager
```

## Failure Interpretation

- `Connection timed out` direct to SSH port: likely corporate network or security group; try proxy CONNECT.
- `proxy CONNECT failed: HTTP/1.1 504`: proxy cannot reach that host/port or security group blocks the proxy egress.
- `Server not found in known_hosts`: add the ECS host key to a trusted known-hosts file or use `--known-hosts` to point at the right file.
- SSH banner probe succeeds but OpenSSH `ProxyCommand` hangs on Windows: use the bundled Paramiko script.
- Paramiko says `private key file is encrypted`: ask for passphrase or have user load key into an agent; do not store passphrase.
- Paramiko RSA unpack errors: try multiple key types. The bundled script already tries RSA, ECDSA, and Ed25519.
- Public HTTP request returns corporate proxy HTML/302: bypass proxy or use a network path that is allowed; the ECS service may still be healthy.
