import supportedServicesConfig from "./config/supported-services.json" with { type: "json" };

const PHASE1 = new Set(supportedServicesConfig.phase1_services);
const PHASE2 = new Set(supportedServicesConfig.phase2_services);

function sanitizeName(name) {
  return name.replace(/[^a-zA-Z0-9_]/g, "_").replace(/_+/g, "_");
}

function tfResource(resourceType, name, body) {
  return `resource "${resourceType}" "${sanitizeName(name)}" {\n${body}\n}`;
}

function generateVersionsTf() {
  return `terraform {
  required_version = ">= 1.5.0"

  required_providers {
    huaweicloud = {
      source  = "huaweicloud/huaweicloud"
      version = "~> 1.70"
    }
  }
}
`;
}

function generateProvidersTf(region) {
  return `provider "huaweicloud" {
  region = var.region

  # Credentials are read from environment variables (HW_ACCESS_KEY, HW_SECRET_KEY).
  # NEVER hardcode credentials in this file or in .tfvars.
}
`;
}

function generateVariablesTf(components) {
  const hasEcs = components.some(c => c.service === "ecs");
  const hasEip = components.some(c => c.service === "eip");
  const hasSg = components.some(c => c.service === "security_group");
  const hasRds = components.some(c => c.service === "rds_mysql");

  let vars = `variable "region" {
  description = "Huawei Cloud region"
  type        = string
}

variable "availability_zone" {
  description = "Availability zone for compute resources"
  type        = string
  default     = "la-north-2a"
}
`;

  if (hasEcs) {
    vars += `
variable "ecs_admin_password" {
  description = "ECS admin password - set via TF_VAR_ecs_admin_password env var"
  type        = string
  sensitive   = true
}
`;
  }

  if (hasRds) {
    vars += `
variable "rds_password" {
  description = "RDS MySQL root password - set via TF_VAR_rds_password env var"
  type        = string
  sensitive   = true
}
`;
  }

  if (hasSg) {
    vars += `
variable "admin_ssh_cidr" {
  description = "CIDR block allowed for SSH access - override for your IP"
  type        = string
  default     = "0.0.0.0/0"
}
`;
  }

  if (hasEip) {
    vars += `
variable "eip_bandwidth_mbps" {
  description = "EIP bandwidth in Mbps"
  type        = number
  default     = 10
}
`;
  }

  return vars;
}

function generateTfvarsExample(architecture) {
  let content = `# terraform.tfvars.example
# Copy to terraform.tfvars and fill in values.
# NEVER commit terraform.tfvars with real secrets.

region = "${architecture.region}"
`;

  const hasEcs = architecture.components.some(c => c.service === "ecs");
  const hasRds = architecture.components.some(c => c.service === "rds_mysql");
  const hasSg = architecture.components.some(c => c.service === "security_group");
  const hasEip = architecture.components.some(c => c.service === "eip");

  if (hasEcs) {
    content += `
# Set ECS admin pass via env: export TF_VAR_ecs_admin_password="..."
# Do NOT uncomment the line below with a real value:
# ecs_admin_password = "REPLACE_WITH_STRONG_PASSWORD"
`;
  }

  if (hasRds) {
    content += `
# Set RDS pass via env: export TF_VAR_rds_password="..."
# Do NOT uncomment the line below with a real value:
# rds_password = "CHANGE_ME_DO_NOT_COMMIT_REAL_PASSWORD"
`;
  }

  if (hasSg) {
    content += `
admin_ssh_cidr = "YOUR_IP/32"
`;
  }

  if (hasEip) {
    const eipComp = architecture.components.find(c => c.service === "eip");
    content += `
eip_bandwidth_mbps = ${eipComp?.bandwidth_mbps || 10}
`;
  }

  return content;
}

function generateVpcResource(comp) {
  const body = `  name = "${comp.name}"
  cidr = "${comp.cidr}"`;
  return tfResource("huaweicloud_vpc", comp.name, body);
}

