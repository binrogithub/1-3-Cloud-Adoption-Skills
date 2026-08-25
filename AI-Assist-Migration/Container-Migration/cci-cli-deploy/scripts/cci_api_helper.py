#!/usr/bin/env python3
"""
CCI API Helper - Create and manage CCI resources from the terminal.

This script encapsulates the complete flow for deploying workloads to
Huawei Cloud CCI (Cloud Container Instance) using the v2 API.

Key discovery: CCI v1beta1 API strips `securityGroups` from Network spec
(not in CRD schema). The v2 API (`cci/v2` + `yangtse/v2`) includes it.

Complete flow:
  1. Create namespace via cci/v2 API
  2. Create network via yangtse/v2 API (with securityGroups)
  3. Create EIP + NAT gateway + SNAT rule (for internet access)
  4. Create image pull secret (if using private registry)
  5. Create deployment with resource limits (required by CCI)
  6. Create service (LoadBalancer with ELB annotation)

Usage:
  python3 cci_api_helper.py --action setup --region sa-brazil-1
  python3 cci_api_helper.py --action deploy --region sa-brazil-1 --image nginx:1.25-alpine
  python3 cci_api_helper.py --action status --region sa-brazil-1
  python3 cci_api_helper.py --action cleanup --region sa-brazil-1
"""

import argparse
import base64
import hashlib
import hmac
import json
import ssl
import time
import urllib.request
from datetime import datetime, timezone


