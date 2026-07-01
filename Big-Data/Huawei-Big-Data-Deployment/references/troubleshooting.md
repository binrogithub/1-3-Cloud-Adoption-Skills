# Troubleshooting

## Provider does not recognize a resource

The Huawei Cloud Terraform provider changes over time. Check the active provider documentation and update the resource name or arguments.

## Flavor unavailable

Smallest available flavors vary by region and AZ. Use variables and document how to list available flavors.

## MRS creation fails

Common causes:

- Unsupported component combination
- Wrong cluster version
- Invalid node flavor
- Missing agency permissions
- Subnet or security group issue

## DWS creation fails

Common causes:

- Unsupported flavor in region
- Insufficient quota
- Wrong subnet/security group
- Password policy issue if password-based setup is used

## DLI queue creation fails

Common causes:

- Queue type not supported in region
- Insufficient quota
- Missing permissions

## CDM unsupported in Terraform

If CDM resources are not available in the active provider version, generate a TODO section and provide manual console/API guidance.

## DataArts unsupported in Terraform

Treat DataArts as a reference architecture in v1 unless concrete provider support is confirmed.
