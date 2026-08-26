#!/usr/bin/env python3
"""
Docker Compose Parser + Validator for CCI Migration.

Parses docker-compose.yaml with yaml.safe_load (correct handling of
anchors, merge keys, multi-line strings) and validates the result.
Outputs a JSON dict that the AI uses for translation to CCI payloads.

This script does NOT translate — the AI does the translation.
This script only ensures correct parsing and warns about issues.

Usage:
  python3 compose_parser.py docker-compose.yaml
  python3 compose_parser.py docker-compose.yaml --check-cci
  python3 compose_parser.py docker-compose.yaml --output parsed.json
"""

import argparse
import json
import os
import sys

try:
    import yaml
except ImportError:
    print("PyYAML required: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


CCI_IMPOSSIBLE_FEATURES = {
    "privileged": "CCI does not allow privileged pods (serverless)",
    "network_mode": "CCI does not support network_mode: host (serverless, no host namespace)",
    "devices": "CCI does not allow device access",
    "cap_add": "CCI does not support Linux capabilities",
    "cap_drop": "CCI does not support Linux capabilities",
    "pid": "CCI does not support pid: host",
    "ipc": "CCI does not support ipc: host",
    "cgroup_parent": "CCI does not support cgroup_parent",
    "storage_opt": "CCI does not support storage_opt",
    "ulimits": "CCI does not support ulimits",
    "sysctls": "CCI does not support sysctls",
    "isolation": "CCI does not support isolation",
}

DB_IMAGES = ["postgres", "mysql", "mariadb", "mongodb", "redis", "mariadb"]
CACHE_IMAGES = ["redis", "memcached"]


def parse_compose(path):
    with open(path) as f:
        data = yaml.safe_load(f)
    return data


def validate_compose(data):
    warnings = []
    errors = []
    info = []

    services = data.get("services", {})
    if not services:
        errors.append("No services found in docker-compose.yaml")
        return errors, warnings, info

    info.append(f"Found {len(services)} service(s): {', '.join(services.keys())}")

    for name, svc in services.items():
        if not isinstance(svc, dict):
            errors.append(f"Service '{name}' is not a valid mapping")
            continue

        image = svc.get("image")
        build = svc.get("build")

        if not image and not build:
            errors.append(f"Service '{name}' has no 'image' or 'build' — cannot deploy")
        elif build and not image:
            info.append(f"Service '{name}' uses 'build:' — needs docker build + push to SWR")

        ports = svc.get("ports", [])
        if ports:
            info.append(f"Service '{name}' exposes ports: {ports}")

        volumes = svc.get("volumes", [])
        if volumes:
            for v in volumes:
                if isinstance(v, str) and ":" in v:
                    src = v.split(":")[0]
                    if not src.startswith(".") and not os.path.isabs(src):
                        info.append(f"Service '{name}' uses named volume: {src}")

        env = svc.get("environment", {})
        env_file = svc.get("env_file")
        if env_file:
            info.append(f"Service '{name}' uses env_file: {env_file}")

        secrets = svc.get("secrets", [])
        if secrets:
            info.append(f"Service '{name}' has secrets: {secrets}")

        depends = svc.get("depends_on", [])
        if depends:
            info.append(f"Service '{name}' depends_on: {depends}")

        healthcheck = svc.get("healthcheck", {})
        if healthcheck:
            info.append(f"Service '{name}' has healthcheck")

        if not svc.get("cpus") and not svc.get("deploy"):
            info.append(f"Service '{name}' has no CPU limit — will use default 250m")

    named_volumes = data.get("volumes", {})
    if named_volumes:
        info.append(f"Named volumes: {list(named_volumes.keys())}")

    networks = data.get("networks", {})
    if networks and len(networks) > 1:
        warnings.append(
            f"Multiple networks defined ({list(networks.keys())}) — "
            "CCI supports only 1 network per namespace. All services will share one CCI network."
        )

    return errors, warnings, info


def check_cci_compatibility(data):
    warnings = []

    services = data.get("services", {})
    for name, svc in services.items():
        for feature, reason in CCI_IMPOSSIBLE_FEATURES.items():
            if feature in svc:
                val = svc[feature]
                if feature == "network_mode" and val != "host":
                    continue
                if feature == "pid" and val != "host":
                    continue
                if feature == "ipc" and val != "host":
                    continue
                warnings.append(f"Service '{name}': {reason} (found {feature}: {val})")

        if svc.get("privileged"):
            warnings.append(
                f"Service '{name}': privileged=true is impossible in CCI. "
                "Consider CCE (full Kubernetes) or ECS (VM) instead."
            )

    return warnings


def detect_managed_service_suggestions(data):
    suggestions = []

    services = data.get("services", {})
    for name, svc in services.items():
        image = svc.get("image", "")
        image_base = image.split(":")[0].split("/")[-1].lower() if image else ""

        if image_base in ["postgres", "postgresql"]:
            suggestions.append(
                f"Service '{name}' (postgres): consider migrating to RDS PostgreSQL "
                "with DRS for managed backup, HA, and scaling. The AI can generate "
                "DRS migration commands."
            )
        elif image_base in ["mysql", "mariadb"]:
            suggestions.append(
                f"Service '{name}' ({image_base}): consider migrating to RDS {image_base.capitalize()} "
                "with DRS for managed backup, HA, and scaling."
            )
        elif image_base == "mongodb":
            suggestions.append(
                f"Service '{name}' (mongodb): consider migrating to GaussDB(for Mongo) "
                "or DDS (Document Database Service) for managed MongoDB."
            )
        elif image_base == "redis":
            suggestions.append(
                f"Service '{name}' (redis): consider migrating to DCS "
                "(Distributed Cache Service) for managed Redis with HA."
            )
        elif image_base == "memcached":
            suggestions.append(
                f"Service '{name}' (memcached): consider DCS Memcached edition "
                "for managed caching."
            )

    return suggestions


def main():
    parser = argparse.ArgumentParser(
        description="Docker Compose Parser + Validator for CCI Migration"
    )
    parser.add_argument("file", help="Path to docker-compose.yaml")
    parser.add_argument("--check-cci", action="store_true",
                        help="Check for CCI-incompatible features")
    parser.add_argument("--output", default=None,
                        help="Output file (default: stdout)")

    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"Error: {args.file} not found", file=sys.stderr)
        sys.exit(1)

    data = parse_compose(args.file)

    errors, warnings, info = validate_compose(data)

    if args.check_cci:
        cci_warnings = check_cci_compatibility(data)
        warnings.extend(cci_warnings)

    suggestions = detect_managed_service_suggestions(data)

    for e in errors:
        print(f"ERROR: {e}", file=sys.stderr)
    for w in warnings:
        print(f"WARNING: {w}", file=sys.stderr)
    for i in info:
        print(f"INFO: {i}", file=sys.stderr)
    for s in suggestions:
        print(f"SUGGEST: {s}", file=sys.stderr)

    if errors:
        print(f"\n{len(errors)} error(s), cannot proceed.", file=sys.stderr)
        sys.exit(1)

    output = json.dumps(data, indent=2)
    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Written to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
