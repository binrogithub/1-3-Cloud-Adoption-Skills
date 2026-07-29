# Discovery Workflow

## Objective
Discover authentication, region, source resources, existing vaults, policies, and backups before any write operation.

## Inputs
- resource_type: ECS, EVS, or CCE
- source_region
- source_resource_name

## Steps

1. Verify hcloud CLI version
   ```bash
   hcloud version
   ```
   Expected: 6.2.9 or compatible

2. Verify authentication and region
   ```bash
   hcloud CBR ListVault --cli-region=<SOURCE_REGION> --limit=1
   ```

3. Discover source resource
   - ECS: `hcloud ECS ListServersDetails --cli-region=<SOURCE_REGION>`
   - EVS: `hcloud EVS ListVolumes --cli-region=<SOURCE_REGION>`
   - CCE: `hcloud CCE ListClusters --cli-region=<SOURCE_REGION>`

4. Discover protectable resources
   ```bash
   hcloud CBR ListProtectable --cli-region=<SOURCE_REGION> --protectable_type=<TYPE>
   ```

5. Discover existing vaults
   ```bash
   hcloud CBR ListVault --cli-region=<SOURCE_REGION>
   ```

6. Discover existing policies
   ```bash
   hcloud CBR ListPolicies --cli-region=<SOURCE_REGION>
   ```

7. Discover existing backups
   ```bash
   hcloud CBR ListBackups --cli-region=<SOURCE_REGION>
   ```

8. Discover replication capabilities
   ```bash
   hcloud CBR ShowReplicationCapabilities --cli-region=<SOURCE_REGION>
   ```

9. Resolve source resource name to ID
10. Validate source resource state

## Verification
- Version confirmed
- Region accessible
- CBR available
- Source resource found (exactly one match)
- Resource state compatible

## Outputs
- artifacts/cbr-auth-discovery.json
- artifacts/cbr-source-discovery.json
- artifacts/cbr-existing-resources.json

## Stop conditions
- Authentication failure
- Region inaccessible
- CBR not available
- Source resource not found or ambiguous
- Resource state incompatible

## Approval requirements
None (all read-only)
