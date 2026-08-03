#!/usr/bin/env python3
import argparse
import asyncio
import json
import os
import re
import statistics
import time
from pathlib import Path

import aiohttp
from transformers import AutoTokenizer


async def fetch_text(session, url):
    try:
        async with session.get(url) as response:
            return await response.text()
    except Exception as exc:
        return f"ERROR: {exc!r}"


async def fetch_text_multi(session, urls):
    """聚合多个端口的 metrics 文本 (multi-port 模式下每端口只暴露自己引擎)。
    urls 可为逗号分隔字符串或列表。返回拼接文本, 各端口指标按 engine 标签区分。"""
    if isinstance(urls, str):
        urls = [u.strip() for u in urls.split(",") if u.strip()]
    texts = await asyncio.gather(*(fetch_text(session, u) for u in urls))
    return "\n".join(texts)


def metric_values(text, name, label=None):
    rows = []
    for line in text.splitlines():
        if not line.startswith(name):
            continue
        if label and label not in line:
            continue
        try:
            rows.append(float(line.rsplit(" ", 1)[1]))
        except (ValueError, IndexError):
            pass
    return rows


async def sample_runtime_metrics(session, url, stop):
    samples = []
    while not stop.is_set():
        # 多端口聚合: url 含逗号则 fetch_text_multi, 否则单端口
        if "," in str(url):
            text = await fetch_text_multi(session, url)
        else:
            text = await fetch_text(session, url)
        samples.append({
            "t": time.time(),
            "kv_usage_max": max(metric_values(text, "vllm:kv_cache_usage_perc") or [0]),
            "running": sum(metric_values(text, "vllm:num_requests_running{") or [0]),
            "waiting": sum(metric_values(text, "vllm:num_requests_waiting{") or [0]),
            "waiting_capacity": sum(metric_values(text, "vllm:num_requests_waiting_by_reason{", 'reason="capacity"') or [0]),
            "waiting_deferred": sum(metric_values(text, "vllm:num_requests_waiting_by_reason{", 'reason="deferred"') or [0]),
        })
        await asyncio.sleep(.1)
    return samples


def exact_prompt_factory(tokenizer_path, target_tokens):
    tok = AutoTokenizer.from_pretrained(tokenizer_path, trust_remote_code=True)

    def make(namespace, idx):
        header = f"cache-test={namespace};id={idx:06d};"
        header_n = len(tok.encode(header, add_special_tokens=False))
        prompt = header + (" x" * (target_tokens - header_n))
        actual = len(tok.encode(prompt, add_special_tokens=False))
        if actual != target_tokens:
            prompt += " x" * (target_tokens - actual)
            actual = len(tok.encode(prompt, add_special_tokens=False))
        if actual != target_tokens:
            raise RuntimeError(f"cannot build exact prompt: wanted={target_tokens}, got={actual}")
        return prompt

    sample = make("sample", 0)
    return make, len(tok.encode(sample, add_special_tokens=False))


def percentile(values, q):
    if not values:
        return None
    return sorted(values)[min(len(values) - 1, int(len(values) * q))]


def rank_url(url, rank):
    """会话亲和: 按 rank 选 multi-port 端口 (8002+rank)。
    url 形如 http://vllm-host:8002/v1/completions, 把端口 8002 换成 8002+rank。
    Internal-LB 模式 (单端口, 无 --data-parallel-multi-port-external-lb) 下必须禁用:
    设置环境变量 KV64K_DISABLE_RANK_URL=1 则所有请求回原端口 (8002), 不按 rank 改端口。"""
    if rank is None:
        return url
    if os.environ.get("KV64K_DISABLE_RANK_URL") == "1":
        return url
    import re
    m = re.search(r":(\d+)(/|$)", url)
    if not m:
        return url
    base_port = int(m.group(1))
    new_port = base_port + rank
    return url[:m.start(1)] + str(new_port) + url[m.end(1):]


async def issue(session, sem, url, model, prompt, rank, max_tokens=1):
    payload = {
        "model": model,
        "prompt": prompt,
        "max_tokens": max_tokens,
        "temperature": 0,
        "ignore_eos": True,
    }
    # 会话亲和: multi-port 模式下按 rank 选端口 (直接路由到对应 DP 引擎)
    target_url = rank_url(url, rank)
    t_enter = time.perf_counter()
    async with sem:
        # TTFT 计时点内移: t0 在拿到 sem 之后, 剔除客户端排队等待时间。
        t0 = time.perf_counter()
        queue_wait = t0 - t_enter
        for attempt in range(2):
          try:
            async with session.post(target_url, json=payload) as response:
                body = await response.json()
                elapsed = time.perf_counter() - t0
                if response.status != 200 or body.get("error"):
                    return {"ok": False, "latency_s": elapsed,
                            "client_queue_wait_s": queue_wait, "error": str(body)[:500]}
                usage = body.get("usage") or {}
                return {
                    "ok": True,
                    "latency_s": elapsed,
                    "client_queue_wait_s": queue_wait,
                    "prompt_tokens": int(usage.get("prompt_tokens") or 0),
                    "completion_tokens": int(usage.get("completion_tokens") or 0),
                }
          except Exception as exc:
            if attempt == 0:
                await asyncio.sleep(.2)
                continue
            return {"ok": False, "latency_s": time.perf_counter() - t0,
                    "client_queue_wait_s": queue_wait, "error": repr(exc)}


