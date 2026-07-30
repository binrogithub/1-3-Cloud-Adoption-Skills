import fs from "fs";

const TEMPLATES_FILE = "/root/.config/maas-pricing/pricing-templates.json";

export function loadTemplates() {
  if (!fs.existsSync(TEMPLATES_FILE)) {
    throw new Error(`Pricing templates file not found: ${TEMPLATES_FILE}`);
  }

  return JSON.parse(fs.readFileSync(TEMPLATES_FILE, "utf8"));
}

function hasReadyProductInfoTemplate(template) {
  return (
    Array.isArray(template.product_infos_template) &&
    template.product_infos_template.length > 0 &&
    template.status === "ready"
  );
}

export function listPricingTemplates(args = {}) {
  const data = loadTemplates();
  const serviceFilter = args.service;
  const regionFilter = args.region || data.default_region;

  const result = {
    tool: "ListPricingTemplates",
    version: data.version,
    currency: data.currency,
    default_region: data.default_region,
    filters: {
      service: serviceFilter || "all",
      region: regionFilter || "all"
    },
    templates: []
  };

  for (const [service, regions] of Object.entries(data.templates || {})) {
    if (serviceFilter && service !== serviceFilter) continue;

    for (const [region, templates] of Object.entries(regions || {})) {
      if (regionFilter && region !== regionFilter) continue;

      for (const [template_id, template] of Object.entries(templates || {})) {
        result.templates.push({
          template_id,
          service,
          region,
          display_name: template.display_name,
          billing_mode: template.billing_mode,
          unit: template.unit,
          status: template.status,
          parameters: template.parameters || {},
          parameter_names: Object.keys(template.parameters || {}),
          has_product_infos_template: Array.isArray(template.product_infos_template) && template.product_infos_template.length > 0,
          ready_for_real_pricing: hasReadyProductInfoTemplate(template),
          description: template.description
        });
      }
    }
  }

  result.count = result.templates.length;
  return result;
}

export function explainRequiredTemplate(args = {}) {
  const service = args.service || null;
  const region = args.region || null;

  return {
    tool: "ExplainRequiredTemplate",
    purpose: "Explain how to create or complete a parametric pricing template for Huawei Cloud cost estimation.",
    requested_service: service,
    requested_region: region,
    required_template_fields: [
      "service",
      "region",
      "display_name",
      "billing_mode",
      "unit",
      "description",
      "parameters",
      "product_infos_template",
      "status"
    ],
    parameter_examples: {
      evs: ["quantity", "size_gb"],
      eip: ["quantity", "bandwidth_mbps"],
      obs: ["quantity", "storage_gb"],
      ecs: ["quantity", "monthly_hours", "system_disk_gb"],
      rds: ["quantity", "monthly_hours", "storage_gb"]
    },
    product_infos_template_guidance: {
      why_needed: "Huawei Cloud pricing APIs require product_infos with product/resource/spec/usage identifiers. The MCP will later fill variable values such as size_gb or bandwidth_mbps into the product_infos_template.",
      how_to_get: [
        "Use Huawei Cloud Price Calculator to configure the target resource.",
        "Use API Explorer or an approved internal method to capture the pricing request payload.",
        "Extract the product_infos array.",
        "Convert fixed values such as disk size or bandwidth into placeholders where needed.",
        "Paste the result into product_infos_template.",
        "Change template status to ready."
      ],
      placeholder_examples: [
        "{{quantity}}",
        "{{size_gb}}",
        "{{bandwidth_mbps}}",
        "{{storage_gb}}",
        "{{monthly_hours}}"
      ]
    },
    safety: {
      creates_resources: false,
      modifies_resources: false,
      deletes_resources: false,
      purchases_resources: false
    }
  };
}

