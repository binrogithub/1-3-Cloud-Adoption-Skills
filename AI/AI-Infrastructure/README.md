# AI Infrastructure

This use case covers the compute and platform foundation required for AI workloads, including training, inference, dedicated AI compute, and hybrid cloud AI deployment patterns. It supports the operational layer beneath model development and serving.

## Typical Skill Areas

- AI compute environment planning
- Training and inference environment design
- Dedicated AI infrastructure planning
- Hybrid cloud AI deployment
- Capacity and environment governance

## Skills

| Skill | Description |
|---|---|
| [detectron2-ascend-demo](./detectron2-ascend-demo.md) | Deploy and test detectron2 on Huawei Ascend 910B3 NPU (ModelArts) with COCO val2017 and OGNet oil/gas refinery inference demos. |
| [ascend-llm-inference-cost-optimization](./ascend-llm-inference-cost-optimization/) | Cut LLM inference token cost on Ascend 910 NPUs with vLLM-Ascend: 16-die DP/TP/EP topology, Mooncake CPU-DRAM KV tier, session affinity, and concurrency tuning. Measured USD 24.77 → 13.96 per million output tokens on a 64K-context agent workload. |
| [sglang-qwen36-ascend-best-practice](./sglang-qwen36-ascend-best-practice/) | Serve Qwen3.6-35B-A3B with SGLang on 16-die Ascend 910: hybrid topology (TP16 single engine at C1, TP2/DP8 sticky at C4+), BF16 + NEXTN speculative decoding. All 12 measured points (3 scenarios × 4 concurrency) beat the prior best by +4% to +153%. |
| [dsv4-dspark-ascend-a3](./dsv4-dspark-ascend-a3/) | Deploy and benchmark DeepSeek-V4-Flash-0731 W8A8 with DSpark speculative decoding on 16-die Ascend A3 (vLLM-Ascend 0.25.1, TP4+DP4). Measured 1.96–2.91× output tok/s per user over the no-spec-decode baseline at low concurrency, with ITL down 41–62%; includes five single-factor optimizations that were tested and rejected. |

## Expected Outputs

- AI infrastructure architecture
- Environment deployment baseline
- Capacity and operations plan
- Validation checklist for AI workloads
