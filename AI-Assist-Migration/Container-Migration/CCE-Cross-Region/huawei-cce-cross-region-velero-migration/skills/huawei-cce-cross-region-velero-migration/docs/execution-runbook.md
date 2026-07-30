# Execution Runbook: CCE Cross-Region Velero Migration

## Step 1: Discovery
```bash
# List namespaces
kubectl get namespaces

# List all resources per namespace
kubectl get all,configmaps,secrets,ingress,pvc,storageclass -n <namespace>

# Check Velero status
velero backup-location get
velero snapshot-location get
```

## Step 2: Architecture Validation
- Compare Kubernetes versions (source vs target)
- Verify StorageClass mapping
- Verify OBS accessibility from target region
- Use `RunTerraformPlan` to preview target infrastructure

## Step 3: Readiness Check
```bash
# Verify Velero on source
velero backup describe --details

# Verify Velero on target
velero restore describe --details

# Check cluster capacity
kubectl top nodes
```

## Step 4: Plan Generation
- Use `GenerateTerraformFromArchitecture` for target infrastructure
- Use `ValidateTerraformConfiguration` to validate
- Generate Velero backup/restore commands
- Document DNS, ELB, and image migration steps

## Step 5: Approval
- Present complete plan
- Obtain explicit approval

## Step 6: Execution
```bash
# Apply Terraform (MANUAL)
terraform apply

# Velero backup
velero backup create migration-backup \
  --include-namespaces ns1,ns2 \
  --snapshot-volumes=false

# Wait for completion
velero backup describe migration-backup --details

# Velero restore
velero restore create migration-restore \
  --from-backup migration-backup \
  --namespace-mappings ns1:ns1,ns2:ns2

# Wait for completion
velero restore describe migration-restore --details
```

## Step 7: Validation
```bash
# Verify deployments
kubectl get deployments -n <namespace>

# Verify services
kubectl get svc -n <namespace>

# Verify ingress
kubectl get ingress -n <namespace>

# Verify PVCs
kubectl get pvc -n <namespace>
```

## Step 8: Cutover
- Update DNS records
- Verify traffic routing
- Monitor application health

## Step 9: Rollback (if needed)
- Revert DNS
- Clean up target resources
- Destroy target infrastructure

## Step 10: Closure
- Generate final report
- Archive backup
- Update documentation
