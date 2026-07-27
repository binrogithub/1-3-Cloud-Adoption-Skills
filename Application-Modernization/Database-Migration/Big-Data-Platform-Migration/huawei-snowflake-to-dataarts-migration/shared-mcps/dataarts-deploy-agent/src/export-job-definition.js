const fs = require("fs");
const path = require("path");
const https = require("https");
const { execSync } = require("child_process");
const config = require("./config");
const { buildSignedHeaders } = require("./huawei-signer");

const OUT_DIR = path.resolve(__dirname, "..", "out");
const EXPORT_DIR = path.join(OUT_DIR, "exported_job");
const EXTRACTED_DIR = path.join(EXPORT_DIR, "extracted");
const V1_REQUEST_FILE = path.join(OUT_DIR, "dataarts_create_job_request.v1.dryrun.json");

function maskId(id) {
  if (!id || id.length < 8) return "***";
  return id.slice(0, 4) + "***" + id.slice(-4);
}

function httpsRequestBuffer(url, options, timeoutMs = 60000) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      req.destroy(new Error("REQUEST_TIMEOUT"));
    }, timeoutMs);

    const req = https.request(url, options, (res) => {
      clearTimeout(timer);
      const chunks = [];
      res.on("data", (chunk) => chunks.push(chunk));
      res.on("end", () => {
        const buffer = Buffer.concat(chunks);
        resolve({ statusCode: res.statusCode, headers: res.headers, body: buffer });
      });
    });

    req.on("error", (err) => {
      clearTimeout(timer);
      reject(err);
    });

    if (options.body) {
      req.write(options.body);
    }
    req.end();
  });
}

async function signedPost(url, ak, sk, workspaceId, body) {
  const headers = {
    "Content-Type": "application/json",
    workspace: workspaceId,
  };

  const signed = buildSignedHeaders({
    method: "POST",
    url,
    headers,
    body: body || "",
    ak,
    sk,
  });

  const parsed = new URL(url);
  const options = {
    hostname: parsed.hostname,
    port: 443,
    path: parsed.pathname + parsed.search,
    method: "POST",
    headers: signed,
  };

  return httpsRequestBuffer(url, options);
}

function isJsonContentType(headers) {
  const ct = (headers["content-type"] || "").toLowerCase();
  return ct.includes("application/json") || ct.includes("text/json");
}

function isZipContentType(headers) {
  const ct = (headers["content-type"] || "").toLowerCase();
  return ct.includes("application/zip") || ct.includes("application/x-zip") || ct.includes("application/octet-stream");
}

function isZipBuffer(buffer) {
  return buffer.length >= 4 && buffer[0] === 0x50 && buffer[1] === 0x4b && buffer[2] === 0x03 && buffer[3] === 0x04;
}

function tryExtractZip(zipPath, destDir) {
  try {
    if (!fs.existsSync(destDir)) {
      fs.mkdirSync(destDir, { recursive: true });
    }
    execSync(`unzip -o "${zipPath}" -d "${destDir}"`, { stdio: "pipe", timeout: 15000 });
    return true;
  } catch {
    return false;
  }
}

function findInExtracted(dir, patterns) {
  const found = {};
  for (const p of patterns) {
    found[p] = false;
  }

  function walk(currentDir) {
    const entries = fs.readdirSync(currentDir, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(currentDir, entry.name);
      if (entry.isDirectory()) {
        walk(fullPath);
      } else if (entry.isFile()) {
        try {
          const content = fs.readFileSync(fullPath, "utf-8");
          for (const p of patterns) {
            if (content.includes(p)) {
              found[p] = true;
            }
          }
        } catch {}
      }
    }
  }

  if (fs.existsSync(dir)) {
    walk(dir);
  }
  return found;
}

function findInJson(obj, patterns) {
  const jsonStr = JSON.stringify(obj, null, 2);
  const found = {};
  for (const p of patterns) {
    found[p] = jsonStr.includes(p);
  }
  return found;
}

