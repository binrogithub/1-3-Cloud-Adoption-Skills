#!/usr/bin/env python3
"""Compute three cost ($/M) metrics from an agent90_mix result JSON.
Reads metrics.vllm_before/after prefix_cache_hits_total (local HBM) and
external_prefix_cache_hits_total (Mooncake DRAM) deltas, plus measure
prompt_tokens/completion_tokens/duration_s."""
import json, re, sys

def sum_counter(text, name):
    total = 0.0
    for line in text.splitlines():
        if not line.startswith(name):
            continue
        try:
            total += float(line.rsplit(' ', 1)[1])
        except (ValueError, IndexError):
            pass
    return total

def main(path):
    d = json.load(open(path))
    m = d['measure']
    metrics = d['metrics']
    vb, va = metrics['vllm_before'], metrics['vllm_after']
    # local HBM prefix cache hits
    local_before = sum_counter(vb, 'vllm:prefix_cache_hits_total')
    local_after = sum_counter(va, 'vllm:prefix_cache_hits_total')
    local_hits = local_after - local_before
    # external (Mooncake DRAM) prefix cache hits
    ext_before = sum_counter(vb, 'vllm:external_prefix_cache_hits_total')
    ext_after = sum_counter(va, 'vllm:external_prefix_cache_hits_total')
    ext_hits = ext_after - ext_before
    prompt_tokens = m['prompt_tokens']
    completion_tokens = m['completion_tokens']
    duration = m['duration_s']
    total_input_cached = local_hits + ext_hits
    non_cached_input = prompt_tokens - total_input_cached
    if non_cached_input < 0:
        non_cached_input = 0
    monthly = d.get('economics',{}).get('monthly_host_cost_usd', 30000.0)
    def cost_per_m(tokens_per_sec):
        return monthly / (tokens_per_sec * 2592000) * 1e6 if tokens_per_sec else None
    # 1. full face value: all tokens (cached input full price) / duration
    full_tokens = (prompt_tokens + completion_tokens) / duration
    cost_full = cost_per_m(full_tokens)
    # 2. cached input at 10%: (non_cached_input + output + cached_input*0.1)/duration
    billable_10 = (non_cached_input + completion_tokens + total_input_cached * 0.1) / duration
    cost_10 = cost_per_m(billable_10)
    # 3. strict: (non_cached_input + output)/duration
    strict_tokens = (non_cached_input + completion_tokens) / duration
    cost_strict = cost_per_m(strict_tokens)
    out = {
        'prompt_tokens': prompt_tokens,
        'completion_tokens': completion_tokens,
        'duration_s': round(duration, 2),
        'local_prefix_cache_hits': int(local_hits),
        'external_prefix_cache_hits': int(ext_hits),
        'total_cached_input': int(total_input_cached),
        'non_cached_input': int(non_cached_input),
        'output_tps': round(completion_tokens / duration, 2),
        'cost_full_face_value_per_M': round(cost_full, 4),
        'cost_cached_at_10pct_per_M': round(cost_10, 4),
        'cost_strict_per_M': round(cost_strict, 4),
        'cache_hit_rate_pct': round(total_input_cached / prompt_tokens * 100, 2) if prompt_tokens else 0,
    }
    print(json.dumps(out, indent=2))
    return out

if __name__ == '__main__':
    main(sys.argv[1])