async def run_batch(session, url, model, items, concurrency, max_tokens=1):
    sem = asyncio.Semaphore(concurrency)
    started = time.perf_counter()
    rows = await asyncio.gather(*(
        issue(session, sem, url, model, prompt, rank, max_tokens) for prompt, rank in items
    ))
    duration = time.perf_counter() - started
    good = [r for r in rows if r["ok"]]
    lat = [r["latency_s"] for r in good]
    qw = [r.get("client_queue_wait_s", 0.0) for r in good]
    return {
        "requests": len(rows),
        "success": len(good),
        "errors": len(rows) - len(good),
        "duration_s": duration,
        "avg_ttft_s": statistics.mean(lat) if lat else None,
        "p50_ttft_s": percentile(lat, .50),
        "p95_ttft_s": percentile(lat, .95),
        "p99_ttft_s": percentile(lat, .99),
        "min_ttft_s": min(lat) if lat else None,
        "max_ttft_s": max(lat) if lat else None,
        "max_client_queue_wait_s": max(qw) if qw else 0.0,
        "prompt_tokens": sum(r.get("prompt_tokens", 0) for r in good),
        "completion_tokens": sum(r.get("completion_tokens", 0) for r in good),
        "error_samples": [r.get("error") for r in rows if not r["ok"]][:5],
        "rows": rows,
    }


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("stage", choices=["prepare-churn", "baseline", "dram-sweep"])
    p.add_argument("--url", default="http://vllm-host:8002/v1/completions")
    p.add_argument("--metrics-url", default="http://vllm-host:8002/metrics")
    p.add_argument("--master-metrics-url", default="http://vllm-host:9003/metrics")
    p.add_argument("--model", default="Qwen3.6-35B-A3B")
    p.add_argument("--tokenizer", default="/mnt/sfs_turbo/models/Qwen3.6-35B-A3B")
    p.add_argument("--input-tokens", type=int, default=65535)
    p.add_argument("--concurrency", type=int, default=1)
    p.add_argument("--requests", type=int, default=0,
                   help="measurement requests; defaults to concurrency")
    p.add_argument("--run-id", type=int, default=1)
    p.add_argument("--output", required=True)
    args = p.parse_args()

    make, sample_tokens = exact_prompt_factory(args.tokenizer, args.input_tokens)
    timeout = aiohttp.ClientTimeout(total=3600)
    # F1 修复: 默认 TCPConnector(limit=100) 把所有 >C100 实验钳到 ~C100。
    # limit=0 = 无上限, 由 Semaphore(concurrency) 单点控制并发。
    conn = aiohttp.TCPConnector(limit=0, limit_per_host=0, ttl_dns_cache=300)
    async with aiohttp.ClientSession(timeout=timeout, connector=conn) as session:
        result = {"stage": args.stage, "sample_prompt_tokens": sample_tokens,
                  "concurrency": args.concurrency, "run_id": args.run_id}

        if args.stage == "prepare-churn":
            # 56 full-context prefixes per DP exceed the ~53 x 64K local capacity.
            items = [(make("churn64k", rank * 56 + i), rank)
                     for rank in range(4) for i in range(56)]
            result["prepare_churn"] = await run_batch(session, args.url, args.model,
                                                       items, min(args.concurrency, 128))
        else:
            n = args.concurrency
            requests = args.requests or n
            result["requests"] = requests
            targets = [(make(f"target-{args.run_id}", i), i % 4) for i in range(requests)]
            if args.stage == "baseline":
                cold = [(make(f"cold-{args.run_id}", i), i % 4) for i in range(requests)]
                result["cold"] = await run_batch(session, args.url, args.model, cold, n)
                result["target_fill"] = await run_batch(session, args.url, args.model, targets, n)
                result["hbm_hit"] = await run_batch(session, args.url, args.model, targets, n)
            else:
                result["target_fill"] = await run_batch(session, args.url, args.model, targets, n)

            # Touch the entire prebuilt churn pool after target_fill. This makes
            # every target older than a >HBM-capacity working set on its DP rank.
            churn = [(make("churn64k", rank * 56 + i), rank)
                     for rank in range(4) for i in range(56)]
            result["eviction_pass"] = await run_batch(session, args.url, args.model,
                                                       churn, min(128, max(n, 32)))
            before_vllm = await fetch_text(session, args.metrics_url)
            before_master = await fetch_text(session, args.master_metrics_url)
            stop = asyncio.Event()
            sampler = asyncio.create_task(sample_runtime_metrics(session, args.metrics_url, stop))
            result["dram_hit"] = await run_batch(session, args.url, args.model, targets, n)
            stop.set()
            samples = await sampler
            after_vllm = await fetch_text(session, args.metrics_url)
            after_master = await fetch_text(session, args.master_metrics_url)
            result["runtime_samples"] = samples
            result["runtime_max"] = {
                key: max((row[key] for row in samples), default=0)
                for key in ["kv_usage_max", "running", "waiting", "waiting_capacity", "waiting_deferred"]
            }
            result["metrics"] = {
                "vllm_before": before_vllm,
                "vllm_after": after_vllm,
                "master_before": before_master,
                "master_after": after_master,
            }

    Path(args.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
    printable = {k: v for k, v in result.items() if k != "metrics"}
    for value in printable.values():
        if isinstance(value, dict):
            value.pop("rows", None)
    print(json.dumps(printable, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
