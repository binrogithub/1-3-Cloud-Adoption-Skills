const fs = require("fs");
const path = require("path");
const yaml = require("js-yaml");

function readJSON(filePath) {
  if (!fs.existsSync(filePath)) {
    throw new Error(`Missing JSON file: ${filePath}`);
  }
  const raw = fs.readFileSync(filePath, "utf-8");
  try {
    return JSON.parse(raw);
  } catch (e) {
    throw new Error(`Invalid JSON in ${filePath}: ${e.message}`);
  }
}

function readYAML(filePath) {
  if (!fs.existsSync(filePath)) {
    throw new Error(`Missing YAML file: ${filePath}`);
  }
  const raw = fs.readFileSync(filePath, "utf-8");
  try {
    return yaml.load(raw);
  } catch (e) {
    throw new Error(`Invalid YAML in ${filePath}: ${e.message}`);
  }
}

function readSQL(filePath) {
  if (!fs.existsSync(filePath)) {
    throw new Error(`Missing SQL file: ${filePath}`);
  }
  return fs.readFileSync(filePath, "utf-8");
}

function loadAll(artifactsDir) {
  const analysisDir = path.join(artifactsDir, "analysis");
  const dataartsDir = path.join(artifactsDir, "dataarts");
  const nodesDir = path.join(dataartsDir, "nodes");

  const canonicalDag = readJSON(path.join(analysisDir, "canonical_dag.json"));
  const pipelineYaml = readYAML(path.join(dataartsDir, "dataarts_pipeline.yaml"));

  const sqlFiles = fs.readdirSync(nodesDir)
    .filter((f) => f.endsWith(".sql"))
    .sort();

  const sqlNodes = {};
  for (const f of sqlFiles) {
    sqlNodes[f] = readSQL(path.join(nodesDir, f));
  }

  return {
    canonicalDag,
    pipelineYaml,
    sqlNodes,
    artifactsDir,
  };
}

module.exports = { loadAll, readJSON, readYAML, readSQL };