function generateSubnetResource(comp, vpcName) {
  const body = `  name       = "${comp.name}"
  vpc_id     = huaweicloud_vpc.${sanitizeName(vpcName)}.id
  cidr       = "${comp.cidr}"${comp.gateway_ip ? `\n  gateway_ip = "${comp.gateway_ip}"` : ""}`;
  return tfResource("huaweicloud_vpc_subnet", comp.name, body);
}

function generateSecurityGroupResource(comp) {
  const body = `  name = "${comp.name}"`;
  return tfResource("huaweicloud_networking_secgroup", comp.name, body);
}

function generateSecurityGroupRules(comp, sgName) {
  if (!comp.rules || comp.rules.length === 0) return "";

  const rules = [];
  for (const rule of comp.rules) {
    const remotePrefix = rule.remote_ip_prefix === "CUSTOM_ADMIN_CIDR_REQUIRED"
      ? "var.admin_ssh_cidr"
      : `"${rule.remote_ip_prefix}"`;

    const direction = rule.direction || "ingress";
    const portMin = rule.port;
    const portMax = rule.port;

    const body = `  direction         = "${direction}"
  protocol          = "${rule.protocol}"
  port_range_min    = ${portMin}
  port_range_max    = ${portMax}
  remote_ip_prefix  = ${remotePrefix}
  security_group_id = huaweicloud_networking_secgroup.${sanitizeName(sgName)}.id
  ethertype         = "IPv4"`;

    rules.push(tfResource("huaweicloud_networking_secgroup_rule", `${sgName}-${direction}-${rule.protocol}-${rule.port}`, body));
  }

  return rules.join("\n\n");
}

function generateEcsResources(comp, subnetName, sgName) {
  const quantity = comp.quantity || 1;
  const resources = [];

  for (let i = 0; i < quantity; i++) {
    const instanceName = quantity > 1 ? `${comp.name}-${i + 1}` : comp.name;
    const body = `  name               = "${instanceName}"
  flavor_id          = "${comp.flavor}"
  image_name         = "${comp.image_name}"
  availability_zone  = var.availability_zone
  security_group_ids = [huaweicloud_networking_secgroup.${sanitizeName(sgName)}.id]

  network {
    uuid = huaweicloud_vpc_subnet.${sanitizeName(subnetName)}.id
  }

  system_disk_type = "${comp.system_disk_type}"
  system_disk_size = ${comp.system_disk_size_gb}

  admin_pass = var.ecs_admin_password`;

    resources.push(tfResource("huaweicloud_compute_instance", instanceName, body));
  }

  return resources.join("\n\n");
}

function generateElbResource(comp, vpcName, subnetName) {
  const listenerPort = comp.listener_port || 80;
  const isShared = comp.type === "shared";

  const elbBody = `  name              = "${comp.name}"
  description       = "${isShared ? "Shared" : "Dedicated"} ELB for ${comp.name}"
  vpc_id            = huaweicloud_vpc.${sanitizeName(vpcName)}.id
  availability_zone = [var.availability_zone]

  ipv4_subnet_id = huaweicloud_vpc_subnet.${sanitizeName(subnetName)}.id`;

  const elbResource = tfResource("huaweicloud_elb_loadbalancer", comp.name, elbBody);

  const listenerBody = `  loadbalancer_id = huaweicloud_elb_loadbalancer.${sanitizeName(comp.name)}.id
  protocol        = "TCP"
  protocol_port   = ${listenerPort}`;

  const listenerResource = tfResource("huaweicloud_elb_listener", comp.name, listenerBody);

  const poolBody = `  loadbalancer_id = huaweicloud_elb_loadbalancer.${sanitizeName(comp.name)}.id
  protocol        = "TCP"
  lb_method       = "ROUND_ROBIN"
  listener_id     = huaweicloud_elb_listener.${sanitizeName(comp.name)}.id`;

  const poolResource = tfResource("huaweicloud_elb_pool", comp.name, poolBody);

  return [elbResource, listenerResource, poolResource].join("\n\n");
}

function generateEipResource(comp) {
  const bandwidth = comp.bandwidth_mbps || 10;
  const body = `  publicip {
    type = "5_bgp"
  }

  bandwidth {
    name        = "${comp.name}-bandwidth"
    size        = ${bandwidth}
    share_type  = "PER"
    charge_mode = "bandwidth"
  }`;

  return tfResource("huaweicloud_vpc_eip", comp.name, body);
}

