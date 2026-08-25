#!/usr/bin/env python3
"""
Docker Compose to CCI Translation Script.

Parses docker-compose.yaml and generates CCI v2 API payloads.
Can also perform full migration using CCIClient.

Usage:
  python3 compose-to-cci.py parse docker-compose.yaml
  python3 compose-to-cci.py translate docker-compose.yaml --namespace my-app
  python3 compose-to-cci.py migrate docker-compose.yaml \
    --ak <AK> --sk <SK> --project-id <PID> \
    --region sa-brazil-1 --namespace my-app \
    --domain-id <DID> --subnet-id <SID> --sg-id <SGID>
"""

import argparse
import base64
import json
import os
import sys
import time

try:
    import yaml
except ImportError:
    print("PyYAML required: pip install pyyaml")
    sys.exit(1)

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from cci_api_helper import CCIClient


DEFAULT_CPU_REQ = "250m"
DEFAULT_MEM_REQ = "512Mi"
DEFAULT_CPU_LIM = "500m"
DEFAULT_MEM_LIM = "1024Mi"


def parse_compose(path):
    with open(path) as f:
        data = yaml.safe_load(f)
    return data


def summarize_compose(data):
    services = data.get("services", {})
    volumes = data.get("volumes", {})
    networks = data.get("networks", {})

    print(f"Services: {len(services)}")
    for name, svc in services.items():
        image = svc.get("image", "?")
        ports = svc.get("ports", [])
        env_count = len(svc.get("environment", {})) if isinstance(svc.get("environment"), dict) else len(svc.get("environment", []))
        vol_count = len(svc.get("volumes", []))
        deps = svc.get("depends_on", [])
        print(f"  {name}: image={image} ports={ports} env={env_count} volumes={vol_count} depends_on={deps}")

    if volumes:
        print(f"\nNamed volumes: {list(volumes.keys())}")
    if networks:
        print(f"Networks: {list(networks.keys())}")


def translate_service(name, svc, namespace):
    image = svc.get("image", f"{name}:latest")
    ports = svc.get("ports", [])
    environment = svc.get("environment", {})
    volumes = svc.get("volumes", [])
    restart = svc.get("restart", "always")
    healthcheck = svc.get("healthcheck", {})
    command = svc.get("command")
    entrypoint = svc.get("entrypoint")
    cpu_limit = svc.get("cpus", "0.25")
    mem_limit = svc.get("mem_limit", "512m")

    cpu_req = f"{int(float(cpu_limit) * 1000)}m" if cpu_limit else DEFAULT_CPU_REQ
    mem_req = _normalize_memory(mem_limit) if mem_limit else DEFAULT_MEM_REQ

    container = {
        "name": name,
        "image": image,
        "resources": {
            "requests": {"cpu": cpu_req, "memory": mem_req},
            "limits": {"cpu": DEFAULT_CPU_LIM, "memory": DEFAULT_MEM_LIM},
        },
    }

    container_ports = []
    for p in ports:
        if isinstance(p, str) and ":" in p:
            external, internal = p.split(":")
            container_ports.append({"containerPort": int(internal)})
        elif isinstance(p, int):
            container_ports.append({"containerPort": p})
        elif isinstance(p, dict):
            container_ports.append({"containerPort": p.get("target", p.get("published", 80))})
    if container_ports:
        container["ports"] = container_ports

    if command:
        container["command"] = command if isinstance(command, list) else command.split()
    if entrypoint:
        container["args"] = entrypoint if isinstance(entrypoint, list) else [entrypoint]

    if isinstance(environment, dict):
        env_list = [{"name": k, "value": str(v)} for k, v in environment.items()]
    elif isinstance(environment, list):
        env_list = []
        for item in environment:
            if "=" in item:
                k, v = item.split("=", 1)
                env_list.append({"name": k, "value": v})
    else:
        env_list = []
    if env_list:
        container["env"] = env_list

    if healthcheck:
        test = healthcheck.get("test", [])
        if test and test[0] == "CMD":
            container["livenessProbe"] = {
                "exec": {"command": test[1:]},
                "periodSeconds": healthcheck.get("interval", "30s").rstrip("s"),
                "timeoutSeconds": healthcheck.get("timeout", "10s").rstrip("s"),
            }

    replicas = 0 if restart == "no" else 1

    deployment = {
        "apiVersion": "cci/v2",
        "kind": "Deployment",
        "metadata": {"name": name},
        "spec": {
            "replicas": replicas,
            "selector": {"matchLabels": {"app": name}},
            "template": {
                "metadata": {"labels": {"app": name}},
                "spec": {"containers": [container]},
            },
        },
    }

    service = None
    if container_ports:
        service = {
            "apiVersion": "cci/v2",
            "kind": "Service",
            "metadata": {
                "name": f"{name}-svc",
                "annotations": {"kubernetes.io/elb.autocreate": "true"},
            },
            "spec": {
                "type": "LoadBalancer",
                "selector": {"app": name},
                "ports": [{"port": p["containerPort"], "targetPort": p["containerPort"], "protocol": "TCP"} for p in container_ports],
            },
        }

    configmap = None
    if isinstance(environment, dict) and environment:
        configmap = {
            "apiVersion": "cci/v2",
            "kind": "ConfigMap",
            "metadata": {"name": f"{name}-config"},
            "data": {k: str(v) for k, v in environment.items()},
        }

    return {"deployment": deployment, "service": service, "configmap": configmap}