function findSqlSnippetsInExtracted(dir) {
  const sqlSnippets = [];

  function walk(currentDir) {
    const entries = fs.readdirSync(currentDir, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(currentDir, entry.name);
      if (entry.isDirectory()) {
        walk(fullPath);
      } else if (entry.isFile()) {
        try {
          const content = fs.readFileSync(fullPath, "utf-8");
          const upper = content.toUpperCase();
          if (upper.includes("SELECT") || upper.includes("INSERT") || upper.includes("MERGE") || upper.includes("CREATE")) {
            sqlSnippets.push({ file: path.relative(dir, fullPath), length: content.length, hasSelect: upper.includes("SELECT"), hasInsert: upper.includes("INSERT"), hasMerge: upper.includes("MERGE") });
          }
        } catch {}
      }
    }
  }

  if (fs.existsSync(dir)) {
    walk(dir);
  }
  return sqlSnippets;
}

function findSqlSnippetsInJson(obj) {
  const sqlSnippets = [];
  const jsonStr = JSON.stringify(obj, null, 2);
  const upper = jsonStr.toUpperCase();
  sqlSnippets.push({ source: "json_response", length: jsonStr.length, hasSelect: upper.includes("SELECT"), hasInsert: upper.includes("INSERT"), hasMerge: upper.includes("MERGE") });
  return sqlSnippets;
}