export function normalizeArchitectureComponents(args = {}) {
  const inputComponents = Array.isArray(args.components) ? args.components : [];

  const components = [];
  const normalizationNotes = [];

  for (const component of inputComponents) {
    const service = component.service;
    const templateId = component.template_id;
    const parameters = component.parameters || {};

    if (service === "rds" && templateId === "rds-mysql-small-payg") {
      const quantity = component.quantity || 1;
      const monthlyHours = parameters.monthly_hours ?? component.monthly_hours ?? 730;

      components.push({
        service: "rds",
        template_id: "rds-mysql-instance-payg",
        quantity,
        parameters: {
          instance_resource_spec: parameters.instance_resource_spec ?? parameters.resource_spec ?? "rds.mysql.n1.large.2",
          monthly_hours: monthlyHours
        }
      });

      components.push({
        service: "rds",
        template_id: "rds-mysql-volume-payg",
        quantity,
        parameters: {
          storage_resource_spec: parameters.storage_resource_spec ?? "rds.mysql.volume.cloudssd",
          storage_gb: parameters.storage_gb ?? component.storage_gb ?? 100,
          monthly_hours: monthlyHours
        }
      });

      normalizationNotes.push({
        original_service: service,
        original_template_id: templateId,
        action: "expanded_rds_mysql_small_into_instance_and_volume",
        replacement_templates: [
          "rds-mysql-instance-payg",
          "rds-mysql-volume-payg"
        ],
        reason: "RDS pricing is modeled as separate instance compute and storage volume components."
      });

      continue;
    }

    if (service === "cce" && templateId === "cce-standard-cluster-payg") {
      const clusterType = parameters.cluster_type ?? "standard";
      const clusterScale = parameters.cluster_scale ?? "cce.s1.small";
      const nodeCount = parameters.node_count ?? 1;
      const nodeTemplateId = parameters.node_template_id ?? "ecs-linux-2vcpu-4gb-payg";
      const nodeSystemDiskSizeGb = parameters.node_system_disk_size_gb ?? 40;
      const nodeDataDiskSizeGb = parameters.node_data_disk_size_gb ?? null;
      const publicIngress = parameters.public_ingress === true;
      const ingressBandwidthMbps = parameters.ingress_bandwidth_mbps ?? 20;
      const monthlyHours = parameters.monthly_hours ?? component.monthly_hours ?? 730;

      if (clusterType === "turbo") {
        components.push({
          service: "cce",
          template_id: "cce-standard-cluster-payg",
          quantity: component.quantity || 1,
          parameters: {
            ...parameters,
            _cce_turbo_unsupported: true
          }
        });

        normalizationNotes.push({
          original_service: service,
          original_template_id: templateId,
          action: "cce_turbo_unsupported_phase1",
          reason: "CCE Turbo pricing is not supported in Phase 1. Component kept with _cce_turbo_unsupported flag. No resource_spec invented."
        });

        continue;
      }

      components.push({
        service: "cce",
        template_id: "cce-cluster-mgmt-payg",
        quantity: 1,
        parameters: {
          resource_spec: clusterScale,
          monthly_hours: monthlyHours
        }
      });

      for (let n = 0; n < nodeCount; n++) {
        components.push({
          service: "ecs",
          template_id: nodeTemplateId,
          quantity: 1,
          parameters: {
            monthly_hours: monthlyHours,
            system_disk_gb: nodeSystemDiskSizeGb
          }
        });
      }

      for (let n = 0; n < nodeCount; n++) {
        components.push({
          service: "evs",
          template_id: "evs-ssd-gb-payg",
          quantity: 1,
          parameters: {
            size_gb: nodeSystemDiskSizeGb,
            monthly_hours: monthlyHours
          }
        });
      }

      if (nodeDataDiskSizeGb !== null && nodeDataDiskSizeGb > 0) {
        for (let n = 0; n < nodeCount; n++) {
          components.push({
            service: "evs",
            template_id: "evs-ssd-gb-payg",
            quantity: 1,
            parameters: {
              size_gb: nodeDataDiskSizeGb,
              monthly_hours: monthlyHours
            }
          });
        }
      }

      if (publicIngress) {
        components.push({
          service: "elb",
          template_id: "elb-shared-instance-payg",
          quantity: 1,
          parameters: {
            network_type: "public",
            bandwidth_mbps: ingressBandwidthMbps,
            monthly_hours: monthlyHours
          }
        });
      }

      const expandedTemplates = ["cce-cluster-mgmt-payg"];
      expandedTemplates.push(`${nodeCount}x ${nodeTemplateId}`);
      expandedTemplates.push(`${nodeCount}x evs-ssd-gb-payg (system disk)`);
      if (nodeDataDiskSizeGb !== null && nodeDataDiskSizeGb > 0) {
        expandedTemplates.push(`${nodeCount}x evs-ssd-gb-payg (data disk)`);
      }
      if (publicIngress) {
        expandedTemplates.push("elb-shared-instance-payg (public ingress)");
      }

      normalizationNotes.push({
        original_service: service,
        original_template_id: templateId,
        action: "expanded_cce_standard_cluster",
        replacement_templates: expandedTemplates,
        reason: "CCE Standard cluster is modeled as: cluster management + worker ECS + system disks + optional data disks + optional public ingress ELB."
      });

      continue;
    }

    components.push(component);
  }

  const publicElbComponents = components.filter((component) => {
    const parameters = component.parameters || {};
    const networkType = parameters.network_type ?? component.network_type ?? null;
    const hasBandwidthHint =
      parameters.bandwidth_mbps !== undefined ||
      component.bandwidth_mbps !== undefined ||
      parameters.public_bandwidth_mbps !== undefined ||
      component.public_bandwidth_mbps !== undefined;

    return (
      component.service === "elb" &&
      component.template_id === "elb-shared-instance-payg" &&
      (networkType === "public" || hasBandwidthHint)
    );
  });

  const hasEipBandwidthComponent = components.some((component) =>
    component.service === "eip" &&
    component.template_id === "eip-bandwidth-mbps-payg"
  );

  if (publicElbComponents.length > 0 && !hasEipBandwidthComponent) {
    const sourceElb = publicElbComponents[0];
    const parameters = sourceElb.parameters || {};
    const monthlyHours = parameters.monthly_hours ?? sourceElb.monthly_hours ?? 730;

    components.push({
      service: "eip",
      template_id: "eip-bandwidth-mbps-payg",
      quantity: parameters.eip_quantity ?? 1,
      parameters: {
        bandwidth_mbps: parameters.bandwidth_mbps ?? parameters.public_bandwidth_mbps ?? sourceElb.bandwidth_mbps ?? sourceElb.public_bandwidth_mbps ?? 20,
        monthly_hours: monthlyHours
      }
    });

    normalizationNotes.push({
      original_service: "elb",
      original_template_id: "elb-shared-instance-payg",
      action: "added_eip_bandwidth_for_public_elb",
      added_template: "eip-bandwidth-mbps-payg",
      reason: "Public ELB exposure requires public bandwidth/EIP pricing. ELB v3 instance is a paid component and does not include bandwidth.",
      defaults_used_if_missing: {
        bandwidth_mbps: 20,
        monthly_hours: monthlyHours
      }
    });
  }

  return {
    components,
    normalization: {
      original_components_count: inputComponents.length,
      normalized_components_count: components.length,
      notes: normalizationNotes
    }
  };
}

