import supportedServicesConfig from "./config/supported-services.json" with { type: "json" };

const SUPPORTED = new Set(supportedServicesConfig.supported_services);
const PHASE1 = new Set(supportedServicesConfig.phase1_services);
const PHASE2 = new Set(supportedServicesConfig.phase2_services);
const SENSITIVE_PATTERNS = [
  "access_key", "secret_key", "password", "token", "credential",
  "HW_ACCESS_KEY", "HW_SECRET_KEY", "OS_ACCESS_KEY", "OS_SECRET_KEY"
];

const REQUIRED_ARCH_FIELDS = ["architecture_id", "region", "deployment_mode", "components"];

const SERVICE_SCHEMAS = {
  vpc: {
    required: ["name", "cidr"],
    optional: []
  },
  subnet: {
    required: ["name", "cidr"],
    optional: ["gateway_ip"]
  },
  security_group: {
    required: ["name"],
    optional: ["rules"]
  },
  ecs: {
    required: ["name", "flavor", "image_name", "system_disk_type", "system_disk_size_gb"],
    optional: ["quantity"]
  },
  elb: {
    required: ["name", "type"],
    optional: ["listener_port", "backend_port"]
  },
  eip: {
    required: ["name"],
    optional: ["bandwidth_mbps"]
  },
  elb_backend_attachment: {
    required: ["name", "elb_name"],
    optional: ["backend_port"]
  },
  rds_mysql: {
    required: ["name", "flavor", "storage_type", "storage_gb"],
    optional: ["engine", "engine_version", "availability_zone", "db_port", "database_name", "username", "ha_mode"]
  },
  obs: {
    required: ["name"],
    optional: ["bucket_name", "storage_class", "acl"]
  }
};

function containsSecret(value) {
  if (typeof value !== "string") return false;
  const lower = value.toLowerCase();
  return SENSITIVE_PATTERNS.some(p => lower.includes(p.toLowerCase()));
}

function deepScanForSecrets(obj, path = "") {
  const findings = [];
  if (!obj || typeof obj !== "object") return findings;
  for (const [key, value] of Object.entries(obj)) {
    const currentPath = path ? `${path}.${key}` : key;
    if (containsSecret(key)) {
      findings.push({ path: currentPath, reason: "sensitive_key_name", key });
    }
    if (typeof value === "string" && containsSecret(value)) {
      findings.push({ path: currentPath, reason: "sensitive_value", key });
    }
    if (value && typeof value === "object") {
      findings.push(...deepScanForSecrets(value, currentPath));
    }
  }
  return findings;
}

export function validateArchitecture(input) {
  const errors = [];
  const warnings = [];
  const componentStatus = [];

  if (!input || typeof input !== "object") {
    return { valid: false, errors: ["Input must be a non-null object"], warnings: [], componentStatus: [] };
  }

  for (const field of REQUIRED_ARCH_FIELDS) {
    if (!input[field]) {
      errors.push(`Missing required field: ${field}`);
    }
  }

  if (input.deployment_mode && input.deployment_mode !== "terraform") {
    errors.push(`Unsupported deployment_mode: ${input.deployment_mode}. Only "terraform" is supported.`);
  }

  if (!Array.isArray(input.components) || input.components.length === 0) {
    errors.push("components must be a non-empty array");
    return { valid: false, errors, warnings, componentStatus };
  }

  const secretFindings = deepScanForSecrets(input);
  for (const finding of secretFindings) {
    errors.push(`Secret detected at ${finding.path}: ${finding.reason} (${finding.key})`);
  }

  const seenNames = new Set();
  for (const comp of input.components) {
    if (!comp.service) {
      errors.push(`Component missing "service" field: ${JSON.stringify(comp)}`);
      continue;
    }

    const service = comp.service;
    const name = comp.name || "(unnamed)";

    if (!SUPPORTED.has(service)) {
      componentStatus.push({ service, name, status: "UNSUPPORTED", message: `Service "${service}" is not supported` });
      continue;
    }

    if (!PHASE1.has(service) && !PHASE2.has(service)) {
      componentStatus.push({ service, name, status: "UNSUPPORTED", message: `Service "${service}" is not supported` });
      continue;
    }

    if (!PHASE1.has(service) && PHASE2.has(service)) {
      const schema = SERVICE_SCHEMAS[service];
      if (schema) {
        for (const reqField of schema.required) {
          if (comp[reqField] === undefined || comp[reqField] === null) {
            errors.push(`Component "${name}" (${service}) missing required field: ${reqField}`);
          }
        }
      }

      if (seenNames.has(name)) {
        errors.push(`Duplicate component name: "${name}"`);
      }
      seenNames.add(name);

      componentStatus.push({ service, name, status: "READY", message: "OK (phase 2)" });
      continue;
    }

    const schema = SERVICE_SCHEMAS[service];
    if (schema) {
      for (const reqField of schema.required) {
        if (comp[reqField] === undefined || comp[reqField] === null) {
          errors.push(`Component "${name}" (${service}) missing required field: ${reqField}`);
        }
      }
    }

    if (seenNames.has(name)) {
      errors.push(`Duplicate component name: "${name}"`);
    }
    seenNames.add(name);

    componentStatus.push({ service, name, status: "READY", message: "OK" });
  }

  const vpcCount = input.components.filter(c => c.service === "vpc").length;
  if (vpcCount === 0) warnings.push("No VPC defined - ECS and other resources require a VPC");
  if (vpcCount > 1) warnings.push("Multiple VPCs defined - cross-VPC references are not auto-generated");

  const subnetCount = input.components.filter(c => c.service === "subnet").length;
  if (subnetCount === 0 && vpcCount > 0) warnings.push("VPC defined but no subnet");

  return {
    valid: errors.length === 0,
    errors,
    warnings,
    componentStatus
  };
}

export { SUPPORTED, PHASE1, PHASE2, SENSITIVE_PATTERNS, SERVICE_SCHEMAS };
