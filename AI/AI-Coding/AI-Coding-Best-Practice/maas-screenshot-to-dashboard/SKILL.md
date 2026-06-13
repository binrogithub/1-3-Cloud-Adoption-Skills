---
name: maas-screenshot-to-dashboard
description: "End-to-end screenshot-to-dashboard pipeline powered by MaaS vision models. Analyze a dashboard screenshot via OpenRouter free vision models, extract design tokens with anydesign, generate design.md + design-tokens.json, plan via CCPM, implement React+Ant Design+ECharts dashboard code, and iterate with screenshot comparison until ≥85% similarity. TRIGGER when the user provides a dashboard screenshot and wants to reconstruct it as a working web app, or says 'rebuild this dashboard', 'convert this screenshot to code', 'reproduce this BI dashboard', 'screenshot to React dashboard'. Do NOT use for: non-dashboard screenshots, Figma-to-code without screenshot, general UI development without a reference image."
---

# MaaS Screenshot-to-Dashboard Skill

## Overview

A complete pipeline that turns a dashboard screenshot into a production-ready React + TypeScript + Ant Design + ECharts web application, using MaaS-backed vision models for image analysis and design token extraction.

```
Screenshot → [1. Vision Model] → [2. anydesign] → [3. CCPM] → [4. Code Gen] → [5. Compare & Iterate]
```

| Step | Tool | Purpose | Time |
|---|---|---|---|
| 1 | OpenRouter Vision API | Analyze screenshot content (OCR, layout, data) | ~30s |
| 2 | anydesign skill | Extract design system tokens, generate design.md | ~2min |
| 3 | CCPM skill | Create PRD → Epic → Tasks with parallelization | ~5min |
| 4 | Claude Code | Implement code following tasks | ~30min |
| 5 | Puppeteer + pixelmatch | Screenshot comparison & iterate | ~1min/iter |

## When to Use

| Situation | Action |
|-----------|--------|
| User provides dashboard screenshot | Run full pipeline |
| "Rebuild this dashboard" | Run full pipeline |
| "Convert screenshot to code" | Run full pipeline |
| "Reproduce this BI dashboard" | Run full pipeline |
| Design tokens from screenshot needed | Run Steps 1-2 only |
| Dashboard code from existing design.md | Run Steps 3-5 only |

**When NOT to use:**
- Non-dashboard screenshots (photos, logos, icons)
- Figma-to-code without a screenshot reference
- General UI development without a reference image
- Static HTML/CSS generation (no framework needed)

## Default MaaS Configuration

| Setting | Value |
|---------|-------|
| Base URL | `https://openrouter.ai/api/v1` |
| Vision Model | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` |
| Fallback Model | `nvidia/nemotron-nano-12b-v2-vl:free` |
| Context Tokens | 196,608 |
| API Key Source | `settings.json → mcpServers.openvision.env.OPENROUTER_API_KEY` |

## Prerequisites

### 1. OpenRouter API Key

Get one at https://openrouter.ai (free tier available). Set in `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "openvision": {
      "command": "/root/.local/bin/uvx",
      "args": ["mcp-openvision"],
      "env": {
        "OPENROUTER_API_KEY": "sk-or-v1-...",
        "OPENROUTER_DEFAULT_MODEL": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"
      }
    }
  }
}
```

### 2. Free Vision Models

| Model ID | Modality | OCR | Speed | Rate Limit |
|---|---|---|---|---|
| `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` | text+image+audio+video→text | Good | Medium | Moderate |
| `nvidia/nemotron-nano-12b-v2-vl:free` | text+image+video→text | Fair | Fast | Moderate |
| `google/gemma-4-26b-a4b-it:free` | text+image+video→text | Good | Medium | Strict (429) |

**Broken (404)**: `qwen/qwen2.5-vl-32b-instruct:free`, `google/gemini-flash-1.5:free`, `meta-llama/llama-4-scout:free`

### 3. anydesign Skill

```bash
git clone https://github.com/uxKero/anydesign.git /tmp/anydesign
cp -r /tmp/anydesign .claude/skills/anydesign
pip install -r .claude/skills/anydesign/requirements.txt
playwright install chromium
```

### 4. CCPM Skill

Already in project at `ccpm-project/skill/ccpm/`. Copy to `.claude/skills/ccpm/`.

### 5. Project Dependencies

```bash
npm install react react-dom antd @ant-design/icons echarts echarts-for-react
npm install -D vite @vitejs/plugin-react typescript puppeteer sharp pixelmatch pngjs
```

## Mandatory Workflow

### Step 1 — Vision Analysis (Read the Screenshot)

**CRITICAL**: Claude Code CANNOT read images with the Read tool. Use OpenRouter Vision API.

```python
import json, base64, urllib.request
from pathlib import Path

