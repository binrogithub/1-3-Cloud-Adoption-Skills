# AI-Assisted Image Discovery and ECS Deployment

## Overview

This scenario demonstrates the core AI-assisted workflow: using OpenCode with HCloud MCP and Terraform MCP to **discover** available OS images on Huawei Cloud and **generate** correct Terraform code for ECS deployment — all through natural conversation.

The AI agent doesn't guess image IDs or flavors. It calls HCloud MCP to list real images available in your account, asks you which one to use, then writes Terraform with the correct `image_id` — verified against the live cloud.

## The Workflow

```
User: "Deploy a web server to my existing VPC"
  |
  v
1. AI gets ECS schema from Terraform MCP
   -> needs: image_id, flavor_id, availability_zone, network.uuid
  |
2. AI writes partial Terraform with placeholders
   resource "huaweicloud_compute_instance" "web" {
     image_id  = "???"  <- need Ubuntu image
     flavor_id = "???"  <- need available flavors
   }
  |
3. AI discovers images via HCloud MCP
   hcloud_list_images(imagetype="gold", os_type="Linux")
   -> Ubuntu 22.04: 67c29d17-... · Ubuntu 20.04: a1b2c3d4-...
  |
4. AI asks: "Which OS image? 1) Ubuntu 22.04 LTS 2) Ubuntu 20.04 LTS"
   User: "Ubuntu 22.04"
  |
5. AI discovers flavors and AZs in parallel
   hcloud_list_flavors(region="la-north-2") -> c6.large.2, c6.xlarge.2
   hcloud_list_availability_zones(region="la-north-2") -> la-north-2a, 2b, 2c
  |
6. AI asks: "Which flavor and AZ?"
   User: "c6.large.2 in la-north-2a"
  |
7. AI discovers VPC and subnet
   hcloud_list_vpcs -> ca5aa4ea...
   hcloud_list_subnets(vpc_id="ca5aa4ea...") -> 701ac87c...
  |
8. AI writes final Terraform with all values resolved
   image_id          = "67c29d17-33bd-..."  ✓
   flavor_id         = "c6.large.2"          ✓
   availability_zone = "la-north-2a"         ✓
   network.uuid      = "701ac87c-47ea-..."   ✓
```

## What's Included

| Path | Description |
|------|-------------|
| `webpage/` | Interactive landing page demonstrating the AI workflow with 3 scenarios (RDS, ECS, Server Restart) |
| `webpage/index.html` | Main page showing the conversational AI workflow |
| `webpage/app.js` | Scroll animations and reveal effects |
| `webpage/styles.css` | Styling for the landing page |
| `skills/huaweicloud-terraform-planner/SKILL.md` | The skill that orchestrates discovery + code generation |

## Key Concepts

### Discover Before Create
The AI never hardcodes resource IDs. It discovers real values from your Huawei Cloud account using HCloud MCP tools, then writes Terraform `data` blocks to reference them:

```hcl
data "huaweicloud_images_image" "ubuntu" {
  name        = "Ubuntu 22.04 server 64bit"
  visibility  = "public"
  most_recent = true
}

resource "huaweicloud_compute_instance" "web" {
  image_id = data.huaweicloud_images_image.ubuntu.id
}
```

### Batch Parallel Discoveries
Independent discoveries (images, flavors, AZs, VPCs, key pairs) are called simultaneously. Only dependent calls (subnets need VPC ID) are serialized.

### Ask Only About Gaps
If the user said "Ubuntu 22.04 in la-north-2", the AI doesn't ask which OS or which region. It only asks about unspecified values with multiple options.

## The Landing Page

The `webpage/` directory contains an interactive HTML landing page that visualizes three AI workflow scenarios:

1. **RDS Deployment** — AI discovers flavors, storage types, VPCs, subnets and writes Terraform for an RDS MySQL instance
2. **ECS Deployment** — AI discovers OS images, flavors, AZs, VPCs, subnets and writes Terraform for a web server
3. **Server Restart** — AI finds a server by name and performs an operational action (restart) via the CLI escape hatch

The page also shows the full HCloud MCP tool catalog (90 tools across 18 services) and the Terraform MCP registry tools.

## Related Skills

- [huaweicloud-terraform-planner](../../Cloud-Foundation/Automation-and-IaC/huaweicloud-terraform-planner/SKILL.md) — The skill used in this scenario for schema discovery and Terraform generation.

## Video Reference

This scenario corresponds to the training video `importingimagesdemo.mkv` (not included in the repository).
