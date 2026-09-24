# E02 Ansible Operator Preparation

E02 provides fixed development Playbooks only. `host-inspect.yml` is read-only; `host-ensure-service.yml` contains one fixed service name and must be published as a Rundeck Job after E01 is available. No user or model input can select an arbitrary Playbook or service.

The authorization policy requires a non-expired RFC3339 timestamp, an allowlisted host, service, and action. Validate it before submitting an E01 job:

```bash
./scripts/check-service-authorization.py --host test-host-01 \
  --service autoops-demo.service --action ensure_running
```

The committed placeholder policy deliberately fails validation. Deployment must supply a protected active policy and Rundeck-managed credentials.
