#!/usr/bin/env python3
"""Call OpenRouter Vision API to analyze a dashboard screenshot.

Usage:
    python call-vision-api.py <screenshot_path> [--model MODEL] [--prompt PROMPT]

Example:
    python call-vision-api.py dashboard.jpeg
    python call-vision-api.py dashboard.jpeg --model nvidia/nemotron-nano-12b-v2-vl:free
"""

import argparse
import base64
import json
import os
from pathlib import Path
import sys
import urllib.request

DEFAULT_MODEL = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"
DEFAULT_PROMPT = """请详细分析这张看板截图的所有内容，包括：
1. 顶部标题和导航栏
2. 左侧菜单栏的所有菜单项
3. 顶部 KPI 卡片的具体数值和指标名称
4. 每个图表的标题、类型和数据
5. 表格的列名和数据
6. 颜色方案和布局细节
7. 所有文字内容（中文/英文）

请尽可能详细和准确地提取所有可见信息。"""

DEFAULT_SETTINGS_PATH = Path.home() / ".claude" / "settings.json"


def get_api_key():
    settings_path = Path(os.environ.get("CLAUDE_SETTINGS_PATH", DEFAULT_SETTINGS_PATH)).expanduser()
    with open(settings_path) as f:
        settings = json.load(f)
    return settings["mcpServers"]["openvision"]["env"]["OPENROUTER_API_KEY"]


def analyze_image(image_path, model=DEFAULT_MODEL, prompt=DEFAULT_PROMPT):
    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    api_key = get_api_key()

    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                {"type": "text", "text": prompt},
            ],
        }],
    }

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            result = json.loads(resp.read().decode())
            return result["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"HTTP {e.code}: {body}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Analyze dashboard screenshot via OpenRouter Vision API")
    parser.add_argument("image", help="Path to screenshot file")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Vision model ID")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="Analysis prompt")
    args = parser.parse_args()

    result = analyze_image(args.image, args.model, args.prompt)
    print(result)


if __name__ == "__main__":
    main()
