# WAF Discovery Report for huaweicloud-pricing MCP

**Date**: 2026-05-29
**Region**: la-north-2
**Status**: Instance resource_spec CONFIRMED (professional + enterprise). Pay-per-use domain/rule/request PENDING.

---

## 1. BSS/OCE Catalog Summary

### cloud_service_type
- **Code**: `hws.service.type.waf`
- **Name**: Web Application Firewall

### Resource Types (16 total)

| # | resource_type_code | Name | Usage Type | On-Demand |
|---|---|---|---|---|
| 1 | `hws.resource.type.waf` | Web Application Firewall | (none) | Unknown |
| 2 | `hws.resource.type.waf.instance` | Web Application Firewall Instance | `duration` | **CONFIRMED** |
| 3 | `hws.resource.type.waf.domain` | Web Application Firewall Host Expansion Package | `count` | Pending |
| 4 | `hws.resource.type.waf.rule` | Web Application Firewall Rule Expansion Package | (none) | Pending |
| 5 | `hws.resource.type.waf.request` | Web Application Firewall Request | `count` | Pending |
| 6 | `hws.resource.type.waf.bandwidth` | Web Application Firewall Bandwidth Expansion Package | (none) | Pending |
| 7 | `hws.resource.type.waf.service` | Web Application Firewall Service Expansion Package | (none) | Pending |
| 8 | `hws.resource.type.waf.customization` | Web Application Firewall Customization Expansion Package | (none) | Pending |
| 9 | `hws.resource.type.waf.delicatedengine` | Web Application Firewall Delicated Engine | (none) | Pending |
| 10 | `hws.resource.type.waf.payperusedomain` | Web Application Firewall Payperuse Domain | `count` | Pending |
| 11 | `hws.resource.type.waf.payperuserule` | Web Application Firewall Payperuse Rule | `count` | Pending |
| 12 | `hws.resource.type.waf.payperuserequest` | Web Application Firewall Payperuse Request | `count` | Pending |
| 13 | `hws.resource.type.waf.contentsecurity` | Content moderation checks | (none) | Pending |
| 14 | `hws.resource.type.waf.urldetection` | Url Detection | (none) | Pending |
| 15 | `hws.resource.type.urldetection.expansion` | Url Detection Expansion Package | (none) | Pending |
| 16 | `hws.resource.type.security.fullstackdec` | fullstackdec | (none) | Pending |

### Usage Types (confirmed per resource type)

| resource_type_code | usage_type code | usage_type name |
|---|---|---|
| `hws.resource.type.waf.instance` | `duration` | Duration |
| `hws.resource.type.waf.domain` | `count` | count |
| `hws.resource.type.waf.request` | `count` | count |
| `hws.resource.type.waf.payperusedomain` | `count` | count |
| `hws.resource.type.waf.payperuserule` | `count` | count |
| `hws.resource.type.waf.payperuserequest` | `count` | count |

Resource types with **no usage types**: `hws.resource.type.waf`, `hws.resource.type.waf.rule`, `hws.resource.type.waf.bandwidth`, `hws.resource.type.waf.service`, `hws.resource.type.waf.customization`, `hws.resource.type.waf.delicatedengine`.

---

## 2. Billing Models Identified

### A. WAF Dedicated Instance (Yearly/Monthly + Pay-per-use)
- **resource_type**: `hws.resource.type.waf.instance`
- **usage_type**: `duration`
- **resource_spec CONFIRMED**:
  - `waf.instance.professional` → USD 576.70/month (730h)
  - `waf.instance.enterprise` → USD 1,365.10/month (730h)
- **resource_spec NOT FOUND**:
  - `waf.instance` (base)
  - `waf.instance.platinum`

### B. WAF Cloud / Pay-per-use Domain
- **resource_type**: `hws.resource.type.waf.payperusedomain`
- **usage_type**: `count`
- **resource_spec**: NOT FOUND (all variants tested returned "Product not found")

### C. WAF Cloud / Pay-per-use Rule
- **resource_type**: `hws.resource.type.waf.payperuserule`
- **usage_type**: `count`
- **resource_spec**: NOT FOUND (all variants tested returned "Product not found")

### D. WAF Cloud / Pay-per-use Request
- **resource_type**: `hws.resource.type.waf.payperuserequest`
- **usage_type**: `count`
- **resource_spec**: NOT FOUND (all variants tested returned "Product not found")

### E. WAF Domain Expansion Package (subscription add-on)
- **resource_type**: `hws.resource.type.waf.domain`
- **usage_type**: `count`
- **resource_spec**: NOT FOUND (all variants tested returned "Product not found")

### F. WAF Rule Expansion Package
- **resource_type**: `hws.resource.type.waf.rule`
- **usage_type**: (none in catalog)
- **resource_spec**: NOT FOUND