export function estimateArchitectureCostDraft(args = {}) {
  const data = loadTemplates();
  const region = args.region || data.default_region;
  const normalized = normalizeArchitectureComponents(args);
  const components = normalized.components;

  const result = {
    tool: "EstimateArchitectureCostDraft",
    status: "DRAFT_ONLY",
    message: "This draft maps architecture components to parametric local pricing templates. It does not call Huawei Cloud pricing APIs yet.",
    region,
    currency: data.currency,
    components: [],
    missing_templates: [],
    incomplete_templates: [],
    ready_templates: [],
    next_step: "Complete product_infos_template for each template, then use real pricing tools."
  };

  for (const component of components) {
    const service = component.service;
    const templateId = component.template_id;
    const quantity = component.quantity || 1;
    const inputParameters = component.parameters || {};

    const template = data.templates?.[service]?.[region]?.[templateId];

    if (!template) {
      const missing = {
        service,
        region,
        template_id: templateId,
        quantity,
        reason: "Template not found"
      };

      result.components.push({ ...missing, status: "MISSING_TEMPLATE" });
      result.missing_templates.push(missing);
      continue;
    }

    const declaredParameters = template.parameters || {};
    const resolvedParameters = {};

    for (const [paramName, paramDef] of Object.entries(declaredParameters)) {
      if (inputParameters[paramName] !== undefined) {
        resolvedParameters[paramName] = inputParameters[paramName];
      } else if (component[paramName] !== undefined) {
        resolvedParameters[paramName] = component[paramName];
      } else if (paramName === "quantity") {
        resolvedParameters[paramName] = quantity;
      } else if (paramDef.default !== undefined) {
        resolvedParameters[paramName] = paramDef.default;
      } else {
        resolvedParameters[paramName] = null;
      }
    }

    const missingRequiredParameters = Object.entries(declaredParameters)
      .filter(([paramName, paramDef]) => paramDef.required && (resolvedParameters[paramName] === null || resolvedParameters[paramName] === undefined))
      .map(([paramName]) => paramName);

    const readyForPricing = hasReadyProductInfoTemplate(template) && missingRequiredParameters.length === 0;

    const item = {
      service,
      region,
      template_id: templateId,
      display_name: template.display_name,
      billing_mode: template.billing_mode,
      unit: template.unit,
      quantity,
      template_status: template.status,
      declared_parameters: declaredParameters,
      resolved_parameters: resolvedParameters,
      missing_required_parameters: missingRequiredParameters,
      has_product_infos_template: Array.isArray(template.product_infos_template) && template.product_infos_template.length > 0,
      ready_for_real_pricing: readyForPricing
    };

    result.components.push(item);

    if (readyForPricing) {
      result.ready_templates.push(item);
    } else {
      result.incomplete_templates.push({
        service,
        region,
        template_id: templateId,
        quantity,
        reason: "product_infos_template missing, status is not ready, or required parameters are missing",
        missing_required_parameters: missingRequiredParameters,
        current_status: template.status
      });
    }
  }

  result.normalization = normalized.normalization;

  result.summary = {
    requested_components: normalized.normalization.original_components_count,
    normalized_components: normalized.normalization.normalized_components_count,
    ready_for_real_pricing: result.ready_templates.length,
    missing_templates: result.missing_templates.length,
    incomplete_templates: result.incomplete_templates.length
  };

  return result;
}

