#!/usr/bin/env python3
"""Execute SSH commands through an HTTP CONNECT proxy.

Reads HTTPS_PROXY or HTTP_PROXY from the environment. For encrypted private keys,
set KEY_PASSPHRASE only for the current process.
"""
import argparse
import base64
import os
import socket
import ssl
import sys
from urllib.parse import unquote, urlparse


def connect_proxy(host: str, port: int) -> socket.socket:
    proxy_url = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
    if not proxy_url:
        raise RuntimeError("HTTPS_PROXY/HTTP_PROXY is not set")

    parsed = urlparse(proxy_url)
    if not parsed.hostname:
        raise RuntimeError("proxy host is missing")

    scheme = (parsed.scheme or "http").lower()
    if scheme not in {"http", "https"}:
        raise RuntimeError(f"unsupported proxy scheme: {parsed.scheme}")

    sock = socket.create_connection((parsed.hostname, parsed.port or 8080), timeout=30)
    if scheme == "https":
        context = ssl.create_default_context()
        sock = context.wrap_socket(sock, server_hostname=parsed.hostname)
    headers = [
        f"CONNECT {host}:{port} HTTP/1.1",
        f"Host: {host}:{port}",
        "Proxy-Connection: Keep-Alive",
    ]
    if parsed.username:
        username = unquote(parsed.username)
        password = unquote(parsed.password or "")
        token = base64.b64encode(f"{username}:{password}".encode()).decode()
        headers.append(f"Proxy-Authorization: Basic {token}")

    sock.sendall(("\r\n".join(headers) + "\r\n\r\n").encode())
    response = b""
    while b"\r\n\r\n" not in response:
        chunk = sock.recv(4096)
        if not chunk:
            break
        response += chunk
        if len(response) > 65536:
            break

    status = response.split(b"\r\n", 1)[0].decode(errors="replace")
    if " 200 " not in status:
        raise RuntimeError(f"proxy CONNECT failed: {status}")
    sock.settimeout(None)
    return sock


def probe_banner(host: str, port: int) -> int:
    sock = connect_proxy(host, port)
    sock.settimeout(10)
    try:
        data = sock.recv(256)
    finally:
        sock.close()
    print(data.decode(errors="replace").strip())
    return 0


def load_key(paramiko, key_path: str):
    passphrase = os.environ.get("KEY_PASSPHRASE")
    last_error = None
    for key_cls in (paramiko.RSAKey, paramiko.ECDSAKey, paramiko.Ed25519Key):
        try:
            return key_cls.from_private_key_file(key_path, password=passphrase)
        except Exception as exc:  # Keep trying other key formats.
            last_error = exc
    raise last_error


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--user")
    parser.add_argument("--key")
    parser.add_argument("--known-hosts")
    parser.add_argument("--command")
    parser.add_argument("--command-file")
    parser.add_argument("--insecure-accept-host-key", action="store_true")
    parser.add_argument("--probe-banner", action="store_true")
    args = parser.parse_args()

    if args.probe_banner:
        return probe_banner(args.host, args.port)

    if not args.user or not args.key:
        parser.error("--user and --key are required unless --probe-banner is used")
    if not args.command and not args.command_file:
        parser.error("--command or --command-file is required")

    command = args.command
    if args.command_file:
        with open(args.command_file, "r", encoding="utf-8") as fh:
            command = fh.read()

    try:
        import paramiko
    except ImportError as exc:
        raise SystemExit(
            "paramiko is required. Install with: python -m pip install --user paramiko"
        ) from exc

    sock = connect_proxy(args.host, args.port)
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    if args.known_hosts:
        client.load_host_keys(args.known_hosts)
    if args.insecure_accept_host_key:
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    else:
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
    key = load_key(paramiko, args.key)
    client.connect(
        hostname=args.host,
        port=args.port,
        username=args.user,
        pkey=key,
        sock=sock,
        timeout=30,
        banner_timeout=30,
        auth_timeout=30,
    )

    _, stdout, stderr = client.exec_command(command, get_pty=False)
    for line in iter(stdout.readline, ""):
        print(line, end="")
    err = stderr.read().decode(errors="replace")
    if err:
        print(err, end="", file=sys.stderr)
    rc = stdout.channel.recv_exit_status()
    client.close()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
