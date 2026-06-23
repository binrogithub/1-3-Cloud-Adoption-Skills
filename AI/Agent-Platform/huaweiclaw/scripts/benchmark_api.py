import requests
import time
import json
import sys
import os
from dotenv import load_dotenv

load_dotenv()

URL = os.getenv("OPENAI_BASE_URL", "https://api-ap-southeast-1.modelarts-maas.com/openai").rstrip("/") + "/v1/chat/completions"
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}"
}
PAYLOAD = {
    "model": "qwen3-32b",
    "messages": [{"role": "user", "content": "hello"}],
    "max_tokens": 250,
    "stream": True
}

NUM_CALLS = 10
results = []

for i in range(NUM_CALLS):
    print(f"Call {i+1}/{NUM_CALLS}...", flush=True)

    start = time.perf_counter()
    first_token_time = None
    token_times = []
    token_count = 0
    cached = None

    try:
        resp = requests.post(URL, headers=HEADERS, json=PAYLOAD, stream=True, timeout=60)
        resp.raise_for_status()

        for line in resp.iter_lines():
            if not line:
                continue
            line = line.decode("utf-8")
            if not line.startswith("data: "):
                continue
            data = line[6:]
            if data.strip() == "[DONE]":
                break

            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue

            # Check for cache info in usage
            if "usage" in chunk and chunk["usage"]:
                usage = chunk["usage"]
                if "prompt_tokens_details" in usage:
                    details = usage["prompt_tokens_details"]
                    if "cached_tokens" in details:
                        cached = details["cached_tokens"]

            choices = chunk.get("choices", [])
            if not choices:
                continue

            delta = choices[0].get("delta", {})
            content = delta.get("content", "")
            if content:
                now = time.perf_counter()
                if first_token_time is None:
                    first_token_time = now
                token_times.append(now)
                token_count += 1

        end = time.perf_counter()

        e2e_ms = (end - start) * 1000
        tft_ms = (first_token_time - start) * 1000 if first_token_time else None

        # Incremental token latency: average ms between tokens (after first)
        if len(token_times) > 1:
            intervals = [(token_times[j] - token_times[j-1]) * 1000 for j in range(1, len(token_times))]
            inc_token_ms = sum(intervals) / len(intervals)
        else:
            inc_token_ms = None

        # Throughput in k tokens/sec
        if token_count > 0 and e2e_ms > 0:
            k_tokens = token_count / (e2e_ms / 1000) / 1000  # k tokens/sec
        else:
            k_tokens = None

        # Cache hit rate
        if cached is not None:
            total_prompt = chunk.get("usage", {}).get("prompt_tokens", 0)
            cache_hit_rate = cached / total_prompt if total_prompt > 0 else 0.0
        else:
            cache_hit_rate = None

        results.append({
            "call": i + 1,
            "e2e_ms": e2e_ms,
            "tft_ms": tft_ms,
            "inc_token_ms": inc_token_ms,
            "token_count": token_count,
            "k_tokens_per_sec": k_tokens,
            "cache_hit_rate": cache_hit_rate,
        })

    except Exception as e:
        print(f"  ERROR: {e}")
        results.append({
            "call": i + 1,
            "e2e_ms": None,
            "tft_ms": None,
            "inc_token_ms": None,
            "token_count": 0,
            "k_tokens_per_sec": None,
            "cache_hit_rate": None,
            "error": str(e),
        })

# Print results table
print("\n" + "=" * 100)
print(f"{'Call':>4}  {'E2E (ms)':>10}  {'TFT (ms)':>10}  {'Inc Token (ms)':>15}  {'Tokens':>7}  {'K tok/s':>8}  {'Cache Hit':>10}")
print("-" * 100)

valid = {k: [] for k in ["e2e_ms", "tft_ms", "inc_token_ms", "k_tokens_per_sec", "cache_hit_rate"]}

for r in results:
    e2e = f"{r['e2e_ms']:.1f}" if r['e2e_ms'] is not None else "N/A"
    tft = f"{r['tft_ms']:.1f}" if r['tft_ms'] is not None else "N/A"
    inc = f"{r['inc_token_ms']:.2f}" if r['inc_token_ms'] is not None else "N/A"
    ktk = f"{r['k_tokens_per_sec']:.3f}" if r['k_tokens_per_sec'] is not None else "N/A"
    ch = f"{r['cache_hit_rate']:.1%}" if r['cache_hit_rate'] is not None else "N/A"

    print(f"{r['call']:>4}  {e2e:>10}  {tft:>10}  {inc:>15}  {r['token_count']:>7}  {ktk:>8}  {ch:>10}")

    for k in valid:
        if r.get(k) is not None:
            valid[k].append(r[k])

print("-" * 100)

# Averages
if valid["e2e_ms"]:
    avg_e2e = sum(valid["e2e_ms"]) / len(valid["e2e_ms"])
    avg_tft = sum(valid["tft_ms"]) / len(valid["tft_ms"]) if valid["tft_ms"] else 0
    avg_inc = sum(valid["inc_token_ms"]) / len(valid["inc_token_ms"]) if valid["inc_token_ms"] else 0
    avg_ktk = sum(valid["k_tokens_per_sec"]) / len(valid["k_tokens_per_sec"]) if valid["k_tokens_per_sec"] else 0
    avg_ch = sum(valid["cache_hit_rate"]) / len(valid["cache_hit_rate"]) if valid["cache_hit_rate"] else 0

    print(f"{'AVG':>4}  {avg_e2e:>10.1f}  {avg_tft:>10.1f}  {avg_inc:>15.2f}  {'':>7}  {avg_ktk:>8.3f}  {avg_ch:>10.1%}")
    print(f"\nSummary (over {len(valid['e2e_ms'])} successful calls):")
    print(f"  E2E Latency:          {avg_e2e:.1f} ms  (p50={sorted(valid['e2e_ms'])[len(valid['e2e_ms'])//2]:.1f})")
    print(f"  TFT (Time to First):  {avg_tft:.1f} ms  (p50={sorted(valid['tft_ms'])[len(valid['tft_ms'])//2]:.1f})")
    print(f"  Inc Token Latency:    {avg_inc:.2f} ms/token")
    print(f"  Throughput:           {avg_ktk:.3f} k tokens/sec")
    print(f"  Cache Hit Rate:       {avg_ch:.1%}" if valid["cache_hit_rate"] else "  Cache Hit Rate:       not reported by API")