with open("<screenshot_path>", "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode()

with open(Path.home() / ".claude" / "settings.json") as f:
    settings = json.load(f)
api_key = settings["mcpServers"]["openvision"]["env"]["OPENROUTER_API_KEY"]

payload = {
    "model": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "messages": [{
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
            {"type": "text", "text": "请详细分析这张看板截图的所有内容，包括：\n1. 顶部标题和导航栏\n2. 左侧菜单栏的所有菜单项\n3. 顶部 KPI 卡片的具体数值和指标名称\n4. 每个图表的标题、类型和数据\n5. 表格的列名和数据\n6. 颜色方案和布局细节\n7. 所有文字内容（中文/英文）\n\n请尽可能详细和准确地提取所有可见信息。"}
        ]
    }]
}

req = urllib.request.Request(
    "https://openrouter.ai/api/v1/chat/completions",
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
)

with urllib.request.urlopen(req, timeout=120) as resp:
    result = json.loads(resp.read().decode())
    content = result["choices"][0]["message"]["content"]
```

See `references/vision-api.md` for full details, error handling, and fallback strategies.

### Step 2 — Design Token Extraction (anydesign)

```bash
# Extract dominant colors
python .claude/skills/anydesign/scripts/extract_colors.py <screenshot_path>

# WCAG contrast check
python .claude/skills/anydesign/scripts/check_contrast.py --pair "#050C38,#FFFFFF" --pair "#050C38,#1890ff"

# Lint design.md after generation
python .claude/skills/anydesign/scripts/lint_design_md.py design.md
```

Generate 3 files:
- `design.md` — YAML frontmatter + 8 analysis sections (see `references/design-output.md`)
- `design-tokens.json` — W3C DTCG format (`$value`/`$type`)
- `design-a11y.md` — WCAG 2.1 contrast ratios

### Step 3 — Project Planning (CCPM)

1. Write PRD at `.claude/prds/<name>.md`
2. Parse PRD into Epic at `.claude/epics/<name>/epic.md`
3. Decompose Epic into Tasks (≤10, identify parallelizable ones)

See `references/planning-workflow.md` for PRD/epic/task templates.

### Step 4 — Code Implementation

Execute tasks in dependency order:

| Phase | Tasks | Parallel? |
|---|---|---|
| Sequential | Theme foundation → Mock data → KPI cards | No |
| Parallel | Map, Tables, Charts (spawn agents) | Yes |
| Assembly | Dashboard layout + all components | No |

See `references/code-patterns.md` for implementation patterns.

### Step 5 — Build & Verify

```bash
npx vite build  # Must succeed with zero errors
```

### Step 6 — Compare & Iterate

```javascript
const sharp = require('sharp');
const { PNG } = require('pngjs');
const pixelmatch = require('pixelmatch').default;

const buf1 = await sharp('original.jpeg').png().toBuffer();
const img1 = PNG.sync.read(buf1);
const buf2 = await sharp('generated.png').resize(img1.width, img1.height).png().toBuffer();
const img2 = PNG.sync.read(buf2);
const diff = new PNG({ width: img1.width, height: img1.height });
const mismatch = pixelmatch(img1.data, img2.data, diff.data, img1.width, img1.height, { threshold: 0.1 });
const similarity = ((1 - mismatch / (img1.width * img1.height)) * 100).toFixed(2);
```

Iterate until similarity ≥ 85% (max 5 rounds). See `references/iteration.md` for strategy.

## Quality Gates

- [ ] `npx vite build` succeeds with zero errors
- [ ] Screenshot similarity ≥ 85%
- [ ] All KPI values match original screenshot
- [ ] All chart titles are bilingual
- [ ] Color surface matches design-tokens.json
- [ ] `lint_design_md.py design.md` passes
- [ ] No console errors on page load
- [ ] Git commit with meaningful message

## Common Pitfalls

1. **Cannot read images with Read tool** — Use OpenRouter Vision API
2. **Free vision models rate-limited (429)** — Switch model (nemotron > gemma)
3. **GeoJSON for maps** — ECharts needs `registerMap()`; fetch at runtime or bundle in `public/`
4. **Ant Design dark ≠ navy theme** — Override `colorBgLayout`, `colorBgContainer`, `colorBgElevated`
5. **pixelmatch import** — Use `require('pixelmatch').default` (ESM default export)
6. **Context window overflow** — Use `/clear` and resume from git state
7. **Chart rendering delay** — Wait 3s after page load before screenshot

## Cross-Skill References

- **maas-ai-coding-quality-skill** — Run quality gates after code generation
- **maas-spec-plan-build-test-skill** — Alternative planning workflow
- **ccpm** — Project management used in Step 3
- **anydesign** — Design analysis used in Step 2