function replacePlaceholders(value, params) {
  if (typeof value === "string") {
    const exact = value.match(/^\{\{([a-zA-Z0-9_]+)\}\}$/);
    if (exact) {
      const key = exact[1];
      return params[key] !== undefined ? params[key] : value;
    }

    return value.replace(/\{\{([a-zA-Z0-9_]+)\}\}/g, (_, key) => {
      return params[key] !== undefined ? String(params[key]) : `{{${key}}}`;
    });
  }

  if (Array.isArray(value)) {
    return value.map((item) => replacePlaceholders(item, params));
  }

  if (value && typeof value === "object") {
    const out = {};
    for (const [k, v] of Object.entries(value)) {
      out[k] = replacePlaceholders(v, params);
    }
    return out;
  }

  return value;
}

export function renderProductInfosFromTemplate(args = {}) {
  const data = loadTemplates();

  const region = args.region || data.default_region;
  const service = args.service;
  const templateId = args.template_id;
  const quantity = args.quantity || 1;
  const inputParameters = args.parameters || {};

  if (!service) {
    throw new Error("service is required");
  }

  if (!templateId) {
    throw new Error("template_id is required");
  }

  const template = data.templates?.[service]?.[region]?.[templateId];

  if (!template) {
    throw new Error(`Template not found: service=${service}, region=${region}, template_id=${templateId}`);
  }

  const declaredParameters = template.parameters || {};

  /*
    Base parameters are always available to product_infos_template placeholders.
    This allows placeholders such as:
    - {{region}}
    - {{service}}
    - {{template_id}}
    - {{quantity}}
  */
  const resolvedParameters = {
    region,
    service,
    template_id: templateId,
    quantity,
    ...inputParameters
  };

  for (const [paramName, paramDef] of Object.entries(declaredParameters)) {
    if (resolvedParameters[paramName] !== undefined) {
      continue;
    } else if (paramName === "quantity") {
      resolvedParameters[paramName] = quantity;
    } else if (paramDef.default !== undefined) {
      resolvedParameters[paramName] = paramDef.default;
    } else {
      resolvedParameters[paramName] = null;
    }
  }

  const missingRequiredParameters = Object.entries(declaredParameters)
    .filter(([paramName, paramDef]) => paramDef.required && (resolvedParameters[paramName] === null || resolvedParameters[paramName] === undefined))
    .map(([paramName]) => paramName);

  const productInfosTemplate = template.product_infos_template || [];

  if (!Array.isArray(productInfosTemplate) || productInfosTemplate.length === 0) {
    return {
      tool: "RenderProductInfosFromTemplate",
      status: "MISSING_PRODUCT_INFOS_TEMPLATE",
      message: "The template exists and parameters were resolved, but product_infos_template is empty. Capture product_infos from Huawei Cloud Price Calculator/API Explorer and add it to the template.",
      service,
      region,
      template_id: templateId,
      display_name: template.display_name,
      billing_mode: template.billing_mode,
      unit: template.unit,
      resolved_parameters: resolvedParameters,
      missing_required_parameters: missingRequiredParameters,
      product_infos: []
    };
  }

  if (missingRequiredParameters.length > 0) {
    return {
      tool: "RenderProductInfosFromTemplate",
      status: "MISSING_REQUIRED_PARAMETERS",
      service,
      region,
      template_id: templateId,
      resolved_parameters: resolvedParameters,
      missing_required_parameters: missingRequiredParameters,
      product_infos: []
    };
  }

  const productInfos = replacePlaceholders(productInfosTemplate, resolvedParameters);

  return {
    tool: "RenderProductInfosFromTemplate",
    status: "OK",
    service,
    region,
    template_id: templateId,
    display_name: template.display_name,
    billing_mode: template.billing_mode,
    unit: template.unit,
    resolved_parameters: resolvedParameters,
    product_infos: productInfos
  };
}
