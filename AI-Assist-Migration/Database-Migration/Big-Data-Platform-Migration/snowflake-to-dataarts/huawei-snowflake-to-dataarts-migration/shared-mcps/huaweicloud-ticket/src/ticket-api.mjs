import { readFile, writeFile, mkdir } from "node:fs/promises";
import { join } from "node:path";
import { homedir } from "node:os";
import axios from "axios";

const SESSION_DIR = join(homedir(), ".ticket-mcp");
const SESSION_FILE = join(SESSION_DIR, "session.json");
const CONSOLE_BASE = "https://console-intl.huaweicloud.com";
const API_BASE = `${CONSOLE_BASE}/ticket/rest/v2/servicerequest`;

async function ensureDir() {
  try { await mkdir(SESSION_DIR, { recursive: true }); } catch {}
}

export async function loadSession() {
  try {
    const raw = await readFile(SESSION_FILE, "utf-8");
    const session = JSON.parse(raw);
    if (session.cftk && session.cookies && Date.now() < session.expiresAt) {
      return session;
    }
    return null;
  } catch {
    return null;
  }
}

export async function saveSession(session) {
  await ensureDir();
  const data = {
    ...session,
    savedAt: Date.now(),
    expiresAt: session.expiresAt || Date.now() + 8 * 60 * 60 * 1000
  };
  await writeFile(SESSION_FILE, JSON.stringify(data, null, 2), "utf-8");
  return data;
}

export function isSessionValid(session) {
  return session && session.cftk && session.cookies && Date.now() < session.expiresAt;
}

function buildHeaders(session, extra = {}) {
  return {
    "content-type": "application/json; charset=UTF-8",
    "accept": "application/json, text/plain, */*",
    "cftk": session.cftk,
    "agencyid": session.agencyId || "",
    "x-language": "en-us",
    "x-requested-with": "XMLHttpRequest",
    "endpoint-scope": "global",
    "region": session.region || "cn-east-5",
    "projectname": session.region || "cn-east-5",
    "version": "1",
    "x-site": "1",
    "x-time-zone": "GMT",
    "cf2-cftk": "",
    cookie: session.cookies,
    ...extra
  };
}

async function apiCall(session, method, path, data = null, params = null) {
  const url = `${API_BASE}${path}`;
  const headers = buildHeaders(session);
  const config = { method, url, headers, maxRedirects: 0, validateStatus: () => true };
  if (data) config.data = data;
  if (params) config.params = params;

  const resp = await axios(config);

  if (resp.status === 401 || resp.status === 403) {
    const err = new Error("Session expired or unauthorized. Re-authentication required.");
    err.code = "SESSION_EXPIRED";
    throw err;
  }

  if (resp.status >= 400) {
    throw new Error(`API error ${resp.status}: ${JSON.stringify(resp.data).substring(0, 500)}`);
  }

  return resp.data;
}

export async function listServiceCategories(session) {
  const data = await apiCall(session, "GET", "/config/categories");
  const categories = [];
  if (data.incident_sub_type_list) {
    for (const subType of data.incident_sub_type_list) {
      for (const cat of subType.incident_product_category_list || []) {
        categories.push({
          id: cat.incident_product_category_id,
          name: cat.incident_product_category_name,
          acronym: cat.incident_product_category_acronym || "",
          description: cat.incident_product_category_desc || "",
          sub_type_id: subType.incident_sub_type_id,
          sub_type_name: subType.incident_sub_type_name,
          can_use_support_plan: cat.can_use_support_plan
        });
      }
    }
  }
  return { total: categories.length, categories };
}

export async function listIssueCategories(session, productCategoryId) {
  const data = await apiCall(session, "GET", `/config/problems`, null, { product_category_id: productCategoryId });
  const categories = (data.incident_business_type_list || []).map(bt => ({
    id: bt.business_type_id,
    name: bt.business_type_name,
    case_type: bt.case_type,
    can_use_support_plan: bt.can_use_support_plan
  }));
  return { total: data.count || categories.length, categories };
}

export async function getTicketFormSchema(session, productCategoryId, businessTypeId, incidentSubTypeId = "-1") {
  const data = await apiCall(session, "GET", `/config/extends-map`, null, {
    product_category_id: productCategoryId,
    business_type_id: businessTypeId,
    incident_sub_type_id: incidentSubTypeId
  });

  const extendsParams = (data.extends_params || []).map(f => {
    const field = {
      key: f.param_key,
      name: f.param_name,
      type: f.param_type,
      required: f.required === 1,
      tips: f.tips || "",
      length: f.length
    };
    if (f.param_subtype) {
      field.subtype = f.param_subtype;
      field.subtype_value = f.param_subtype_value;
    }
    if (f.select_item) {
      try {
        field.options = JSON.parse(f.select_item);
      } catch {
        field.options_raw = f.select_item;
      }
    }
    if (f.default_value) field.default_value = f.default_value;
    return field;
  });

  const commonParams = (data.common_params || []).map(f => ({
    key: f.param_key,
    name: f.param_name,
    show: f.is_show === 1,
    required: f.is_required === 1
  }));

  return { extends_params: extendsParams, common_params: commonParams };
}

export async function listRegions(session) {
  const data = await apiCall(session, "GET", "/config/regions");
  const regions = (data.data_center_list || [])
    .filter(r => r.region_status === "Running" && r.type === 0)
    .map(r => ({ id: r.region_id, name: r.region_name }));
  return { total: regions.length, regions };
}

export async function listSeverities(session, productCategoryId, businessTypeId) {
  const data = await apiCall(session, "GET", `/config/severities`, null, {
    product_category_id: productCategoryId,
    business_type_id: businessTypeId
  });
  return {
    show: data.show,
    severities: (data.severity_list || []).map(s => ({ id: s.severity_id, name: s.severity_name }))
  };
}

export async function checkCreatePrivilege(session) {
  const data = await apiCall(session, "GET", "/privileges", null, { privilege: "createCase" });
  return data;
}

export async function getSignedAgreement(session) {
  const data = await apiCall(session, "GET", "/agreements/signed-latest", null, { agreement_type: "0" });
  return data;
}

export async function createTicket(session, payload) {
  const data = await apiCall(session, "POST", "/cases", payload);
  return data;
}

export async function listTickets(session, offset = 0, limit = 10) {
  const data = await apiCall(session, "GET", "/cases", null, {
    offset,
    limit,
    trim_osm_rich_text_label: "false"
  });
  return {
    total: data.total_count,
    count: data.count,
    tickets: (data.incident_info_list || []).map(t => ({
      id: t.incident_id,
      number: t.incident_number,
      title: t.simple_description?.substring(0, 100),
      status: t.incident_status,
      created: t.create_time
    }))
  };
}

export async function getGlobalToken(session) {
  const headers = buildHeaders(session);
  const resp = await axios.get(`${CONSOLE_BASE}/ticket/rest/global/token`, { headers, validateStatus: () => true });
  return resp.data;
}

export { apiCall, buildHeaders, CONSOLE_BASE, API_BASE };