### G. WAF Bandwidth Expansion Package
- **resource_type**: `hws.resource.type.waf.bandwidth`
- **usage_type**: (none in catalog)
- **resource_spec**: NOT FOUND (CBC.6074: "The billing item does not exist")

### H. WAF Service Expansion Package
- **resource_type**: `hws.resource.type.waf.service`
- **usage_type**: (none in catalog)
- **resource_spec**: NOT FOUND (CBC.6074: "The billing item does not exist")

### I. WAF Customization Expansion Package
- **resource_type**: `hws.resource.type.waf.customization`
- **usage_type**: (none in catalog)
- **resource_spec**: NOT FOUND (CBC.6074: "The billing item does not exist")

### J. WAF Dedicated Engine
- **resource_type**: `hws.resource.type.waf.delicatedengine`
- **usage_type**: (none in catalog)
- **resource_spec**: NOT FOUND (CBC.6074: "The billing item does not exist")

---

## 3. resource_spec Search Results

### 3.1 WAF Instance (CONFIRMED)

| resource_spec | resource_type | Result | Price (USD/month) |
|---|---|---|---|
| `waf.instance` | `hws.resource.type.waf.instance` | Product not found | - |
| `waf.instance.professional` | `hws.resource.type.waf.instance` | **SUCCESS** | **576.70** |
| `waf.instance.enterprise` | `hws.resource.type.waf.instance` | **SUCCESS** | **1,365.10** |
| `waf.instance.platinum` | `hws.resource.type.waf.instance` | Product not found | - |

### 3.2 WAF Pay-per-use Domain (NOT FOUND)

| resource_spec | resource_type | Result |
|---|---|---|
| `waf.payperusedomain` | `hws.resource.type.waf.payperusedomain` | Product not found |
| `waf.cloud.domain` | `hws.resource.type.waf.payperusedomain` | Product not found |
| `waf.postpaid.domain` | `hws.resource.type.waf.payperusedomain` | Product not found |
| `waf.instance.professional.domain` | `hws.resource.type.waf.payperusedomain` | Product not found |
| `waf.instance.professional.payperusedomain` | `hws.resource.type.waf.payperusedomain` | Product not found |
| `waf.instance.professional.extend.domain` | `hws.resource.type.waf.payperusedomain` | Product not found |
| `waf.instance.cloud.domain` | `hws.resource.type.waf.payperusedomain` | Product not found |

### 3.3 WAF Pay-per-use Rule (NOT FOUND)

| resource_spec | resource_type | Result |
|---|---|---|
| `waf.payperuserule` | `hws.resource.type.waf.payperuserule` | Product not found |
| `waf.cloud.rule` | `hws.resource.type.waf.payperuserule` | Product not found |
| `waf.postpaid.rule` | `hws.resource.type.waf.payperuserule` | Product not found |
| `waf.instance.professional.rule` | `hws.resource.type.waf.payperuserule` | Product not found |
| `waf.instance.professional.payperuserule` | `hws.resource.type.waf.payperuserule` | Product not found |
| `waf.instance.professional.extend.rule` | `hws.resource.type.waf.payperuserule` | Product not found |
| `waf.instance.cloud.rule` | `hws.resource.type.waf.payperuserule` | Product not found |

### 3.4 WAF Pay-per-use Request (NOT FOUND)

| resource_spec | resource_type | Result |
|---|---|---|
| `waf.payperuserequest` | `hws.resource.type.waf.payperuserequest` | Product not found |
| `waf.cloud.request` | `hws.resource.type.waf.payperuserequest` | Product not found |
| `waf.postpaid.request` | `hws.resource.type.waf.payperuserequest` | Product not found |
| `waf.instance.professional.request` | `hws.resource.type.waf.payperuserequest` | Product not found |
| `waf.instance.professional.payperuserequest` | `hws.resource.type.waf.payperuserequest` | Product not found |
| `waf.instance.professional.extend.request` | `hws.resource.type.waf.payperuserequest` | Product not found |
| `waf.instance.cloud.request` | `hws.resource.type.waf.payperuserequest` | Product not found |

### 3.5 WAF Domain Expansion Package (NOT FOUND)

| resource_spec | resource_type | Result |
|---|---|---|
| `waf.domain` | `hws.resource.type.waf.domain` | Product not found |
| `waf.instance.professional.domain` | `hws.resource.type.waf.domain` | Product not found |
| `waf.instance.enterprise.domain` | `hws.resource.type.waf.domain` | Product not found |
| `waf.instance.professional.host` | `hws.resource.type.waf.domain` | Product not found |

### 3.6 WAF Request (NOT FOUND)

| resource_spec | resource_type | Result |
|---|---|---|
| `waf.request` | `hws.resource.type.waf.request` | Product not found |
| `waf.instance.professional.request` | `hws.resource.type.waf.request` | Product not found |

### 3.7 Expansion Packages (CBC.6074: "The billing item does not exist")

