# Design Output Reference — design.md Template

## File: design.md

### YAML Frontmatter

```yaml
---
version: anydesign-1
name: <dashboard-name>
source: <screenshot-path>
captured_at: YYYY-MM-DD
description: |
  <2-3 sentence atmosphere paragraph>

colors:
  surface: "#050C38"
  surface-elevated: "#1F2241"
  surface-card: "#0A1945"
  text-primary: "#FFFFFF"
  text-secondary: "#ffffffd9"
  text-muted: "#ffffffa6"
  text-faint: "#ffffff4d"
  primary: "#1890ff"
  accent: "#fa8c16"
  border: "rgba(255,255,255,0.08)"

typography:
  title: { fontFamily: "system-ui", fontSize: "20px", fontWeight: 600 }
  card-title: { fontFamily: "system-ui", fontSize: "13px", fontWeight: 500 }
  body: { fontFamily: "system-ui", fontSize: "12px", fontWeight: 400 }
  kpi-value: { fontFamily: "system-ui", fontSize: "24px", fontWeight: 600 }

spacing:
  base: 4px
  scale: [4, 8, 12, 16, 20, 24, 32, 48]

rounded:
  sm: 6px

components:
  kpi-card: { backgroundColor: "{colors.surface-card}", border: "1px solid {colors.border}", rounded: "{rounded.sm}" }
  chart-card: { backgroundColor: "{colors.surface-card}", border: "1px solid {colors.border}", rounded: "{rounded.sm}" }
---
```

### Prose Sections (8 required)

1. **Source** — type, path, capture method, limitations
2. **TL;DR** — 2-3 sentences: visual personality + distinctive + actionable insight
3. **Visual Identity** — personality, mood, references, density, positioning, brand voice, ONE brand thing
4. **Design System** — colors (hex + semantic role), typography, spacing, radii, elevation, borders, accessibility
5. **Components** — generic (KPI card, chart card, table) + signature (bilingual title, region-banded chart)
6. **Layout** — grid, composition patterns, responsive behavior, image behavior
7. **Reconstruction** — suggested stack, quick wins, tricky bits, confidence map
8. **Do's and Don'ts** — 5-7 each, brand-specific, cite tokens

## File: design-tokens.json

W3C DTCG format:

```json
{
  "color": {
    "surface": { "$value": "#050C38", "$type": "color", "$description": "Base background", "$extensions": { "anydesign": { "confidence": "high" } } }
  },
  "typography": {
    "font-size": {
      "body": { "$value": "12px", "$type": "dimension" }
    }
  },
  "$extensions": {
    "anydesign": {
      "source": "<screenshot-path>",
      "captured_at": "YYYY-MM-DD",
      "method": "vision model + extract_colors.py",
      "spec": "W3C Design Tokens Community Group 2025.10"
    }
  }
}
```

## File: design-a11y.md

WCAG 2.1 contrast table for key color pairs:

| Pair | Ratio | AA normal | AAA normal |
|---|---|---|---|
| `#FFFFFF` on `#050C38` | 18.81:1 | ✅ | ✅ |
| `#1890ff` on `#050C38` | 5.8:1 | ✅ | ❌ |