async function main() {
  console.log("=== DataArts Deploy Agent: EXPORT JOB DEFINITION ===\n");

  try {
    const env = config.load();
    config.validate(env);

    const endpointHost = `dayu-dlf.${env.HUAWEI_REGION}.myhuaweicloud.com`;
    const endpoint = `https://${endpointHost}`;
    const projectId = env.HUAWEI_PROJECT_ID;
    const workspaceId = env.DATAARTS_WORKSPACE_ID;
    const ak = env.HUAWEI_AK;
    const sk = env.HUAWEI_SK;

    console.log(`Endpoint:  ${endpoint}`);
    console.log(`Project:   ${maskId(projectId)}`);
    console.log(`Workspace: ${maskId(workspaceId)}`);
    console.log("");

    if (!fs.existsSync(V1_REQUEST_FILE)) {
      throw new Error(`Missing v1 dry-run request: ${V1_REQUEST_FILE}\nRun "npm run dry-run" first.`);
    }

    const v1Request = JSON.parse(fs.readFileSync(V1_REQUEST_FILE, "utf-8"));
    const v1Body = v1Request.body || v1Request;
    const jobName = v1Body.name;

    if (!jobName) {
      throw new Error("V1 request is missing job name.");
    }

    console.log(`Job name:  ${jobName}`);
    console.log("");

    const exportUrl = `${endpoint}/v1/${projectId}/jobs/${encodeURIComponent(jobName)}/export`;
    console.log("Exporting job definition...");
    console.log(`  POST /v1/${maskId(projectId)}/jobs/${jobName}/export`);

    let result;
    try {
      result = await signedPost(exportUrl, ak, sk, workspaceId, "");
    } catch (err) {
      throw new Error(`Export request failed: ${err.message}`);
    }

    console.log(`  Status: ${result.statusCode}`);

    const contentType = result.headers["content-type"] || "unknown";
    console.log(`  Content-Type: ${contentType}`);

    if (!fs.existsSync(EXPORT_DIR)) {
      fs.mkdirSync(EXPORT_DIR, { recursive: true });
    }

    const timestamp = new Date().toISOString();
    const outputFiles = [];
    let exportSuccessful = false;
    let isZip = false;
    let isJson = false;
    let nodeNamesFound = {};
    let sqlSnippets = [];
    let extractedOk = false;
    let jsonExport = null;

    const expectedNodeNames = ["load_silver_orders", "build_gold_daily_sales", "audit_pipeline"];

    if (result.statusCode >= 200 && result.statusCode < 300) {
      exportSuccessful = true;

      if (isZipContentType(result.headers) || isZipBuffer(result.body)) {
        isZip = true;
        const zipPath = path.join(EXPORT_DIR, "job_export.zip");
        fs.writeFileSync(zipPath, result.body);
        outputFiles.push("out/exported_job/job_export.zip");
        console.log(`  Saved ZIP: ${zipPath} (${result.body.length} bytes)`);

        extractedOk = tryExtractZip(zipPath, EXTRACTED_DIR);
        if (extractedOk) {
          console.log(`  Extracted to: ${EXTRACTED_DIR}`);
          outputFiles.push("out/exported_job/extracted/");

          nodeNamesFound = findInExtracted(EXTRACTED_DIR, expectedNodeNames);
          sqlSnippets = findSqlSnippetsInExtracted(EXTRACTED_DIR);
        } else {
          console.log("  ZIP extraction failed — manual inspection needed.");
        }
      } else if (isJsonContentType(result.headers)) {
        isJson = true;
        try {
          jsonExport = JSON.parse(result.body.toString("utf-8"));
        } catch {
          jsonExport = null;
        }
        const jsonPath = path.join(EXPORT_DIR, "job_export_response.json");
        fs.writeFileSync(jsonPath, JSON.stringify(jsonExport || result.body.toString("utf-8"), null, 2), "utf-8");
        outputFiles.push("out/exported_job/job_export_response.json");
        console.log(`  Saved JSON: ${jsonPath}`);

        if (jsonExport) {
          nodeNamesFound = findInJson(jsonExport, expectedNodeNames);
          sqlSnippets = findSqlSnippetsInJson(jsonExport);
        }
      } else {
        const rawPath = path.join(EXPORT_DIR, "job_export_response.raw");
        fs.writeFileSync(rawPath, result.body);
        outputFiles.push("out/exported_job/job_export_response.raw");
        console.log(`  Saved raw response: ${rawPath} (${result.body.length} bytes)`);

        if (isZipBuffer(result.body)) {
          isZip = true;
          const zipPath = path.join(EXPORT_DIR, "job_export.zip");
          fs.writeFileSync(zipPath, result.body);
          outputFiles.push("out/exported_job/job_export.zip");
          extractedOk = tryExtractZip(zipPath, EXTRACTED_DIR);
          if (extractedOk) {
            console.log(`  Extracted to: ${EXTRACTED_DIR}`);
            outputFiles.push("out/exported_job/extracted/");
            nodeNamesFound = findInExtracted(EXTRACTED_DIR, expectedNodeNames);
            sqlSnippets = findSqlSnippetsInExtracted(EXTRACTED_DIR);
          }
        }
      }
    } else {
      console.log(`  Export failed or returned unexpected status.`);
      const errBody = result.body.toString("utf-8").slice(0, 500);
      console.log(`  Response: ${errBody}`);

      const errJsonPath = path.join(EXPORT_DIR, "job_export_response.json");
      try {
        const errJson = JSON.parse(result.body.toString("utf-8"));
        fs.writeFileSync(errJsonPath, JSON.stringify(errJson, null, 2), "utf-8");
        outputFiles.push("out/exported_job/job_export_response.json");
      } catch {
        fs.writeFileSync(errJsonPath, result.body.toString("utf-8"), "utf-8");
        outputFiles.push("out/exported_job/job_export_response.json");
      }
    }

    const allNodesFound = expectedNodeNames.every((n) => nodeNamesFound[n]);
    const hasSql = sqlSnippets.length > 0 && (sqlSnippets.some((s) => s.hasSelect || s.hasInsert || s.hasMerge));

    const jsonReport = {
      timestamp,
      endpoint,
      project_id_masked: maskId(projectId),
      workspace_id_masked: maskId(workspaceId),
      job_name: jobName,
      http_status: result.statusCode,
      response_content_type: contentType,
      export_successful: exportSuccessful,
      response_format: isZip ? "ZIP" : isJson ? "JSON" : "UNKNOWN",
      output_files: outputFiles,
      zip_extracted: extractedOk,
      node_names_in_export: nodeNamesFound,
      all_nodes_found: allNodesFound,
      sql_snippets_found: hasSql,
      sql_snippet_details: sqlSnippets,
      no_secrets_included: true,
      safety: {
        no_publish: true,
        no_start: true,
        no_run: true,
        no_update: true,
        no_delete: true,
        no_overwrite: true,
        only_endpoint_called: `POST /v1/{project_id}/jobs/${jobName}/export`,
      },
    };

    const mdLines = [];
    mdLines.push("# Export Job Definition Report");
    mdLines.push("");
    mdLines.push(`**Timestamp:** ${timestamp}`);
    mdLines.push(`**Result:** ${exportSuccessful ? "EXPORT SUCCESSFUL" : "EXPORT FAILED"}`);
    mdLines.push("");

    mdLines.push("## Environment");
    mdLines.push("");
    mdLines.push("| Field | Value |");
    mdLines.push("|-------|-------|");
    mdLines.push(`| Endpoint | ${endpoint} |`);
    mdLines.push(`| project_id | ${maskId(projectId)} |`);
    mdLines.push(`| workspace_id | ${maskId(workspaceId)} |`);
    mdLines.push(`| job_name | ${jobName} |`);
    mdLines.push("");

    mdLines.push("## Export Result");
    mdLines.push("");
    mdLines.push("| Field | Value |");
    mdLines.push("|-------|-------|");
    mdLines.push(`| HTTP Status | ${result.statusCode} |`);
    mdLines.push(`| Content-Type | ${contentType} |`);
    mdLines.push(`| Response Format | ${isZip ? "ZIP" : isJson ? "JSON" : "UNKNOWN"} |`);
    mdLines.push(`| Export Successful | ${exportSuccessful ? "Yes" : "No"} |`);
    mdLines.push(`| ZIP Extracted | ${extractedOk ? "Yes" : isZip ? "No (manual inspection needed)" : "N/A"} |`);
    mdLines.push("");

    mdLines.push("## Output Files");
    mdLines.push("");
    for (const f of outputFiles) {
      mdLines.push(`- \`${f}\``);
    }
    mdLines.push("");

    mdLines.push("## Node Names in Exported Content");
    mdLines.push("");
    mdLines.push("| Node Name | Found |");
    mdLines.push("|-----------|-------|");
    for (const n of expectedNodeNames) {
      mdLines.push(`| ${n} | ${nodeNamesFound[n] ? "Yes" : "No"} |`);
    }
    mdLines.push("");
    mdLines.push(`**All nodes found:** ${allNodesFound ? "Yes" : "No"}`);
    mdLines.push("");

    mdLines.push("## SQL Snippets");
    mdLines.push("");
    if (hasSql) {
      mdLines.push(`SQL content found in exported data (${sqlSnippets.length} source(s)).`);
      mdLines.push("");
      for (const s of sqlSnippets) {
        const loc = s.file || s.source || "unknown";
        mdLines.push(`- \`${loc}\` (length: ${s.length}, SELECT: ${s.hasSelect}, INSERT: ${s.hasInsert}, MERGE: ${s.hasMerge})`);
      }
    } else {
      mdLines.push("No SQL snippets found in exported content (or extraction was not possible).");
    }
    mdLines.push("");

    mdLines.push("## Safety Statement");
    mdLines.push("");
    mdLines.push("> **No publish, start, run, update, delete, or overwrite operation was executed.**");
    mdLines.push(">");
    mdLines.push(`> This command only called \`POST /v1/{project_id}/jobs/${jobName}/export\`.`);
    mdLines.push("> The export operation is read-only — it retrieves job definitions and dependency scripts.");
    mdLines.push("> It did NOT call `/start`, `/run-immediate`, any PUT, PATCH, or DELETE endpoint.");
    mdLines.push("> No write, publish, start, or destructive operation was executed.");
    mdLines.push("");

    const mdReport = mdLines.join("\n");

    fs.writeFileSync(path.join(EXPORT_DIR, "export_job_definition_result.json"), JSON.stringify(jsonReport, null, 2), "utf-8");
    fs.writeFileSync(path.join(EXPORT_DIR, "export_job_definition_report.md"), mdReport, "utf-8");

    console.log("");
    console.log("=== Export Summary ===\n");
    console.log(`  Export successful: ${exportSuccessful}`);
    console.log(`  Response format:   ${isZip ? "ZIP" : isJson ? "JSON" : "UNKNOWN"}`);
    console.log(`  All nodes found:   ${allNodesFound}`);
    console.log(`  SQL snippets:      ${hasSql ? "Yes" : "No"}`);
    if (isZip) {
      console.log(`  ZIP extracted:     ${extractedOk}`);
    }
    console.log("");
    console.log("Safety: No publish, start, run, update, delete, or overwrite operation was executed.");
    console.log("Only POST .../export was called (read-only export of job definition).\n");

    console.log("Reports saved:");
    console.log(`  ${path.join(EXPORT_DIR, "export_job_definition_report.md")}`);
    console.log(`  ${path.join(EXPORT_DIR, "export_job_definition_result.json")}`);

    process.exit(exportSuccessful ? 0 : 1);
  } catch (err) {
    console.error(`EXPORT JOB DEFINITION FAILED: ${err.message}`);
    process.exit(1);
  }
}

main();
