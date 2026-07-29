# DWS Cluster Deployment Known Issues

## Troubleshooting

| Symptom | Likely cause | Diagnostic command | Resolution | Retry safe |
|---|---|---|---|---|
| DWS service unavailable in region | DWS not enabled or region unsupported | `hcloud DWS ListClusters --cli-region=<REGION>` | Use supported region; check service status | Yes |
| Version unavailable | Engine version not offered in region | `hcloud DWS ListNodeTypes --cli-region=<REGION>` | Select available version | Yes |
| Node type unavailable | Flavor not offered in region | `hcloud DWS ListNodeTypes --cli-region=<REGION>` | Select available node type | Yes |
| Node type unavailable in selected AZ | Flavor restricted to specific AZs | `hcloud DWS ListNodeTypes --cli-region=<REGION>` | Change AZ or node type | Yes |
| Storage type unavailable | Storage not offered in region/version | `hcloud DWS ListNodeTypes --cli-region=<REGION>` | Select available storage type | Yes |
| Invalid node count | number_of_node outside 3-256 (cluster) or !=1 (standalone) | Validate against constraints | Correct node count | Yes |
| HA configuration invalid | HA not supported for selected version/region | Check DWS documentation | Adjust HA requirement | Yes |
| Cluster name already exists | Duplicate name in project/region | `hcloud DWS ListClusters --cli-region=<REGION>` | Rename or evaluate reuse | Yes |
| Invalid database name | Name violates DWS constraints | Check naming rules (4-64 chars, letter start) | Correct name | Yes |
| Subnet has insufficient IP addresses | Available IPs < required nodes + buffer | `hcloud VPC ListSubnets` | Use larger subnet or reduce node count | Yes |
| VPC or subnet mismatch | Resources in different VPC or region | `hcloud VPC ListVpcs` / `hcloud VPC ListSubnets` | Use matching VPC/subnet | Yes |
| Security group blocks port | SG rule does not allow DWS port from client CIDR | `hcloud VPC ListSecurityGroupRules` | Add rule for authorized CIDR | Yes |
| Security group too permissive | SG rule allows 0.0.0.0/0 on DWS port | `hcloud VPC ListSecurityGroupRules` | Restrict to authorized CIDR | No |
| EIP binding unsupported | Cluster or region does not support public access | Check DWS documentation | Use private access only | No |
| EIP quota exceeded | EIP limit reached | `hcloud VPC ListPublicIps` | Request quota increase or release unused EIP | Yes |
| DWS quota exceeded | Cluster limit reached | Quota API | Request quota increase | Yes |
| Node quota exceeded | Compute node limit reached | Quota API | Request quota increase | Yes |
| Storage quota exceeded | Storage limit reached | Quota API | Request quota increase | Yes |
| IAM permission denied | Insufficient permissions | Check IAM policy | Grant DWS permissions | Yes |
| Password exposed in shell history | Password passed via visible command line | Check shell history | Use --cli-jsonInput; rotate password | No |
| Password rejected by policy | Password does not meet complexity rules | Check DWS password policy | Provide compliant password | Yes |
| CreateCluster request rejected | Invalid parameters or quota exceeded | Check API error response | Fix parameters or request quota | Yes |
| Cluster remains in creating state | Long creation time or stuck | `hcloud DWS ShowClusters` | Continue polling; escalate if stuck > 30 min | Yes |
| Cluster enters failed state | Creation error | `hcloud DWS ShowClusters` | Inspect error; do NOT auto-delete | No |
| Polling timeout | Cluster not operational within expected time | `hcloud DWS ShowClusters` | Investigate manually; extend timeout | Yes |
| Connection refused | Endpoint not reachable | psql/JDBC connection test | Check SG, endpoint, port | Yes |
| TLS or certificate error | Certificate mismatch or not trusted | psql with SSL options | Configure trust or disable SSL (dev only) | Yes |
| Authentication failed | Wrong username or password | Verify credentials | Reset password if needed | Yes |
| JDBC driver incompatibility | Driver version mismatch with DWS version | Check DWS version | Use compatible JDBC driver | No |
| psql version incompatibility | psql version incompatible with DWS | `psql --version` | Use compatible psql version | No |
| OBS access denied | IAM permissions or bucket policy | Test OBS access | Grant required permissions | Yes |
| OBS data format error | Unsupported format or delimiter | Check data format | Use supported format | Yes |
| External table syntax unsupported | Syntax not supported in DWS version | Check DWS documentation | Use supported syntax | No |
| Snapshot creation failure | Insufficient storage or cluster busy | `hcloud DWS ListSnapshots` | Retry or check storage | Yes |
| Snapshot policy invalid | Schedule or retention not supported | Check DWS documentation | Use valid policy | Yes |
| Restore capability mismatch | Snapshot incompatible with target config | `hcloud DWS ListSnapshotDetails` | Adjust target config | No |
| Resize operation unavailable | Resize not supported for current config | Check DWS documentation | Use supported resize method | No |
| Insufficient target capacity | Target cannot accommodate resize | Check available capacity | Increase capacity first | Yes |
| CLI version mismatch | hcloud version incompatible | `hcloud --version` | Use verified version (6.2.9) | No |
| API throttling or request timeout | Rate limiting or transient error | Retry with backoff | Wait and retry | Yes |
