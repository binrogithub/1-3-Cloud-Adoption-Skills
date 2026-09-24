#!/usr/bin/env python3
"""Playwright UI-latency A/B (PRD V6 follow-up): same question through the real
UI, sampling the live-strip stages. Isolates the retrieval leg (click -> 'evidence:
N page(s)') which is what the MCP transport changed."""
import json, sys, time
from playwright.sync_api import sync_playwright

Q = "What is the maximum size of a single OBS object?"

def one_round(page):
    page.goto("https://localhost:8444/llmwiki", wait_until="domcontentloaded", timeout=20000)
    page.wait_for_timeout(1000)
    page.fill("[data-testid=ask-input]", Q)
    t0 = time.time()
    page.locator("[data-testid=ask-button]").click()
    marks = {}
    while time.time() - t0 < 90:
        strip = ""
        if page.locator("[data-testid=live-strip] p").count():
            strip = page.locator("[data-testid=live-strip] p").inner_text()
        if "evidence:" in strip and "evidence" not in marks:
            marks["evidence"] = time.time() - t0
        if "thinking" in strip and "thinking" not in marks:
            marks["thinking"] = time.time() - t0
        if "verifying" in strip and "provisional" not in marks:
            marks["provisional"] = time.time() - t0
        if page.locator("text=/grounded|partially_verified|abstained|no_claims/").count():
            marks["final"] = time.time() - t0
            break
        page.wait_for_timeout(250)
    return marks

def run(label, n):
    out = []
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(ignore_https_errors=True, viewport={"width": 1280, "height": 950})
        page = ctx.new_page()
        for i in range(n):
            out.append(one_round(page))
        b.close()
    print(f"[{label}]")
    for i, m in enumerate(out):
        print(f"  round{i+1}: " + "  ".join(f"{k}={v:.2f}s" for k, v in m.items()))
    leg = [m.get("evidence") for m in out if "evidence" in m]
    if leg:
        print(f"  retrieval leg (click->evidence): median {sorted(leg)[len(leg)//2]:.2f}s")
    return out

if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "run", int(sys.argv[2]) if len(sys.argv) > 2 else 2)