function generateRdsMysqlResource(comp, vpcName, subnetName, sgName) {
  const azValue = comp.availability_zone
    ? `["${comp.availability_zone}"]`
    : "[var.availability_zone]";
  const engineVersion = comp.engine_version || "8.0";
  const dbPort = comp.db_port || 3306;
  const dbName = comp.database_name || "appdb";
  const username = comp.username || "root";

  const body = `  name              = "${comp.name}"
  flavor            = "${comp.flavor}"
  availability_zone = ${azValue}

  vpc_id            = huaweicloud_vpc.${sanitizeName(vpcName)}.id
  subnet_id         = huaweicloud_vpc_subnet.${sanitizeName(subnetName)}.id
  security_group_id = huaweicloud_networking_secgroup.${sanitizeName(sgName)}.id

  volume {
    type = "${comp.storage_type}"
    size = ${comp.storage_gb}
  }

  db {
    type      = "mysql"
    version   = "${engineVersion}"
    user_name = "${username}"
    password  = var.rds_password
    port      = ${dbPort}
  }`;

  return tfResource("huaweicloud_rds_instance", comp.name, body);
}

function generateObsResource(comp) {
  const bucketName = comp.bucket_name || comp.name;
  const storageClass = comp.storage_class || "STANDARD";
  const acl = comp.acl || "private";

  const body = `  bucket        = "${bucketName}"
  storage_class = "${storageClass}"
  acl           = "${acl}"`;

  return tfResource("huaweicloud_obs_bucket", comp.name, body);
}

function generateElbBackendMembers(elbComp, ecsComps, subnetName) {
  if (!elbComp || !ecsComps || ecsComps.length === 0) {
    return "";
  }

  const port = elbComp.backend_port || 80;
  const members = [];

  for (const ecsComp of ecsComps) {
    const quantity = ecsComp.quantity || 1;
    for (let i = 0; i < quantity; i++) {
      const instanceName = quantity > 1 ? `${ecsComp.name}-${i + 1}` : ecsComp.name;
      const memberName = `${elbComp.name}-${instanceName}`;
      const body = `  pool_id       = huaweicloud_elb_pool.${sanitizeName(elbComp.name)}.id
  address       = huaweicloud_compute_instance.${sanitizeName(instanceName)}.access_ip_v4
  protocol_port = ${port}
  subnet_id     = huaweicloud_vpc_subnet.${sanitizeName(subnetName)}.id`;

      members.push(tfResource("huaweicloud_elb_member", memberName, body));
    }
  }

  return members.join("\n\n");
}

function generateMainTf(architecture) {
  const components = architecture.components;
  const vpc = components.find(c => c.service === "vpc");
  const subnet = components.find(c => c.service === "subnet");
  const sg = components.find(c => c.service === "security_group");

  const vpcName = vpc ? vpc.name : "default-vpc";
  const subnetName = subnet ? subnet.name : "default-subnet";
  const sgName = sg ? sg.name : "default-sg";

  const ecsComps = components.filter(c => c.service === "ecs");
  const elbComps = components.filter(c => c.service === "elb");

  const sections = [];

  sections.push(`# Architecture: ${architecture.architecture_id}
# Region: ${architecture.region}
# Generated by huaweicloud-deploy-mcp (phase 2)
# DO NOT edit manually - regenerate from architecture definition.
`);

  for (const comp of components) {
    switch (comp.service) {
      case "vpc":
        sections.push(generateVpcResource(comp));
        break;
      case "subnet":
        sections.push(generateSubnetResource(comp, vpcName));
        break;
      case "security_group":
        sections.push(generateSecurityGroupResource(comp));
        break;
      case "ecs":
        sections.push(generateEcsResources(comp, subnetName, sgName));
        break;
      case "elb":
        sections.push(generateElbResource(comp, vpcName, subnetName));
        break;
      case "eip":
        sections.push(generateEipResource(comp));
        break;
      case "rds_mysql":
        sections.push(generateRdsMysqlResource(comp, vpcName, subnetName, sgName));
        break;
      case "obs":
        sections.push(generateObsResource(comp));
        break;
      case "elb_backend_attachment":
        break;
      default:
        sections.push(`# UNSUPPORTED: ${comp.service} "${comp.name || "(unnamed)"}" - skipped`);
    }
  }

  if (sg) {
    const rulesSection = generateSecurityGroupRules(sg, sgName);
    if (rulesSection) {
      sections.push(rulesSection);
    }
  }

  for (const elbComp of elbComps) {
    const backendSection = generateElbBackendMembers(elbComp, ecsComps, subnetName);
    if (backendSection) {
      sections.push(backendSection);
    }
  }

  return sections.join("\n\n");
}

