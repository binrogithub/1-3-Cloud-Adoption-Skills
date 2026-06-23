import requests
import time
import json
import sys
import os
import concurrent.futures
from dotenv import load_dotenv

load_dotenv()

URL = os.getenv("OPENAI_BASE_URL", "https://api-ap-southeast-1.modelarts-maas.com/openai").rstrip("/") + "/v1/chat/completions"
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}"
}
MODELS = [
    "deepseek-v4-flash",
    "DeepSeek-V3",
    "glm-5.1",
    "glm-5",
    "qwen3-32b",
    "deepseek-v3.2",
    "deepseek-v3.1-terminus",
]
NUM_CALLS = 10
PROMPT = "hello"
MAX_TOKENS = 250

def run_call(model, call_idx):
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": MAX_TOKENS,
        "stream": True,
    }

    start = time.perf_counter()
    first_token_time = None
    token_times = []
    output_tokens = 0
    input_tokens = 0

    try:
        resp = requests.post(URL, headers=HEADERS, json=payload, stream=True, timeout=120)
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

            usage = chunk.get("usage")
            if usage:
                input_tokens = usage.get("prompt_tokens", input_tokens)
                output_tokens = usage.get("completion_tokens", output_tokens)

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

        end = time.perf_counter()

        # Count output tokens from streaming if usage didn't report
        stream_tokens = len(token_times)
        if output_tokens == 0:
            output_tokens = stream_tokens

        e2e_ms = (end - start) * 1000
        tft_ms = (first_token_time - start) * 1000 if first_token_time else None

        # Incremental token latency (avg ms between tokens after first)
        if len(token_times) > 1:
            intervals = [(token_times[j] - token_times[j-1]) * 1000 for j in range(1, len(token_times))]
            inc_token_ms = sum(intervals) / len(intervals)
        else:
            inc_token_ms = None

        # k input tokens/sec = input_tokens / tft_seconds / 1000
        if tft_ms and tft_ms > 0 and input_tokens > 0:
            k_input_tok_s = input_tokens / (tft_ms / 1000) / 1000
        else:
            k_input_tok_s = None

        # k output tokens/sec = output_tokens / generation_seconds / 1000
        gen_time_ms = e2e_ms - tft_ms if tft_ms else None
        if gen_time_ms and gen_time_ms > 0 and output_tokens > 0:
            k_output_tok_s = output_tokens / (gen_time_ms / 1000) / 1000
        else:
            k_output_tok_s = None

        return {
            "call": call_idx + 1,
            "e2e_ms": e2e_ms,
            "tft_ms": tft_ms,
            "inc_token_ms": inc_token_ms,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "k_input_tok_s": k_input_tok_s,
            "k_output_tok_s": k_output_tok_s,
        }
    except Exception as e:
        return {
            "call": call_idx + 1,
            "e2e_ms": None, "tft_ms": None, "inc_token_ms": None,
            "input_tokens": 0, "output_tokens": 0,
            "k_input_tok_s": None, "k_output_tok_s": None,
            "error": str(e),
        }

def benchmark_model(model):
    print(f"\n{'='*90}")
    print(f"Model: {model}")
    print(f"{'='*90}")

    results = []
    for i in range(NUM_CALLS):
        print(f"  Call {i+1}/{NUM_CALLS}...", end="", flush=True)
        r = run_call(model, i)
        results.append(r)
        status = "OK" if r["e2e_ms"] is not None else f"ERR: {r.get('error','')[:40]}"
        print(f" {status} ({r['e2e_ms']:.0f}ms)" if r["e2e_ms"] else f" {status}")

    # Table
    print(f"\n  {'#':>2}  {'E2E ms':>8}  {'TFT ms':>8}  {'Inc ms':>7}  {'In tok':>6}  {'Out tok':>7}  {'K in/s':>7}  {'K out/s':>8}")
    print(f"  {'-'*70}")

    valid = {k: [] for k in ["e2e_ms", "tft_ms", "inc_token_ms", "k_input_tok_s", "k_output_tok_s"]}
    for r in results:
        e2e = f"{r['e2e_ms']:.0f}" if r['e2e_ms'] is not None else "ERR"
        tft = f"{r['tft_ms']:.0f}" if r['tft_ms'] is not None else "-"
        inc = f"{r['inc_token_ms']:.1f}" if r['inc_token_ms'] is not None else "-"
        ki = f"{r['k_input_tok_s']:.2f}" if r['k_input_tok_s'] is not None else "-"
        ko = f"{r['k_output_tok_s']:.2f}" if r['k_output_tok_s'] is not None else "-"
        print(f"  {r['call']:>2}  {e2e:>8}  {tft:>8}  {inc:>7}  {r['input_tokens']:>6}  {r['output_tokens']:>7}  {ki:>7}  {ko:>8}")
        for k in valid:
            if r.get(k) is not None:
                valid[k].append(r[k])

    # Averages
    if valid["e2e_ms"]:
        avg = lambda lst: sum(lst)/len(lst)
        p50 = lambda lst: sorted(lst)[len(lst)//2]
        print(f"  {'-'*70}")
        ae = avg(valid["e2e_ms"])
        at = avg(valid["tft_ms"]) if valid["tft_ms"] else 0
        ai = avg(valid["inc_token_ms"]) if valid["inc_token_ms"] else 0
        aki = avg(valid["k_input_tok_s"]) if valid["k_input_tok_s"] else 0
        ako = avg(valid["k_output_tok_s"]) if valid["k_output_tok_s"] else 0
        print(f"  {'AVG':>2}  {ae:>8.0f}  {at:>8.0f}  {ai:>7.1f}  {'':>6}  {'':>7}  {aki:>7.2f}  {ako:>8.2f}")
        print(f"  {'P50':>2}  {p50(valid['e2e_ms']):>8.0f}  {p50(valid['tft_ms']):>8.0f}")

    return model, valid

# Run models sequentially (to avoid rate limits), calls sequentially within each model
all_summary = {}
for model in MODELS:
    model_name, valid = benchmark_model(model)
    if valid["e2e_ms"]:
        avg = lambda lst: sum(lst)/len(lst)
        p50 = lambda lst: sorted(lst)[len(lst)//2]
        all_summary[model_name] = {
            "e2e_avg": avg(valid["e2e_ms"]),
            "e2e_p50": p50(valid["e2e_ms"]),
            "tft_avg": avg(valid["tft_ms"]) if valid["tft_ms"] else 0,
            "inc_avg": avg(valid["inc_token_ms"]) if valid["inc_token_ms"] else 0,
            "k_in_avg": avg(valid["k_input_tok_s"]) if valid["k_input_tok_s"] else 0,
            "k_out_avg": avg(valid["k_output_tok_s"]) if valid["k_output_tok_s"] else 0,
        }

# Final comparison table
print("\n\n" + "=" * 110)
print("COMPARISON SUMMARY (averages over 10 calls)")
print("=" * 110)
print(f"{'Model':<25}  {'E2E avg':>8}  {'E2E p50':>8}  {'TFT avg':>8}  {'Inc tok':>8}  {'K in/s':>8}  {'K out/s':>9}")
print("-" * 110)
for model in MODELS:
    s = all_summary.get(model)
    if not s:
        print(f"{model:<25}  {'FAILED':>8}")
        continue
    print(f"{model:<25}  {s['e2e_avg']:>8.0f}  {s['e2e_p50']:>8.0f}  {s['tft_avg']:>8.0f}  {s['inc_avg']:>8.1f}  {s['k_in_avg']:>8.2f}  {s['k_out_avg']:>9.2f}")
