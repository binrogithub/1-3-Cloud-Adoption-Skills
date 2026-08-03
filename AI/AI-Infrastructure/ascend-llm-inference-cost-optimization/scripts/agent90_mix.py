#!/usr/bin/env python3
import argparse
import asyncio
import json
import random
import sys
from pathlib import Path

import aiohttp

sys.path.insert(0, str(Path(__file__).parent))
from kv64k_bench import (exact_prompt_factory, fetch_text, fetch_text_multi,
                         run_batch, sample_runtime_metrics)
from transformers import AutoTokenizer


def agent_prompt_factory(tokenizer_path, total_tokens, shared_tokens):
    tok = AutoTokenizer.from_pretrained(tokenizer_path, trust_remote_code=True)

    def make(session_id, turn_id):
        head = f"agent-session={session_id:06d}; persistent-history:"
        hn = len(tok.encode(head, add_special_tokens=False))
        shared = head + (" context" * (shared_tokens - hn))
        sn = len(tok.encode(shared, add_special_tokens=False))
        if sn != shared_tokens:
            shared += " context" * (shared_tokens - sn)
        tail_head = f" current-turn={turn_id:04d};"
        used = len(tok.encode(shared + tail_head, add_special_tokens=False))
        prompt = shared + tail_head + (" update" * (total_tokens - used))
        actual = len(tok.encode(prompt, add_special_tokens=False))
        if actual != total_tokens:
            prompt += " update" * (total_tokens - actual)
            actual = len(tok.encode(prompt, add_special_tokens=False))
        if actual != total_tokens:
            raise RuntimeError(f"wanted={total_tokens}, got={actual}")
        return prompt

    return make


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://vllm-host:8002/v1/completions")
    p.add_argument("--metrics-url", default="http://vllm-host:8002/metrics")
    p.add_argument("--master-metrics-url", default="http://vllm-host:9003/metrics")
    p.add_argument("--model", default="Qwen3.6-35B-A3B")
    p.add_argument("--tokenizer", default="/mnt/sfs_turbo/models/Qwen3.6-35B-A3B")
    p.add_argument("--concurrency", type=int, default=16)
    p.add_argument("--run-id", type=int, required=True,
                   help="unique namespace offset; prevents cross-run cache pollution")
    p.add_argument("--monthly-host-cost-usd", type=float, default=30000.0)
    p.add_argument("--pool-mult", type=int, default=1,
                   help="multiply measured request pool by this factor (2 -> 320 req for DP8)")
    p.add_argument("--dp-engines", type=int, default=4,
                   help="number of DP engines for rank modulo (4=DP4, 8=DP8)")
    p.add_argument("--hot-unique", type=int, default=0,
                   help="唯一热会话数(绝对值); 0=沿用 28*pool_mult。"
                        "复用次数自动推导为 112*pool_mult/hot_unique, 混合比例不变")
    p.add_argument("--output", required=True)
    args = p.parse_args()

    total = 65280
    shared = 58982  # 90.35% text identity; cache granularity is reported separately.
    make = agent_prompt_factory(args.tokenizer, total, shared)
    make_churn, churn_tokens = exact_prompt_factory(args.tokenizer, 65535)
    namespace = args.run_id * 10000
    mult = args.pool_mult
    ndp = args.dp_engines
    warm_ids = list(range(namespace, namespace + 32 * mult))
    # 热会话数解耦: --hot-unique 给绝对值, 否则沿用 28*mult。
    # 复用次数 = 112*mult / hot_unique, 保持 70% 热比例不变。
    n_hot_req = 112 * mult                     # 70% of 160*mult
    hot_unique = args.hot_unique or 28 * mult
    hot_reuse = n_hot_req // hot_unique
    hot_ids = list(range(namespace + 1000, namespace + 1000 + hot_unique))
    cold_ids = list(range(namespace + 2000, namespace + 2000 + 16 * mult))
    timeout = aiohttp.ClientTimeout(total=7200)

    def items(ids, turn):
        # rank 按会话 ID 派生 (sid % ndp), 保证同一会话永远落同一引擎 (会话亲和)。
        # 旧版用列表下标 i%ndp, hot_ids*R 会让同一会话在多个 rank 间跳, 亲和静默失效。
        return [(make(sid, turn), sid % ndp) for sid in ids]

    # F1 修复: 默认 TCPConnector(limit=100) 把所有 >C100 实验钳到 ~C100。
    # limit=0 = 无上限, 由 Semaphore(concurrency) 单点控制并发。
    conn = aiohttp.TCPConnector(limit=0, limit_per_host=0, ttl_dns_cache=300)
    async with aiohttp.ClientSession(timeout=timeout, connector=conn) as session:
        result = {
            "input_tokens": total,
            "output_tokens_per_request": 256,
            "shared_prompt_tokens": shared,
            "shared_prompt_ratio": shared / total,
            "mix": {"hbm": 112 * mult, "dram": 32 * mult, "cold": 16 * mult},
            "unique_sessions": {"hbm": hot_unique, "dram": 32 * mult, "cold": 16 * mult},
            "concurrency": args.concurrency,
            "run_id": args.run_id,
            "pool_mult": mult,
            "dp_engines": ndp,
        }
        def checkpoint():
            Path(args.output).write_text(json.dumps(result, indent=2), encoding="utf-8")

        result["warm_fill"] = await run_batch(session, args.url, args.model,
                                               items(warm_ids, 0), args.concurrency)
        checkpoint()
        # Interleave ranks so the first concurrency window exercises all DP
        # engines. Grouping by rank serializes the 64K churn across DPs.
        # F3 修复: churn 恒定 56 (不随 ndp 膨胀)。旧版 56×ndp 在 ndp=8 时
        # 写入 ~352GB 撑爆 Mooncake 池导致驱逐 warm 层。每引擎驱逐压力应恒定。
        churn = [(make_churn(f"churn64k-{args.run_id}", i), i % ndp)
                 for i in range(56)]
        result["eviction_pass"] = await run_batch(session, args.url, args.model,
                                                   churn, min(128, 64 * (ndp // 4)))
        checkpoint()
        result["hot_fill"] = await run_batch(session, args.url, args.model,
                                              items(hot_ids, 0), args.concurrency)
        checkpoint()

        measured = []
        measured.extend(items(hot_ids * hot_reuse, 1))
        measured.extend(items(warm_ids, 1))
        measured.extend(items(cold_ids, 1))
        random.Random(20260802).shuffle(measured)
        # 指标聚合: multi-port 下 --metrics-url 可为逗号分隔多端口, 聚合 8 引擎指标
        before_vllm = await fetch_text_multi(session, args.metrics_url)
        before_master = await fetch_text(session, args.master_metrics_url)
        stop = asyncio.Event()
        sampler = asyncio.create_task(sample_runtime_metrics(session, args.metrics_url, stop))
        result["measure"] = await run_batch(session, args.url, args.model,
                                             measured, args.concurrency, max_tokens=256)
        stop.set()
        samples = await sampler
        after_vllm = await fetch_text_multi(session, args.metrics_url)
        after_master = await fetch_text(session, args.master_metrics_url)
        result["runtime_max"] = {
            key: max((row[key] for row in samples), default=0)
            for key in ["kv_usage_max", "running", "waiting", "waiting_capacity", "waiting_deferred"]
        }
        result["metrics"] = {"vllm_before": before_vllm, "vllm_after": after_vllm,
                             "master_before": before_master, "master_after": after_master}
        # F3 验收门: measure 窗内 Mooncake 驱逐增量必须为 0, 否则缓存层塌陷, 该轮作废
        from kv64k_bench import metric_values
        evict_before = sum(metric_values(before_master, "master_evicted_size_bytes") or [0])
        evict_after = sum(metric_values(after_master, "master_evicted_size_bytes") or [0])
        result["mooncake_eviction_delta_bytes"] = evict_after - evict_before
        result["mooncake_eviction_gate"] = "PASS" if (evict_after - evict_before) == 0 else "FAIL_EVICTED"
        completion_tokens = result["measure"]["completion_tokens"]
        duration = result["measure"]["duration_s"]
        output_tps = completion_tokens / duration if duration else 0.0
        result["economics"] = {
            "monthly_host_cost_usd": args.monthly_host_cost_usd,
            "output_tokens_per_second": output_tps,
            "usd_per_million_output_tokens_at_100pct_utilization": (
                args.monthly_host_cost_usd / (output_tps * 2592000) * 1000000
                if output_tps else None
            ),
        }
        checkpoint()

    for value in result.values():
        if isinstance(value, dict):
            value.pop("rows", None)
    result.pop("metrics", None)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