class CCIClient:
    """Minimal CCI API client with Huawei Cloud AK/SK signing."""

    def __init__(self, ak, sk, project_id, region):
        self.ak = ak
        self.sk = sk
        self.project_id = project_id
        self.host = f"cci.{region}.myhuaweicloud.com"
        self.region = region
        self.ctx = ssl.create_default_context()

    def _sign_and_request(self, method, path, body=None, timeout=30):
        body_bytes = json.dumps(body).encode("utf-8") if body else b""
        body_hash = (
            hashlib.sha256(body_bytes).hexdigest()
            if body
            else "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        )
        now = datetime.now(timezone.utc)
        sdk_date = now.strftime("%Y%m%dT%H%M%SZ")
        signed_headers = "content-type;x-project-id;x-sdk-date"
        canonical_uri = path + "/"
        canonical_headers = (
            f"content-type:application/json\n"
            f"x-project-id:{self.project_id}\n"
            f"x-sdk-date:{sdk_date}\n"
        )
        canonical_request = (
            f"{method}\n{canonical_uri}\n\n"
            f"{canonical_headers}\n{signed_headers}\n{body_hash}"
        )
        hash_cr = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
        string_to_sign = f"SDK-HMAC-SHA256\n{sdk_date}\n{hash_cr}"
        signature = hmac.new(
            self.sk.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        auth = (
            f"SDK-HMAC-SHA256 Access={self.ak}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )
        url = f"https://{self.host}{path}"
        req = urllib.request.Request(
            url, data=body_bytes if body else None, method=method
        )
        req.add_header("Content-Type", "application/json")
        req.add_header("X-Project-Id", self.project_id)
        req.add_header("X-Sdk-Date", sdk_date)
        req.add_header("Authorization", auth)
        try:
            with urllib.request.urlopen(req, context=self.ctx, timeout=timeout) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read().decode("utf-8"))
            except Exception:
                return e.code, {"error": str(e)}
        except Exception as e:
            return -1, {"error": str(e)}

    # --- Namespace operations (cci/v2) ---

    def create_namespace(self, name, domain_id):
        body = {
            "apiVersion": "cci/v2",
            "kind": "Namespace",
            "metadata": {
                "name": name,
                "annotations": {
                    "yangtse.io/domain-id": domain_id,
                    "yangtse.io/project-id": self.project_id,
                },
            },
        }
        return self._sign_and_request("POST", "/apis/cci/v2/namespaces", body)

    def get_namespace(self, name):
        return self._sign_and_request("GET", f"/apis/cci/v2/namespaces/{name}")

    def delete_namespace(self, name):
        return self._sign_and_request("DELETE", f"/apis/cci/v2/namespaces/{name}")

    def list_namespaces(self):
        return self._sign_and_request("GET", "/apis/cci/v2/namespaces")

    # --- Network operations (yangtse/v2) ---

    def create_network(
        self, namespace, name, domain_id, subnet_id, security_group_ids
    ):
        body = {
            "apiVersion": "yangtse/v2",
            "kind": "Network",
            "metadata": {
                "name": name,
                "annotations": {
                    "yangtse.io/domain-id": domain_id,
                    "yangtse.io/project-id": self.project_id,
                },
            },
            "spec": {
                "networkType": "underlay_neutron",
                "securityGroups": security_group_ids,
                "subnets": [{"subnetID": subnet_id}],
            },
        }
        return self._sign_and_request(
            "POST", f"/apis/yangtse/v2/namespaces/{namespace}/networks", body
        )

    def get_network(self, namespace, name):
        return self._sign_and_request(
            "GET", f"/apis/yangtse/v2/namespaces/{namespace}/networks/{name}"
        )

    # --- Workload operations (cci/v2) ---

    def create_deployment(
        self,
        namespace,
        name,
        image,
        replicas=1,
        container_port=80,
        cpu_req="250m",
        mem_req="512Mi",
        cpu_lim="500m",
        mem_lim="1024Mi",
        image_pull_secret=None,
    ):
        container = {
            "name": name,
            "image": image,
            "ports": [{"containerPort": container_port}],
            "resources": {
                "requests": {"cpu": cpu_req, "memory": mem_req},
                "limits": {"cpu": cpu_lim, "memory": mem_lim},
            },
        }
        pod_spec = {"containers": [container]}
        if image_pull_secret:
            pod_spec["imagePullSecrets"] = [{"name": image_pull_secret}]

        body = {
            "apiVersion": "cci/v2",
            "kind": "Deployment",
            "metadata": {"name": name},
            "spec": {
                "replicas": replicas,
                "selector": {"matchLabels": {"app": name}},
                "template": {
                    "metadata": {"labels": {"app": name}},
                    "spec": pod_spec,
                },
            },
        }
        return self._sign_and_request(
            "POST", f"/apis/cci/v2/namespaces/{namespace}/deployments", body
        )

    def delete_deployment(self, namespace, name):
        return self._sign_and_request(
            "DELETE", f"/apis/cci/v2/namespaces/{namespace}/deployments/{name}"
        )

    def create_configmap(self, namespace, name, data):
        body = {
            "apiVersion": "cci/v2",
            "kind": "ConfigMap",
            "metadata": {"name": name},
            "data": data,
        }
        return self._sign_and_request(
            "POST", f"/apis/cci/v2/namespaces/{namespace}/configmaps", body
        )

    def create_secret(self, namespace, name, secret_type, data):
        body = {
            "apiVersion": "cci/v2",
            "kind": "Secret",
            "metadata": {"name": name},
            "type": secret_type,
            "data": data,
        }
        return self._sign_and_request(
            "POST", f"/apis/cci/v2/namespaces/{namespace}/secrets", body
        )

    def create_image_pull_secret(self, namespace, name, registry, username, password):
        config = {
            "auths": {
                registry: {
                    "auth": base64.b64encode(
                        f"{username}:{password}".encode()
                    ).decode()
                }
            }
        }
        config_b64 = base64.b64encode(json.dumps(config).encode()).decode()
        return self.create_secret(
            namespace,
            name,
            "kubernetes.io/dockerconfigjson",
            {".dockerconfigjson": config_b64},
        )

    def create_service(self, namespace, name, selector, port, target_port, elb_id=None):
        spec = {
            "selector": selector,
            "ports": [{"port": port, "targetPort": target_port, "protocol": "TCP"}],
        }
        if elb_id:
            spec["type"] = "LoadBalancer"
            metadata = {
                "name": name,
                "annotations": {"kubernetes.io/elb.id": elb_id},
            }
        else:
            spec["type"] = "ExternalName"
            spec["externalName"] = "example.com"
            metadata = {"name": name}
        body = {
            "apiVersion": "cci/v2",
            "kind": "Service",
            "metadata": metadata,
            "spec": spec,
        }
        return self._sign_and_request(
            "POST", f"/apis/cci/v2/namespaces/{namespace}/services", body
        )

    # --- Query operations ---

    def list_pods(self, namespace):
        return self._sign_and_request(
            "GET", f"/apis/cci/v2/namespaces/{namespace}/pods"
        )

    def get_deployment(self, namespace, name):
        return self._sign_and_request(
            "GET", f"/apis/cci/v2/namespaces/{namespace}/deployments/{name}"
        )

    def wait_for_pod_ready(self, namespace, timeout=120, interval=5):
        start = time.time()
        while time.time() - start < timeout:
            s, r = self.list_pods(namespace)
            if s == 200:
                for p in r.get("items", []):
                    phase = p.get("status", {}).get("phase", "?")
                    cs = p.get("status", {}).get("containerStatuses", [])
                    ready = cs[0].get("ready", False) if cs else False
                    if phase == "Running" and ready:
                        return True, p
            time.sleep(interval)
        return False, None


def main():
    parser = argparse.ArgumentParser(description="CCI API Helper")
    parser.add_argument("--ak", required=True, help="Access Key ID")
    parser.add_argument("--sk", required=True, help="Secret Access Key")
    parser.add_argument("--project-id", required=True, help="Project ID")
    parser.add_argument("--region", default="sa-brazil-1", help="Region")
    parser.add_argument("--action", required=True,
                        choices=["setup", "deploy", "status", "cleanup"])
    parser.add_argument("--namespace", default="cci-v2-ns")
    parser.add_argument("--network", default="cci-v2-network")
    parser.add_argument("--domain-id", default="")
    parser.add_argument("--vpc-id", default="")
    parser.add_argument("--subnet-id", default="")
    parser.add_argument("--sg-id", default="")
    parser.add_argument("--image", default="nginx:1.25-alpine")
    parser.add_argument("--name", default="nginx-test")
    args = parser.parse_args()

    client = CCIClient(args.ak, args.sk, args.project_id, args.region)

    if args.action == "setup":
        print(f"Creating namespace {args.namespace}...")
        s, r = client.create_namespace(args.namespace, args.domain_id)
        print(f"  Namespace: {s} - {r.get('metadata', {}).get('name', r.get('message', ''))}")

        print(f"Creating network {args.network}...")
        s, r = client.create_network(
            args.namespace, args.network, args.domain_id,
            args.subnet_id, [args.sg_id]
        )
        print(f"  Network: {s} - {r.get('metadata', {}).get('name', r.get('message', ''))}")

    elif args.action == "deploy":
        print(f"Creating deployment {args.name} with image {args.image}...")
        s, r = client.create_deployment(args.namespace, args.name, args.image)
        print(f"  Deployment: {s}")

        print("Waiting for pod to be ready...")
        ok, pod = client.wait_for_pod_ready(args.namespace)
        if ok:
            print(f"  RUNNING! podIP={pod.get('status', {}).get('podIP')}")
        else:
            print("  TIMEOUT - pod not ready")

    elif args.action == "status":
        s, r = client.list_pods(args.namespace)
        if s == 200:
            for p in r.get("items", []):
                name = p["metadata"]["name"]
                phase = p.get("status", {}).get("phase", "?")
                ip = p.get("status", {}).get("podIP", "?")
                print(f"  {name}: {phase} ip={ip}")

    elif args.action == "cleanup":
        print(f"Deleting deployment {args.name}...")
        client.delete_deployment(args.namespace, args.name)
        print(f"Deleting namespace {args.namespace}...")
        client.delete_namespace(args.namespace)
        print("Done.")


if __name__ == "__main__":
    main()
