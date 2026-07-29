# SDRS Known Issues and Troubleshooting

## Troubleshooting Table

| Symptom | Likely cause | Diagnosis | Resolution | Retry safe |
|---|---|---|---|---|
| Service not available in region | SDRS not deployed in region | Check SDRS console in region | Select alternative region or contact support | No |
| Region pair not supported | SDRS does not support this region combination | Check official documentation for supported pairs | Select alternative DR region | No |
| Cross-region topology unsupported | SDRS version or configuration does not support cross-region for this pair | Check SDRS version and region pair | Use cross-AZ or alternative region pair | No |
| Source ECS unsupported | ECS flavor or configuration not compatible with SDRS | Check SDRS supported server types | Change ECS flavor or use CBR as alternative | No |
| OS unsupported | Operating system not in SDRS supported list | Check SDRS supported OS list | Change OS or use CBR as alternative | No |
| Disk type unsupported | EVS disk type not compatible with SDRS replication | Check SDRS supported disk types | Change disk type or exclude from protection | No |
| Existing protection conflict | ECS already protected by another protection group | Check existing protection groups in console | Remove from existing group or reuse group | No |
| Gateway installation failure | Network, port, OS, or IAM issue | Check gateway logs, network connectivity, port access | Fix root cause, retry installation | Yes |
| Gateway registration failure | Credentials, connectivity, or service issue | Check gateway status, network, IAM | Fix root cause, retry registration | Yes |
| Gateway unhealthy | Resource exhaustion, network issue, or service degradation | Check gateway resource usage, network health | Restart gateway or escalate | Yes |
| Required port blocked | Security group or firewall blocking gateway communication | Check security group rules, firewall rules | Open required ports, retry | Yes |
| Insufficient bandwidth | Network bandwidth insufficient for replication | Check replication lag trend, network utilization | Increase bandwidth or reduce data change rate | Yes |
| Replication lag above threshold | High data change rate, insufficient bandwidth, or gateway issue | Check replication lag, data rate, bandwidth, gateway health | Increase bandwidth, optimize data rate, fix gateway | Yes |
| Replication pair degraded | Network interruption, source or target volume issue | Check pair status, network, volume health | Fix root cause, re-enable if needed | Yes |
| Protected instance error | ECS state change, configuration issue | Check ECS status, protection configuration | Fix ECS state, retry protection | Yes |
| Protection cannot be enabled | Replication pairs not ready, gateway issue | Check all pair statuses, gateway health | Fix pairs/gateway, retry | Yes |
| Drill creation fails | Quota insufficient, protection not active | Check quotas, protection status | Fix quotas/activation, retry | Yes |
| Drill server cannot boot | DR site network, security group, or OS issue | Check DR site network, SG, OS image | Fix configuration, retry drill | Yes |
| Network unavailable in DR site | VPC, subnet, or route issue | Check DR site VPC, subnet, route tables | Fix network configuration | Yes |
| Security group mismatch | DR site SG differs from production | Compare SG rules between sites | Align SG rules at DR site | Yes |
| DNS points to production | DNS not updated after failover | Check DNS records | Update DNS manually per plan | Yes |
| Planned failover rejected | Protection not active, replication not ready, or approval missing | Check protection status, replication, approval | Fix prerequisites, obtain approval, retry | Yes |
| Unplanned failover leaves uncertain primary state | Primary site state unknown after failover | Assess both sites manually | Decide based on data consistency, do not assume | No |
| Reverse reprotection unavailable | SDRS version, region, or gateway issue | Check SDRS version, region support, gateway | Fix root cause, retry; DR site is UNPROTECTED | Yes |
| Failback blocked | Reverse replication not synchronized, original site not ready | Check reverse replication status, original site capacity | Wait for sync, fix site, retry | Yes |
| Target capacity insufficient | DR site quotas or ECS flavors insufficient | Check quotas and available flavors | Request quota increase or adjust instance count | No |
| IAM permission denied | Missing required permissions | Check IAM permissions in both regions | Request IAM admin to grant permissions | Yes |
| Quota exceeded | Protection group, instance, or volume quota exceeded | Check quotas in console | Request quota increase via ticket | No |
| Console field differs from documentation | SDRS console UI updated | Document discrepancy | Use console as source of truth, report via ticket | No |
| API or service version mismatch | SDRS API version differs between regions | Check SDRS API version in both regions | Document version, contact support if needed | No |
