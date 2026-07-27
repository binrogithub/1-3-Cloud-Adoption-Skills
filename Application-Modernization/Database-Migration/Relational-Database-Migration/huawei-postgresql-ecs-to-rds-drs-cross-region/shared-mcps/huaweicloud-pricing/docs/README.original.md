# Huawei Cloud Pricing MCP

Local MCP tool for Huawei Cloud architecture pricing using BSS/OCE APIs.

## Main capabilities

- Estimate architecture pricing using Huawei Cloud BSS/OCE.
- Validate ECS flavor availability by region and AZ.
- Block ECS flavors marked as abandon, sellout, or not available.
- Optionally calculate reference pricing for blocked components.
- Search ECS flavor candidates across multiple regions and AZs.
- Provide semantic cost breakdown for public Shared ELB as ELB base + EIP bandwidth.

## Important rules

- Pricing comes from Huawei Cloud BSS/OCE.
- Discovery decides availability.
- monthly_total includes only validated priced components.
- monthly_total_estimated_with_blocked is reference-only.
- Blocked ECS components remain not recommended for deployment.
