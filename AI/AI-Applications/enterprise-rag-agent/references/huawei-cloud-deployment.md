# Huawei Cloud Deployment Reference

Use this reference when provisioning or debugging a Huawei Cloud demo with OBS, CSS/OpenSearch, ECS, RAGFlow, LlamaIndex, Huawei Cloud MaaS, and a lightweight upload/search portal.

## Credential Rules

- Never write AK/SK into generated files, state files, shell history snippets, or cloud-init.
- Read credentials from `HWC_ACCESS_KEY_ID` and `HWC_SECRET_ACCESS_KEY`.
- Treat pasted AK/SK as compromised after use and recommend rotation.
- Store only non-secret state: region, project ID, resource IDs, endpoints, public IPs, and SSH key paths.

## SDK Setup

If Huawei Cloud CLI or Terraform is unavailable, use Python SDK packages:

```bash
python3 -m pip install --user huaweicloudsdkcore huaweicloudsdkiam huaweicloudsdkecs huaweicloudsdkvpc huaweicloudsdkims huaweicloudsdkcss esdk-obs-python
```

If `pip` is missing and sudo is unavailable, bootstrap user-level pip with `get-pip.py`, then install SDKs under `~/.local`.

## Resource Defaults

- Region: `la-north-2`
- Project ID: require discovery or explicit `HWC_PROJECT_ID`
- OBS: private bucket named with a unique deployment prefix
- CSS: one node, `ess.spec-4u8g`, 40 GB disk, version `7.10.2` when available
- CSS disk: use `HIGH` if `COMMON` returns sold-out errors
- ECS: Ubuntu 22.04, general-purpose flavor, 100 GB root disk, 5 Mbit traffic-billed EIP
- Access control: allow SSH/RAGFlow/HTTP only from the operator's current public IP CIDR
- Portal: run a lightweight Flask/Gunicorn app on ECS port `8000` for document upload and CSS keyword search when a fast proof of value is needed

## Common Huawei Cloud Behaviors

- `VPC.0114 Quota exceeded for resources: ['router']`: reuse an existing VPC and subnet; create only a dedicated security group.
- `CSS.0065 The disk has been sold out`: retry CSS with the same smallest flavor and a different disk type such as `HIGH`.
- Ubuntu public images may use `root` as the SSH login user even when typical cloud images use `ubuntu`.
- ECS creation is asynchronous: wait for the ECS job to succeed and server status `ACTIVE`.
- CSS creation is asynchronous: poll cluster details until status is `200` and an endpoint is returned.

## Installation Pattern on ECS

Prefer direct SSH installation after ECS is reachable unless cloud-init is simple and already proven. Complex cloud-init heredocs are easy to break with invalid YAML.

Install Docker and LlamaIndex:

```bash
apt-get update
apt-get install -y ca-certificates curl git docker.io docker-compose-v2 python3-venv python3-pip
systemctl enable --now docker
python3 -m venv /opt/government-rag/venv
/opt/government-rag/venv/bin/pip install --upgrade pip wheel
/opt/government-rag/venv/bin/pip install llama-index opensearch-py llama-index-vector-stores-opensearch esdk-obs-python
```

Install RAGFlow:

```bash
git clone --depth 1 https://github.com/infiniflow/ragflow.git /opt/ragflow
cd /opt/ragflow/docker
docker compose -f docker-compose.yml up -d
```

If Docker Hub is slow, try the Huawei SWR image referenced in RAGFlow's `.env`, but expect occasional SWR/OBS layer `TLS handshake timeout` failures. Retry `docker compose up -d`; do not treat a transient layer timeout as a failed infrastructure deployment.

## Fast Demo Portal

When RAGFlow image pulls are slow or a customer needs an immediate UI, install a lightweight ECS portal before finishing the full RAGFlow stack. The portal should:

- Listen on `0.0.0.0:8000` behind a security group restricted to the operator CIDR.
- Upload `.txt`, `.md`, `.pdf`, and `.docx`.
- Extract text, chunk locally, and index into CSS/OpenSearch.
- Search CSS/OpenSearch and show highlighted snippets, file name, chunk number, and score.
- Be labeled as a demo portal; add authentication before broad access.

Use `scripts/install_ecs_portal.sh` from this skill as the starting point. Example:

```bash
scp -i <key_path> scripts/install_ecs_portal.sh root@<ecs_public_ip>:/root/
ssh -i <key_path> root@<ecs_public_ip> 'CSS_URL=http://<css_private_endpoint>:9200 bash /root/install_ecs_portal.sh'
```

Verify from the operator host:

```bash
curl http://<ecs_public_ip>:8000/health
```

Verify upload/search:

```bash
printf 'Procurement policy requires citation evidence.' > /tmp/sample-policy.txt
curl -L -F 'document=@/tmp/sample-policy.txt' http://<ecs_public_ip>:8000/upload
curl 'http://<ecs_public_ip>:8000/?q=procurement%20citation'
```

## Verification Commands

From the operator host:

```bash
ssh -i <key_path> root@<ecs_public_ip> 'hostname; uptime'
```

From ECS:

```bash
/opt/government-rag/venv/bin/python - <<'PY'
import llama_index
print("llama-index import ok")
PY

curl -sS --connect-timeout 5 http://<css_private_endpoint>:9200 | head -c 300
docker ps --format '{{.Names}} {{.Status}} {{.Ports}}'
```

## Cleanup Discipline

- Delete failed-retry OBS buckets if they are empty.
- Keep the intended demo bucket, ECS, CSS cluster, security group, and SSH key path in a local state file.
- Do not delete pre-existing VPCs/subnets when they were reused.
