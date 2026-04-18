#!/usr/bin/env python3
"""Preflight checks for Kafka broker TCP reachability and GaussDB login/query.

Examples:
  python3 smoke_check.py --kafka-bootstrap-servers broker1:9093,broker2:9093
  python3 smoke_check.py --gaussdb-host db-host --gaussdb-port 8000 --gaussdb-user app --gaussdb-password secret --gaussdb-database postgres
"""

from __future__ import annotations

import argparse
import socket
import sys
from dataclasses import dataclass


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


def parse_bootstrap_servers(value: str) -> list[tuple[str, int]]:
    items: list[tuple[str, int]] = []
    for raw in value.split(","):
        raw = raw.strip()
        if not raw:
            continue
        host, port = raw.rsplit(":", 1)
        items.append((host.strip(), int(port)))
    return items


def check_tcp(host: str, port: int, timeout: float) -> CheckResult:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return CheckResult(f"tcp://{host}:{port}", True, "reachable")
    except Exception as exc:
        return CheckResult(f"tcp://{host}:{port}", False, str(exc))


def check_gaussdb(args: argparse.Namespace) -> CheckResult:
    try:
        try:
            import psycopg2 as psycopg  # type: ignore
        except ImportError:
            import psycopg  # type: ignore

        conn = psycopg.connect(
            host=args.gaussdb_host,
            port=args.gaussdb_port,
            user=args.gaussdb_user,
            password=args.gaussdb_password,
            dbname=args.gaussdb_database,
            connect_timeout=int(args.timeout),
        )
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT version()")
                version = cur.fetchone()[0]
            return CheckResult(
                f"gaussdb://{args.gaussdb_host}:{args.gaussdb_port}/{args.gaussdb_database}",
                True,
                version.split(",")[0],
            )
        finally:
            conn.close()
    except Exception as exc:
        return CheckResult(
            f"gaussdb://{args.gaussdb_host}:{args.gaussdb_port}/{args.gaussdb_database}",
            False,
            str(exc),
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke check Kafka and GaussDB connectivity.")
    parser.add_argument("--kafka-bootstrap-servers", default="")
    parser.add_argument("--gaussdb-host", default="")
    parser.add_argument("--gaussdb-port", type=int, default=8000)
    parser.add_argument("--gaussdb-user", default="")
    parser.add_argument("--gaussdb-password", default="")
    parser.add_argument("--gaussdb-database", default="postgres")
    parser.add_argument("--timeout", type=float, default=3.0)
    args = parser.parse_args()

    results: list[CheckResult] = []

    if args.kafka_bootstrap_servers:
        for host, port in parse_bootstrap_servers(args.kafka_bootstrap_servers):
            results.append(check_tcp(host, port, args.timeout))

    if args.gaussdb_host:
        required = [args.gaussdb_user, args.gaussdb_password, args.gaussdb_database]
        if not all(required):
            print("GaussDB checks require host, user, password, and database.", file=sys.stderr)
            return 2
        results.append(check_gaussdb(args))

    if not results:
        print("Nothing to check. Supply Kafka bootstrap servers and/or GaussDB connection arguments.", file=sys.stderr)
        return 2

    failed = False
    for item in results:
        status = "OK" if item.ok else "FAIL"
        print(f"[{status}] {item.name} - {item.detail}")
        failed = failed or not item.ok

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
