# DWS Cluster Deployment Lessons Learned

1. **Discover before create**: Always use ListNodeTypes and ListClusters before CreateCluster to avoid conflicts and invalid configurations.

2. **Region-dependent capabilities**: Node types, storage types, and versions vary by region. Never assume availability without discovery.

3. **Password security is critical**: The CreateCluster API requires user_pwd. Use --cli-jsonInput to avoid shell history exposure. Rotate password after creation if possible.

4. **Creation is asynchronous**: CreateCluster returns immediately but the cluster takes 10-15 minutes (reference). Use polling with ShowClusters.

5. **Cluster name constraints are strict**: 4-64 chars, letter start, alphanumeric + hyphens + underscores only. Validate before attempting creation.

6. **Node count is mode-dependent**: Cluster mode requires 3-256 nodes. Standalone mode requires exactly 1. Do not assume 3 is always the minimum.

7. **Port 8000 is default but not guaranteed**: The default port is 8000 but the range is 8000-30000. Always read the actual port from the cluster response.

8. **PostgreSQL compatibility is partial**: DWS uses PostgreSQL-compatible protocol but is NOT standard PostgreSQL. Test all SQL features before assuming compatibility.

9. **Security group must be validated**: Never allow 0.0.0.0/0 on the DWS port. Always restrict to authorized CIDR.

10. **Subnet IP capacity must be calculated**: Account for all cluster nodes plus internal components and future growth.

11. **DeleteCluster is destructive**: "All resources including customer data will be released." Always create a snapshot before deletion. Use keep_last_manual_snapshot parameter.

12. **RestoreCluster creates a new cluster**: Restore does not overwrite the original. This incurs additional cost. Plan accordingly.

13. **No DWS MCP exists**: All operations are via hcloud CLI. This limits automation and error handling. Consider building a DWS MCP using mcp-capability-builder.

14. **huaweicloud-deploy does not support DWS**: Use it only for VPC/subnet/SG prerequisites. DWS cluster creation must use hcloud CLI.

15. **OBS external table syntax is version-dependent**: Validate syntax against the specific DWS version before use.
