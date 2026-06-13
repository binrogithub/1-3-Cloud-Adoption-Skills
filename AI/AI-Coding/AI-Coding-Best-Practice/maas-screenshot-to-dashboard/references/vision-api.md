# Vision API Reference — OpenRouter Free Vision Models

## How to Call

### Direct Python API Call (Most Reliable)

```python
import json, base64, urllib.request
from pathlib import Path

# 1. Read image file as base64
with open("screenshot.jpeg", "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode()

# 2. Get API key from Claude settings
with open(Path.home() / ".claude" / "settings.json") as f:
    settings = json.load(f)
api_key = settings["mcpServers"]["openvision"]["env"]["OPENROUTER_API_KEY"]

# 3. Build request payload
payload = {
    "model": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "messages": [{
        "role": "user",
        "content": [
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{img_b64}"
                }
            },
            {
                "type": "text",
                "text": "你的分析提示词..."
            }
        ]
    }]
}

# 4. Send request
req = urllib.request.Request(
    "https://openrouter.ai/api/v1/chat/completions",
    data=json.dumps(payload).encode(),
    headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
)

# 5. Parse response
with urllib.request.urlopen(req, timeout=120) as resp:
    result = json.loads(resp.read().decode())
    content = result["choices"][0]["message"]["content"]
    print(content)
```

### Image URL Formats

The `image_url.url` field accepts:

| Format | Example | When to use |
|---|---|---|
| Base64 data URI | `data:image/jpeg;base64,/9j/4AAQ...` | Local files (most common) |
| HTTP URL | `https://example.com/screenshot.png` | Publicly hosted images |
| File path | Does NOT work | Never — must convert to base64 first |

### Converting local files to base64

```python
import base64

# JPEG
with open("image.jpeg", "rb") as f:
    b64 = base64.b64encode(f.read()).decode()
    url = f"data:image/jpeg;base64,{b64}"

# PNG
with open("image.png", "rb") as f:
    b64 = base64.b64encode(f.read()).decode()
    url = f"data:image/png;base64,{b64}"
```

## Available Free Models

| Model ID | Modality | OCR Quality | Speed | Rate Limit |
|---|---|---|---|---|
| `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` | text+image+audio+video→text | Good | Medium | Moderate |
| `nvidia/nemotron-nano-12b-v2-vl:free` | text+image+video→text | Fair | Fast | Moderate |
| `google/gemma-4-26b-a4b-it:free` | text+image+video→text | Good | Medium | Strict (429) |
| `google/gemma-4-31b-it:free` | text+image+video→text | Good | Slow | Strict (429) |
| `openrouter/free` | text+image→text | Variable | Fast | Moderate |

### Model Selection Strategy

1. Try `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` first (best balance)
2. If 429 rate-limited → wait 10s and retry, or switch to `nvidia/nemotron-nano-12b-v2-vl:free`
3. If content is empty → switch model and retry
4. Never use Google models as primary (too aggressive rate limiting)

### Broken/404 Models (Do NOT use)

- `qwen/qwen2.5-vl-32b-instruct:free` — 404 no endpoint
- `google/gemini-flash-1.5:free` — 404 no endpoint
- `meta-llama/llama-4-scout:free` — 404 no endpoint

## Prompt Templates

### Dashboard Analysis (Full)

```
请详细分析这张看板截图的所有内容，包括：
1. 顶部标题和导航栏
2. 左侧菜单栏的所有菜单项
3. 顶部 KPI 卡片的具体数值和指标名称
4. 每个图表的标题、类型和数据
5. 表格的列名和数据
6. 颜色方案和布局细节
7. 所有文字内容（中文/英文）

请尽可能详细和准确地提取所有可见信息。
```

### Layout Analysis (Focused)

```
分析这张截图的布局结构：
1. 整体是几列布局？每列的宽度比例？
2. 每个区域包含什么组件？
3. 组件之间的间距是多少像素？
4. 有没有侧边栏、顶栏、面包屑？
```

### Color Extraction (Focused)

```
列出这张截图中所有使用的颜色，包括：
1. 背景色（精确hex值）
2. 文字颜色（不同层级）
3. 图表配色（每个数据系列的颜色）
4. 边框和分割线颜色
5. 强调色/品牌色
```

## Error Handling

| Error | Cause | Solution |
|---|---|---|
| 400 Bad Request | Image too large or invalid | Resize image to < 1MB before encoding |
| 429 Too Many Requests | Rate limit hit | Wait 10-30s, switch model, or retry |
| Empty `content` in response | Model couldn't process | Switch to different model, simplify prompt |
| Timeout | Large image + slow model | Reduce image size, increase timeout to 180s |
| 404 Model not found | Model deprecated | Use a different model from the list above |

## MCP openvision Alternative

If the `openvision` MCP server is connected in the current session, you can use its `image_analysis` tool instead of direct API calls. However, MCP servers are often not connected after session restart, so the direct Python API call is more reliable.

Settings for MCP openvision:
```json
{
  "openvision": {
    "command": "/root/.local/bin/uvx",
    "args": ["mcp-openvision"],
    "env": {
      "OPENROUTER_API_KEY": "sk-or-v1-...",
      "OPENROUTER_DEFAULT_MODEL": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"
    }
  }
}
```
