#!/usr/bin/env python3
"""
滚动预算演示脚本（中英双语输出），分两幕：
  第一幕：持续发请求，直到撞上第一层（5 分钟窗口）滚动预算，打印 429 详情；
  第二幕：每 15 秒重试一次，等最早的消费滑出 5 分钟窗口、额度自动恢复。

Bilingual (zh/en) rolling-budget demo in two acts:
  Act 1: keep sending requests until the tier-1 (5-minute window) rolling budget trips;
  Act 2: retry every 15s and watch the budget restore as old spend slides out.

用法 Usage：./demo.py [virtual-key]   （不传则读取 setup.py 生成的 .demo_key /
                                       defaults to .demo_key written by setup.py）
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.getenv("LITELLM_URL", "http://localhost:4000")

if len(sys.argv) > 1:
    KEY = sys.argv[1]
else:
    key_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".demo_key")
    try:
        KEY = open(key_path).read().strip()
    except FileNotFoundError:
        sys.exit(
            "找不到 demo/.demo_key，请先运行 ./setup.py，或把 key 作为参数传入\n"
            "demo/.demo_key not found — run ./setup.py first, or pass the key as an argument"
        )


def chat():
    """返回 (http状态码, 本次成本, 错误体) / returns (status, cost, error body)"""
    req = urllib.request.Request(
        f"{BASE}/v1/chat/completions",
        data=json.dumps(
            {"model": "demo-model", "messages": [{"role": "user", "content": "hi"}]}
        ).encode(),
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            cost = float(r.headers.get("x-litellm-response-cost") or 0)
            return r.status, cost, None
    except urllib.error.HTTPError as e:
        return e.code, 0.0, e.read().decode()


def ts():
    return time.strftime("%H:%M:%S")


total = 0.0
n = 0
print("══ 第一幕：持续发请求，直到 5 分钟滚动窗口的 $0.05 额度耗尽 ══")
print("══ Act 1: send requests until the 5-minute rolling window's $0.05 budget runs out ══\n")
while True:
    n += 1
    status, cost, err = chat()
    if status == 200:
        total += cost
        print(
            f"[{ts()}] #{n:>3}  200 OK    本次 cost=${cost:.4f}   "
            f"窗口内累计 window total≈${total:.4f}"
        )
        time.sleep(2)  # 留出 spend log 落库时间 / let the spend-log batch writer flush (1s)
    elif status == 429:
        print(f"\n[{ts()}] #{n:>3}  ❌ 429 — 被滚动预算拦截 / blocked by the rolling budget:")
        try:
            detail = json.loads(err)
            print(json.dumps(detail, indent=2, ensure_ascii=False))
        except (json.JSONDecodeError, TypeError):
            print(err)
        break
    else:
        sys.exit(f"[{ts()}] #{n} 意外状态码 unexpected status {status}: {err}")

print("\n══ 第二幕：每 15 秒重试 —— 观察额度随窗口滑动自动恢复 ══")
print("══ Act 2: retry every 15s — watch the budget restore as the window slides ══")
print("（无需等整点重置：最早那笔消费满 5 分钟滑出窗口的瞬间，额度就回来了）")
print("(No fixed reset to wait for: budget returns the moment the oldest spend"
      " slides out of the 5-minute window)\n")
while True:
    time.sleep(15)
    status, cost, err = chat()
    if status == 200:
        print(f"[{ts()}] ✅ 200 OK — 最早的消费已滑出 5 分钟窗口，额度自动恢复！")
        print(f"[{ts()}] ✅ 200 OK — the oldest spend slid out of the 5-minute window,"
              " budget restored automatically!")
        print("\n演示结束。这就是滚动窗口与固定周期重置的区别。")
        print("Demo complete. That's the difference between a sliding window and a fixed reset.")
        break
    print(f"[{ts()}] 仍然 429 — 等待旧消费滑出窗口… / still 429 — waiting for old spend"
          " to slide out of the window…")
