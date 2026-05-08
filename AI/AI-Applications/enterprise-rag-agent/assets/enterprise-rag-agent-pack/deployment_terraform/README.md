# Terraform Placeholder

Create customer-specific Terraform here for:

- OBS buckets for raw documents and parse artifacts.
- CSS/OpenSearch indexes.
- GaussDB/RDS metadata and audit tables.
- Secrets or environment variable bindings for MaaS and service credentials.
- Network, IAM, and logging resources required by the customer security baseline.

Do not commit cloud access keys or secret keys.

Demo defaults:

- Reuse an existing VPC/subnet when VPC router quota is exhausted.
- Create a dedicated security group for the demo.
- Restrict inbound SSH, HTTP, HTTPS, and RAGFlow ports to the operator CIDR.
- Use the smallest available CSS flavor, and document any disk-type fallback caused by regional inventory.
- Store non-secret outputs such as OBS bucket name, CSS endpoint, ECS public IP, and SSH key path.
