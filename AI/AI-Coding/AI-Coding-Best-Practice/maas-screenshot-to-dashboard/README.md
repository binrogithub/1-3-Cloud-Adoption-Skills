# MaaS Screenshot-to-Dashboard Skill

## Architecture

```
Screenshot (JPEG/PNG)
  → Step 1: OpenRouter Vision API (free model) — OCR, layout, data extraction
  → Step 2: anydesign — design.md + design-tokens.json + design-a11y.md
  → Step 3: CCPM — PRD → Epic → Tasks (with parallelization)
  → Step 4: Claude Code — React + Ant Design + ECharts implementation
  → Step 5: Puppeteer screenshot + pixelmatch comparison
  → Iterate until ≥ 85% similarity (max 5 rounds)
```

## Default MaaS Configuration

| Setting | Value |
|---------|-------|
| Base URL | `https://openrouter.ai/api/v1` |
| Vision Model | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` |
| Fallback Model | `nvidia/nemotron-nano-12b-v2-vl:free` |
| Context Tokens | 196,608 |
| API Key Source | `settings.json → mcpServers.openvision.env.OPENROUTER_API_KEY` |

## Files

```
maas-screenshot-to-dashboard/
  SKILL.md                              # This skill definition
  README.md                             # This file
  references/
    vision-api.md                       # OpenRouter Vision API call details
    iteration.md                        # Screenshot comparison & iteration strategy
    code-patterns.md                    # Ant Design + ECharts dark theme patterns
    design-output.md                    # design.md template and token format
    planning-workflow.md                # PRD/epic/task templates from CCPM
  scripts/
    call-vision-api.py                  # Standalone vision API caller
    compare-screenshots.js              # Standalone screenshot comparison
    extract-dominant-colors.sh          # Wrapper for anydesign extract_colors.py
  agents/
    openai.yaml                         # Agent interface for parallel chart implementation
  assets/
    config/
      antd-dark-navy-theme.json         # Ant Design theme token overrides for navy surface
```

## Quick Start

### 1. Install Prerequisites

```bash
# Install anydesign skill
git clone https://github.com/uxKero/anydesign.git /tmp/anydesign
cp -r /tmp/anydesign .claude/skills/anydesign
pip install -r .claude/skills/anydesign/requirements.txt
playwright install chromium

# Install CCPM skill
cp -r ccpm-project/skill/ccpm .claude/skills/ccpm

# Install project dependencies
npm install react react-dom antd @ant-design/icons echarts echarts-for-react
npm install -D vite @vitejs/plugin-react typescript puppeteer sharp pixelmatch pngjs
```

### 2. Set OpenRouter API Key

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "openvision": {
      "command": "/root/.local/bin/uvx",
      "args": ["mcp-openvision"],
      "env": {
        "OPENROUTER_API_KEY": "sk-or-v1-YOUR_KEY",
        "OPENROUTER_DEFAULT_MODEL": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"
      }
    }
  }
}
```

### 3. Run the Pipeline

In Claude Code, provide a dashboard screenshot:

```
Rebuild this dashboard from screenshot.jpeg
```

The skill will automatically:
1. Analyze the screenshot via vision model
2. Extract design tokens
3. Plan the project (PRD → Epic → Tasks)
4. Implement the code
5. Compare and iterate until ≥85% similarity

## Output Files

| File | Purpose |
|------|---------|
| `design.md` | Design analysis with YAML frontmatter tokens |
| `design-tokens.json` | W3C DTCG format tokens for tooling |
| `design-a11y.md` | WCAG 2.1 contrast report |
| `generated-screenshot.png` | Latest generated screenshot |
| `diff-image.png` | Visual diff between original and generated |
| `.claude/prds/<name>.md` | Product requirement document |
| `.claude/epics/<name>/` | Epic + task files |

## Verified With

- **Screenshot**: WhatsApp dashboard image (1041×681px)
- **Stack**: React 19 + TypeScript + Ant Design 6 + ECharts 6 + Vite 8
- **Vision Model**: `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` via OpenRouter
- **Result**: 70.78% similarity on first iteration (target ≥85% with iteration)
- **Components**: 8 KPI cards, choropleth map, 2 Top-10 tables, 4 ECharts visualizations

## Cross-Skill Dependencies

- **anydesign** — Design analysis and token extraction (Step 2)
- **ccpm** — Project planning and task management (Step 3)
- **maas-ai-coding-quality-skill** — Quality gates after code generation
- **maas-spec-plan-build-test-skill** — Alternative planning workflow