def _normalize_memory(mem):
    if isinstance(mem, str):
        if mem.endswith("m"):
            return f"{mem[:-1]}Mi"
        if mem.endswith("g"):
            return f"{mem[:-1]}Gi"
        if mem.endswith("M"):
            return f"{mem[:-1]}Mi"
        if mem.endswith("G"):
            return f"{mem[:-1]}Gi"
    return f"{mem}Mi"


def translate_compose(data, namespace, output_dir=None):
    services = data.get("services", {})
    results = []

    for name, svc in services.items():
        translated = translate_service(name, svc, namespace)
        results.append({"service_name": name, **translated})

        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            for res_type, payload in translated.items():
                if payload:
                    filename = f"{name}-{res_type}.json"
                    with open(os.path.join(output_dir, filename), "w") as f:
                        json.dump(payload, f, indent=2)

    return results


def migrate_compose(data, client, namespace, domain_id, subnet_id, sg_id):
    print(f"Creating namespace {namespace}...")
    s, r = client.create_namespace(namespace, domain_id)
    print(f"  Namespace: {s} - {r.get('metadata', {}).get('name', r.get('message', ''))}")

    print(f"Creating network...")
    s, r = client.create_network(namespace, f"{namespace}-net", domain_id, subnet_id, [sg_id])
    print(f"  Network: {s} - {r.get('metadata', {}).get('name', r.get('message', ''))}")

    services = data.get("services", {})
    for name, svc in services.items():
        print(f"\nTranslating service: {name}")
        translated = translate_service(name, svc, namespace)

        if translated["configmap"]:
            s, r = client.create_configmap(
                namespace,
                translated["configmap"]["metadata"]["name"],
                translated["configmap"]["data"],
            )
            print(f"  ConfigMap: {s}")

        image = svc.get("image", f"{name}:latest")
        ports = svc.get("ports", [])
        container_port = 80
        if ports:
            p = ports[0]
            if isinstance(p, str) and ":" in p:
                container_port = int(p.split(":")[1])
            elif isinstance(p, int):
                container_port = p

        s, r = client.create_deployment(namespace, name, image, container_port=container_port)
        print(f"  Deployment: {s}")

        if translated["service"]:
            print(f"  Service: (requires ELB ID - skipping auto-create)")

        print(f"  Waiting for pod...")
        ok, pod = client.wait_for_pod_ready(namespace, timeout=120)
        if ok:
            print(f"  RUNNING! podIP={pod.get('status', {}).get('podIP')}")
        else:
            print(f"  TIMEOUT or still starting...")


def main():
    parser = argparse.ArgumentParser(description="Docker Compose to CCI Translation")
    sub = parser.add_subparsers(dest="action", required=True)

    p_parse = sub.add_parser("parse", help="Parse and summarize docker-compose.yaml")
    p_parse.add_argument("file")

    p_translate = sub.add_parser("translate", help="Generate CCI v2 API payloads")
    p_translate.add_argument("file")
    p_translate.add_argument("--namespace", default="my-app")
    p_translate.add_argument("--output", default=None)

    p_migrate = sub.add_parser("migrate", help="Full migration to CCI")
    p_migrate.add_argument("file")
    p_migrate.add_argument("--namespace", default="my-app")
    p_migrate.add_argument("--ak", required=True)
    p_migrate.add_argument("--sk", required=True)
    p_migrate.add_argument("--project-id", required=True)
    p_migrate.add_argument("--region", default="sa-brazil-1")
    p_migrate.add_argument("--domain-id", required=True)
    p_migrate.add_argument("--subnet-id", required=True)
    p_migrate.add_argument("--sg-id", required=True)

    args = parser.parse_args()
    data = parse_compose(args.file)

    if args.action == "parse":
        summarize_compose(data)

    elif args.action == "translate":
        results = translate_compose(data, args.namespace, args.output)
        for r in results:
            print(f"\n--- {r['service_name']} ---")
            if r["deployment"]:
                print(json.dumps(r["deployment"], indent=2))
            if r["service"]:
                print(json.dumps(r["service"], indent=2))
            if r["configmap"]:
                print(json.dumps(r["configmap"], indent=2))

    elif args.action == "migrate":
        client = CCIClient(args.ak, args.sk, args.project_id, args.region)
        migrate_compose(data, client, args.namespace, args.domain_id, args.subnet_id, args.sg_id)


if __name__ == "__main__":
    main()