| resource_spec | resource_type | Error |
|---|---|---|
| `waf.bandwidth` | `hws.resource.type.waf.bandwidth` | CBC.6074: Request usage type list fail |
| `waf.service` | `hws.resource.type.waf.service` | CBC.6074: Request usage type list fail |
| `waf.customization` | `hws.resource.type.waf.customization` | CBC.6074: Request usage type list fail |
| `waf.delicatedengine.professional` | `hws.resource.type.waf.delicatedengine` | CBC.6074: Request usage type list fail |
| `waf.professional` | `hws.resource.type.waf` | CBC.6074: Request usage type list fail |

The CBC.6074 error indicates these resource types exist in the catalog but have no on-demand billing items. They may be subscription-only or require different resource_spec values not discoverable via naming convention inference.

---

## 4. Confirmed product_infos

### 4.1 WAF Professional Instance

```json
{
  "id": "waf-instance-professional-{{monthly_hours}}h-{{quantity}}",
  "cloud_service_type": "hws.service.type.waf",
  "resource_type": "hws.resource.type.waf.instance",
  "resource_spec": "waf.instance.professional",
  "region": "{{region}}",
  "usage_factor": "Duration",
  "usage_value": "{{monthly_hours}}",
  "usage_measure_id": 4,
  "subscription_num": "{{quantity}}"
}
```

**Validated**: la-north-2, 730h → USD 576.70/month. product_id: OFFI841211620895129603.

### 4.2 WAF Enterprise Instance

```json
{
  "id": "waf-instance-enterprise-{{monthly_hours}}h-{{quantity}}",
  "cloud_service_type": "hws.service.type.waf",
  "resource_type": "hws.resource.type.waf.instance",
  "resource_spec": "waf.instance.enterprise",
  "region": "{{region}}",
  "usage_factor": "Duration",
  "usage_value": "{{monthly_hours}}",
  "usage_measure_id": 4,
  "subscription_num": "{{quantity}}"
}
```

**Validated**: la-north-2, 730h → USD 1,365.10/month. product_id: OFFI841211620895129602.

---

## 5. Validated Pricing

| resource_spec | Region | Hours | Monthly Price (USD) | product_id |
|---|---|---|---|---|
| `waf.instance.professional` | la-north-2 | 730 | **576.70** | OFFI841211620895129603 |
| `waf.instance.enterprise` | la-north-2 | 730 | **1,365.10** | OFFI841211620895129602 |

---

## 6. Errors Found

| Category | Error Code | Error Message | resource_types Affected |
|---|---|---|---|
| Product not found | CBC.6006 | Can not find product {spec} | waf.instance (base), waf.instance.platinum, all payperusedomain/rule/request variants, domain/request expansion variants |
| Billing item does not exist | CBC.6074 | Request usage type list fail | waf.bandwidth, waf.service, waf.customization, waf.delicatedengine, waf (base) |
| Missing region | CBC.0100 | region: must not be null | All (initial calls without region field) |
| Missing id | CBC.0100 | id: must not be null | All (initial calls without id field) |

---

## 7. Recommendation

### WAF Fase 1: IMPLEMENT (instance-only)

**Rationale**:
- Two resource_spec values confirmed for `hws.resource.type.waf.instance`:
  - `waf.instance.professional` → USD 576.70/month
  - `waf.instance.enterprise` → USD 1,365.10/month
- product_infos_template fully defined for both editions.
- usage_factor, usage_measure_id, and billing model confirmed via live BSS/OCE API.
- Instance-only template follows the same pattern as ECS, DDS instance, and DCS Redis instance.

**Proposed Templates**:
- `waf-instance-professional-payg`: Dedicated WAF professional edition, pay-per-use.
- `waf-instance-enterprise-payg`: Dedicated WAF enterprise edition, pay-per-use.

Or a single parametric template:
- `waf-instance-payg`: params {quantity, resource_spec (default: waf.instance.professional), monthly_hours}.

**Deferred** (blocked by missing resource_spec):
- `waf-payperusedomain-payg`: Cloud WAF domain count.
- `waf-payperuserule-payg`: Cloud WAF rule count.
- `waf-payperuserequest-payg`: Cloud WAF request count.
- `waf-domain-expansion-payg`: Domain expansion package for dedicated instance.
- All expansion packages (bandwidth, service, customization).
- Dedicated engine.
- `service_cost_breakdown` for dedicated + cloud breakdown.

**Unblock Path**:
- Huawei Cloud Price Calculator export for WAF (https://support.huaweicloud.com/intl/en-us/price-waf/waf_03_0001.html).
- Billing statement analysis from a live WAF deployment.
- API Explorer capture of product_infos from the Price Calculator UI.

---

## 8. Files Modified

- **Created**: `docs/waf-discovery.md` (this file)
- **Updated**: `docs/service-expansion-analysis.md` (WAF section updated with confirmed instance resource_spec)