function generateOutputsTf(architecture) {
  const components = architecture.components;
  const outputs = [];

  const vpc = components.find(c => c.service === "vpc");
  if (vpc) {
    outputs.push(`output "vpc_id" {
  description = "VPC ID"
  value       = huaweicloud_vpc.${sanitizeName(vpc.name)}.id
}`);
  }

  const subnet = components.find(c => c.service === "subnet");
  if (subnet) {
    outputs.push(`output "subnet_id" {
  description = "Subnet ID"
  value       = huaweicloud_vpc_subnet.${sanitizeName(subnet.name)}.id
}`);
  }

  const ecsComps = components.filter(c => c.service === "ecs");
  for (const comp of ecsComps) {
    const quantity = comp.quantity || 1;
    for (let i = 0; i < quantity; i++) {
      const instanceName = quantity > 1 ? `${comp.name}-${i + 1}` : comp.name;
      outputs.push(`output "ecs_${sanitizeName(instanceName)}_id" {
  description = "ECS instance ID for ${instanceName}"
  value       = huaweicloud_compute_instance.${sanitizeName(instanceName)}.id
}`);
    }
  }

  const eipComps = components.filter(c => c.service === "eip");
  for (const comp of eipComps) {
    outputs.push(`output "eip_${sanitizeName(comp.name)}_address" {
  description = "Public IP address for ${comp.name}"
  value       = huaweicloud_vpc_eip.${sanitizeName(comp.name)}.address
}`);
  }

  const elbComps = components.filter(c => c.service === "elb");
  for (const comp of elbComps) {
    outputs.push(`output "elb_${sanitizeName(comp.name)}_id" {
  description = "ELB ID for ${comp.name}"
  value       = huaweicloud_elb_loadbalancer.${sanitizeName(comp.name)}.id
}`);
  }

  const rdsComps = components.filter(c => c.service === "rds_mysql");
  for (const comp of rdsComps) {
    outputs.push(`output "rds_${sanitizeName(comp.name)}_id" {
  description = "RDS instance ID for ${comp.name}"
  value       = huaweicloud_rds_instance.${sanitizeName(comp.name)}.id
}`);

    outputs.push(`output "rds_${sanitizeName(comp.name)}_private_ips" {
  description = "RDS private IPs for ${comp.name}"
  value       = huaweicloud_rds_instance.${sanitizeName(comp.name)}.private_ips
}`);
  }

  const obsComps = components.filter(c => c.service === "obs");
  for (const comp of obsComps) {
    outputs.push(`output "obs_${sanitizeName(comp.name)}_bucket" {
  description = "OBS bucket name for ${comp.name}"
  value       = huaweicloud_obs_bucket.${sanitizeName(comp.name)}.bucket
}`);
  }

  if (outputs.length === 0) {
    outputs.push(`# No outputs generated for this architecture`);
  }

  return outputs.join("\n\n");
}

export function generateTerraform(architecture) {
  const files = {};

  files["versions.tf"] = generateVersionsTf();
  files["providers.tf"] = generateProvidersTf(architecture.region);
  files["variables.tf"] = generateVariablesTf(architecture.components);
  files["main.tf"] = generateMainTf(architecture);
  files["outputs.tf"] = generateOutputsTf(architecture);
  files["terraform.tfvars.example"] = generateTfvarsExample(architecture);

  return files;
}

export { sanitizeName };
