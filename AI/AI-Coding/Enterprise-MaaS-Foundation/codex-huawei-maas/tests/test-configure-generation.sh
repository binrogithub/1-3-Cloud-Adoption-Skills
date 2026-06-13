#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

mkdir -p "$tmp/bin" "$tmp/npmroot/@musistudio/claude-code-router/dist"

cat > "$tmp/bin/npm" <<EOF
#!/usr/bin/env bash
case "\$1" in
  root) echo "$tmp/npmroot" ;;
  install) exit 0 ;;
  *) exit 0 ;;
esac
EOF

cat > "$tmp/bin/ccr" <<'EOF'
#!/usr/bin/env bash
case "$1" in
  start|stop|status) exit 0 ;;
  *) exit 0 ;;
esac
EOF

cat > "$tmp/bin/codex" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF

cat > "$tmp/bin/curl" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF

chmod +x "$tmp/bin"/*

node - "$tmp/npmroot/@musistudio/claude-code-router/dist/cli.js" <<'NODE'
const fs = require('fs');
const file = process.argv[2];
const needle = 'e.get("/health",async()=>({status:"ok",timestamp:new Date().toISOString()}));let t=e.transformerService.getTransformersWithEndpoint();for(let{transformer:r}of t)r.endPoint&&e.post(r.endPoint,async(n,s)=>cN(n,s,e,r));';
fs.writeFileSync(file, needle);
NODE

PATH="$tmp/bin:$PATH" \
HOME="$tmp/home" \
CODEX_HOME="$tmp/home/.codex" \
CODEX_GLM_BIN_DIR="$tmp/home/.local/bin" \
CODEX_GLM_CONFIG_DIR="$tmp/home/.config/codex-glm" \
CODEX_GLM_CCR_HOME="$tmp/home/.codex-glm/ccr-home" \
CODEX_GLM_MODEL_CATALOG_DIR="$tmp/home/.codex-glm" \
INSTALL_SYSTEMD_USER_SERVICE=0 \
VERIFY=0 \
HUAWEI_MAAS_API_KEY=test-key \
CODEX_GLM_ENABLE_SEARCH=1 \
CODEX_GLM_ENABLE_IMAGE=1 \
CODEX_GLM_IMAGE_MODEL=vision-openrouter \
LITELLM_CCR_KEY=litellm-key \
"$repo_dir/scripts/configure-codex-glm.sh" >/dev/null

node - "$tmp" <<'NODE'
const fs = require('fs');
const base = process.argv[2];
const cfg = JSON.parse(fs.readFileSync(`${base}/home/.codex-glm/ccr-home/.claude-code-router/config.json`, 'utf8'));
const catalog = JSON.parse(fs.readFileSync(`${base}/home/.codex-glm/model-catalog.json`, 'utf8'));
const env = fs.readFileSync(`${base}/home/.config/codex-glm/env`, 'utf8');
const cli = fs.readFileSync(`${base}/npmroot/@musistudio/claude-code-router/dist/cli.js`, 'utf8');

if (cfg.Router.default !== 'LiteLLM Provider,glm-5.1') throw new Error('search should route default traffic through LiteLLM Provider');
if (cfg.Router.image !== 'litellm-chat,vision-openrouter') throw new Error('missing image route');
if (!cfg.transformers || cfg.transformers.length !== 1) throw new Error('missing search transformer path');
const imageProvider = cfg.Providers.find((provider) => provider.name === 'litellm-chat');
if (!imageProvider) throw new Error('missing litellm-chat provider');
if (!imageProvider.models.includes('vision-openrouter')) throw new Error('image provider did not use configured vision model');
if (catalog.models[0].supports_search_tool !== true) throw new Error('missing search catalog flag');
if (!catalog.models[0].input_modalities.includes('image')) throw new Error('missing image modality');
if (!env.includes('CODEX_GLM_ENABLE_SEARCH="1"')) throw new Error('env did not persist search flag');
if (!env.includes('CODEX_GLM_ENABLE_IMAGE="1"')) throw new Error('env did not persist image flag');
if (!env.includes('CODEX_GLM_IMAGE_MODEL="vision-openrouter"')) throw new Error('env did not persist image model');
if ((cli.match(/\/\/ codex-glm responses shim/g) || []).length !== 1) throw new Error('shim injection is not idempotent in generated cli');
NODE

echo "configure generation tests passed"
