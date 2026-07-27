const fs = require("fs");
const path = require("path");

const V1_FILE = path.resolve(__dirname, "..", "out", "dataarts_create_job_request.v1.dryrun.json");

const SECRET_KEYS = new Set(["huawei_ak", "huawei_sk", "ak", "sk", "access_key", "secret_key", "password", "token"]);

const PLACEHOLDER_PATTERNS = [
  /^REPLACE_ME$/i,
  /^your_.*_here$/i,
  /^changeme$/i,
  /^placeholder$/i,
];

function findSecrets(obj, path) {
  const findings = [];
  if (!obj || typeof obj !== "object") return findings;
  for (const [k, v] of Object.entries(obj)) {
    const p = path ? `${path}.${k}` : k;
    if (SECRET_KEYS.has(k.toLowerCase())) {
      findings.push(p);
    }
    if (typeof v === "object" && v !== null) {
      findings.push(...findSecrets(v, p));
    }
  }
  return findings;
}

function findPlaceholders(obj, path) {
  const findings = [];
  if (!obj || typeof obj !== "object") return findings;
  for (const [k, v] of Object.entries(obj)) {
    const p = path ? `${path}.${k}` : k;
    if (typeof v === "string" && PLACEHOLDER_PATTERNS.some((pat) => pat.test(v))) {
      findings.push(`${p}=${v}`);
    }
    if (typeof v === "object" && v !== null) {
      findings.push(...findPlaceholders(v, p));
    }
  }
  return findings;
}

function main() {
  console.log("=== DataArts Deploy Agent: Payload Audit ===\n");

  if (!fs.existsSync(V1_FILE)) {
    console.log("FAIL: Missing file: " + V1_FILE);
    console.log("Run `npm run dry-run` first.");
    process.exit(1);
  }

  let request;
  try {
    request = JSON.parse(fs.readFileSync(V1_FILE, "utf-8"));
  } catch (e) {
    console.log("FAIL: Invalid JSON in v1 request file");
    process.exit(1);
  }

  const checks = [];

  const body = request.body;
  checks.push({ name: "body exists", pass: !!body, detail: body ? "OK" : "missing" });

  if (!body) {
    for (const c of checks) {
      const status = c.pass ? "PASS" : "FAIL";
      console.log(`  [${status}] ${c.name} (${c.detail})`);
    }
    console.log("");
    console.log("Overall: FAIL");
    process.exit(1);
  }

  checks.push({ name: "body.name exists", pass: !!body.name, detail: body.name || "null/missing" });
  checks.push({ name: "body.processType exists", pass: !!body.processType, detail: body.processType || "null/missing" });
  checks.push({ name: "body.schedule exists", pass: !!body.schedule, detail: body.schedule ? "OK" : "null/missing" });

  const nodeCount = Array.isArray(body.nodes) ? body.nodes.length : 0;
  checks.push({ name: "body.nodes length >= 3", pass: nodeCount >= 3, detail: `got ${nodeCount}` });

  if (Array.isArray(body.nodes)) {
    const allDlisql = body.nodes.every((n) => n.type === "DLISQL");
    checks.push({ name: "All node types = DLISQL", pass: allDlisql, detail: allDlisql ? "OK" : body.nodes.map((n) => n.type).join(", ") });

    const allPreNodeArrays = body.nodes.every((n) => Array.isArray(n.preNodeName));
    checks.push({ name: "All node preNodeName are arrays", pass: allPreNodeArrays, detail: allPreNodeArrays ? "OK" : "not all arrays" });

    const allLocationStrings = body.nodes.every((n) =>
      n.location && typeof n.location.x === "string" && typeof n.location.y === "string"
    );
    checks.push({ name: "All node location.x/y are strings", pass: allLocationStrings, detail: allLocationStrings ? "OK" : "not all strings" });

    const allPropsArrays = body.nodes.every((n) => Array.isArray(n.properties));
    checks.push({ name: "All node properties are arrays", pass: allPropsArrays, detail: allPropsArrays ? "OK" : "not all arrays" });

    const allHaveSql = body.nodes.every((n) =>
      Array.isArray(n.properties) && n.properties.some((p) => p.name === "sql")
    );
    checks.push({ name: "All nodes have sql property", pass: allHaveSql, detail: allHaveSql ? "OK" : "missing sql" });

    const nodeNames = new Set(body.nodes.map((n) => n.name));
    for (const node of body.nodes) {
      for (const dep of node.preNodeName || []) {
        if (!nodeNames.has(dep)) {
          checks.push({ name: `Node "${node.name}" preNodeName valid`, pass: false, detail: `depends on "${dep}" which is not defined` });
        }
      }
    }
  }

  if (body.schedule) {
    checks.push({ name: "schedule.type = CRON", pass: body.schedule.type === "CRON", detail: body.schedule.type || "missing" });

    if (body.schedule.cron) {
      const expr = body.schedule.cron.expression;
      const fields = expr ? expr.split(/\s+/) : [];
      checks.push({ name: "Cron expression has 6 fields", pass: fields.length === 6, detail: `got ${fields.length}: "${expr}"` });
      if (fields.length === 6) {
        checks.push({ name: "Cron first field = 0", pass: fields[0] === "0", detail: `got "${fields[0]}"` });
        checks.push({ name: "Cron fifth field = *", pass: fields[4] === "*", detail: `got "${fields[4]}"` });
        checks.push({ name: "Cron sixth field = ?", pass: fields[5] === "?", detail: `got "${fields[5]}"` });
      }
      checks.push({ name: "Cron expression = 0 0-59/5 * * * ?", pass: expr === "0 0-59/5 * * * ?", detail: expr || "missing" });

      const startTime = body.schedule.cron.startTime;
      checks.push({ name: "startTime exists", pass: !!startTime, detail: startTime || "missing" });
      if (startTime) {
        const hasMillis = /\.\d{3}/.test(startTime);
        checks.push({ name: "startTime has no milliseconds", pass: !hasMillis, detail: hasMillis ? "contains milliseconds" : "OK" });
      }
    }
  }

  const secrets = findSecrets(request, "");
  checks.push({ name: "No secrets present", pass: secrets.length === 0, detail: secrets.length > 0 ? secrets.join(", ") : "OK" });

  const placeholders = findPlaceholders(request, "");
  checks.push({ name: "No placeholder values", pass: placeholders.length === 0, detail: placeholders.length > 0 ? placeholders.join(", ") : "OK" });

  for (const c of checks) {
    const status = c.pass ? "PASS" : "FAIL";
    console.log(`  [${status}] ${c.name} (${c.detail})`);
  }

  const allPass = checks.every((c) => c.pass);
  console.log("");
  console.log(allPass ? "Overall: PASS" : "Overall: FAIL");
  process.exit(allPass ? 0 : 1);
}

main();
