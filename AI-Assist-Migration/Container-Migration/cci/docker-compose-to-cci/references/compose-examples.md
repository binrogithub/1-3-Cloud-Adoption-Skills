# Docker Compose to CCI Migration Examples

## Example 1: Nginx + Redis (Simple Web App)

### docker-compose.yaml

```yaml
version: "3.8"
services:
  web:
    image: nginx:1.25-alpine
    ports:
      - "80:80"
    environment:
      - REDIS_HOST=redis
      - REDIS_PORT=6379
    depends_on:
      - redis
    restart: always
    cpus: "0.25"
    mem_limit: 512m

  redis:
    image: redis:7-alpine
    restart: always
    cpus: "0.25"
    mem_limit: 256m
```

### CCI v2 API Payloads

**Namespace:**
```json
{
  "apiVersion": "cci/v2",
  "kind": "Namespace",
  "metadata": {
    "name": "webapp",
    "annotations": {
      "yangtse.io/domain-id": "<domain-id>",
      "yangtse.io/project-id": "<project-id>"
    }
  }
}
```

**Network:**
```json
{
  "apiVersion": "yangtse/v2",
  "kind": "Network",
  "metadata": {
    "name": "webapp-net",
    "annotations": {
      "yangtse.io/domain-id": "<domain-id>",
      "yangtse.io/project-id": "<project-id>"
    }
  },
  "spec": {
    "networkType": "underlay_neutron",
    "securityGroups": ["<sg-id>"],
    "subnets": [{"subnetID": "<neutron-subnet-id>"}]
  }
}
```

**ConfigMap (web):**
```json
{
  "apiVersion": "cci/v2",
  "kind": "ConfigMap",
  "metadata": {"name": "web-config"},
  "data": {"REDIS_HOST": "redis", "REDIS_PORT": "6379"}
}
```

**Deployment (web):**
```json
{
  "apiVersion": "cci/v2",
  "kind": "Deployment",
  "metadata": {"name": "web"},
  "spec": {
    "replicas": 1,
    "selector": {"matchLabels": {"app": "web"}},
    "template": {
      "metadata": {"labels": {"app": "web"}},
      "spec": {
        "containers": [{
          "name": "web",
          "image": "nginx:1.25-alpine",
          "ports": [{"containerPort": 80}],
          "env": [
            {"name": "REDIS_HOST", "value": "redis"},
            {"name": "REDIS_PORT", "value": "6379"}
          ],
          "resources": {
            "requests": {"cpu": "250m", "memory": "512Mi"},
            "limits": {"cpu": "500m", "memory": "1024Mi"}
          }
        }]
      }
    }
  }
}
```

**Deployment (redis):**
```json
{
  "apiVersion": "cci/v2",
  "kind": "Deployment",
  "metadata": {"name": "redis"},
  "spec": {
    "replicas": 1,
    "selector": {"matchLabels": {"app": "redis"}},
    "template": {
      "metadata": {"labels": {"app": "redis"}},
      "spec": {
        "containers": [{
          "name": "redis",
          "image": "redis:7-alpine",
          "resources": {
            "requests": {"cpu": "250m", "memory": "256Mi"},
            "limits": {"cpu": "500m", "memory": "512Mi"}
          }
        }]
      }
    }
  }
}
```

**Service (web):**
```json
{
  "apiVersion": "cci/v2",
  "kind": "Service",
  "metadata": {
    "name": "web-svc",
    "annotations": {"kubernetes.io/elb.id": "<elb-id>"}
  },
  "spec": {
    "type": "LoadBalancer",
    "selector": {"app": "web"},
    "ports": [{"port": 80, "targetPort": 80, "protocol": "TCP"}]
  }
}
```

### Migration Commands

```bash
# Parse
python3 compose-to-cci.py parse docker-compose.yaml

# Translate to JSON payloads
python3 compose-to-cci.py translate docker-compose.yaml --namespace webapp --output payloads/

# Full migration
python3 compose-to-cci.py migrate docker-compose.yaml \
  --ak <AK> --sk <SK> --project-id <PID> \
  --region sa-brazil-1 --namespace webapp \
  --domain-id <DID> --subnet-id <SID> --sg-id <SGID>
```

## Example 2: GitLab Runner (CI/CD)

### docker-compose.yaml

```yaml
version: "3.8"
services:
  gitlab-runner:
    image: gitlab/gitlab-runner:latest
    volumes:
      - runner-config:/etc/gitlab-runner
    environment:
      - CI_SERVER_URL=https://gitlab.example.com
      - REGISTRATION_TOKEN=${RUNNER_TOKEN}
    restart: always
    cpus: "0.5"
    mem_limit: 1g

volumes:
  runner-config:
```

### CCI Translation

- `gitlab-runner` → Deployment (cci/v2)
- `runner-config` volume → PVC with `storageClassName: sfs-turbo`
- `CI_SERVER_URL` → ConfigMap
- `REGISTRATION_TOKEN` → Secret (base64 encoded)
- No ports → no Service needed

## Example 3: Multi-Service App with Health Checks

### docker-compose.yaml

```yaml
version: "3.8"
services:
  api:
    image: my-api:latest
    ports: ["8080:8080"]
    environment:
      DB_HOST: db
      DB_PORT: 5432
    depends_on:
      db:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
    cpus: "0.5"
    mem_limit: 1g

  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: myapp
      POSTGRES_PASSWORD: secret
    volumes:
      - db-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD", "pg_isready"]
      interval: 10s
    cpus: "0.5"
    mem_limit: 1g

volumes:
  db-data:
```

### CCI Translation Notes

- `api` and `db` → two Deployments in same namespace
- `db-data` → PVC (SFS Turbo, 10Gi)
- `api` healthcheck → `livenessProbe.exec.command: ["curl", "-f", "http://localhost:8080/health"]`
- `db` healthcheck → `livenessProbe.exec.command: ["pg_isready"]`
- `depends_on` with `condition: service_healthy` → init container that waits for db readiness
- `POSTGRES_PASSWORD` → Secret (base64: `c2VjcmV0`)
- `api` port 8080 → Service LoadBalancer with ELB
