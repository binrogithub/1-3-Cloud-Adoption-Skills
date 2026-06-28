# Step3 Discovery & SG Plan

## 1. Resource Discovery (Read-only)

- Region: `na-mexico-1`
- Source account project_id: `e84695c2e5a546d6b45fc405416e47f6`
- Target account project_id: `019ea55049357658b4a43d77ec94d728`

### Source RDS
- Instance ID: `e327af04e9204e1e867179f9df2057d7in01`
- Private IP: `192.168.0.183`
- EIP: `119.8.0.182`
- VPC: `e1c3eeea-214f-4028-8c96-bae266bd7114`
- Subnet: `665c39c8-4049-4ba9-83de-b8a34ffc275b`
- SGs: `74cabd8e-bf73-4ec4-a631-644cf1896fe5`, `3994e159-9592-4aa2-892b-79439f0e20e3`

### Target RDS
- Instance ID: `0f07fd696084478cb58752582bf3e802in01`
- Private IP: `192.168.0.183`
- EIP: `94.74.76.132`
- VPC: `0aa90f9e-85f8-43bb-aff7-64c5e209f496`
- Subnet: `385f6a84-92ff-460f-a450-503c9284f5ff`
- SGs: `0c2164fe-cc7c-4e24-ba94-54027f724f80`, `6159c5ba-9999-49cd-87c3-ee8bdc5314ac`

### Target Account EIP Inventory
- Total EIP count: `1`
- Existing EIP `94.74.76.132` is already bound to target RDS port.

### Existing DRS Jobs in target account
- `0` jobs found.

## 2. Security Group Current State (MySQL 3306 relevant)

### Source SG `3994e159-9592-4aa2-892b-79439f0e20e3`
- Rule ID `6be6055f-6254-45aa-9013-812bff7d6a19`: ingress tcp/3306 from `8.219.161.249/32`, description empty.
- Rule ID `4201097a-8e0a-4c08-87c2-51720b7070e1`: ingress tcp/3306 from `147.139.161.240/32`, description empty.

### Target SG `6159c5ba-9999-49cd-87c3-ee8bdc5314ac`
- Rule ID `33fafddb-3f24-4eb7-8397-c9bbfd1cf8f8`: ingress tcp/3306 from `8.219.161.249/32`, description empty.
- Rule ID `d5af1cf6-51de-4dea-91bf-958a9e876714`: ingress tcp/3306 from `147.139.161.240/32`, description empty.

## 3. Planned SG Changes (Need explicit approval)

Because VPC API does not support in-place update of SG rule descriptions, set description by **delete + recreate** same rule:

- For source SG `3994...`:
  - recreate tcp/3306 from `8.219.161.249/32` with description `for rds migration`
  - recreate tcp/3306 from `147.139.161.240/32` with description `for rds migration`

- For target SG `6159...`:
  - recreate tcp/3306 from `8.219.161.249/32` with description `for rds migration`
  - recreate tcp/3306 from `147.139.161.240/32` with description `for rds migration`

No `0.0.0.0/0` ingress will be added.

## 4. DRS Public-network Note

Official docs indicate that for public-network migration, source-side whitelist should allow the DRS instance EIP. If DRS instance EIP is not one of the above IPs, additional `/32` rules will be required after DRS instance creation.

