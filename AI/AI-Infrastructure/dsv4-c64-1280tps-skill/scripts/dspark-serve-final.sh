#!/usr/bin/env bash
# DSV4-Flash C64 >1280 TPS Final Optimized Configuration
# Result: 1531 tok/s aggregate (23.9 tok/s/concurrency), CV=2.3%
# Optimizations: Fused MC2 + DSpark3 + MLAPO + DSA-CP
source /usr/local/Ascend/ascend-toolkit/set_env.sh 2>/dev/null || true
source /usr/local/Ascend/cann-9.0.0/share/info/ascendnpu-ir/bin/set_env.sh 2>/dev/null || true
source /usr/local/Ascend/nnal/atb/set_env.sh 2>/dev/null || true
export LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libjemalloc.so.2:${LD_PRELOAD:-}
exec vllm serve /data/models/DeepSeek-V4-Flash-0731-w8a8 \
  --host 0.0.0.0 --port 6697 \
  --served-model-name DeepSeek-V4-Flash-0731-w8a8 \
  --tensor-parallel-size 4 --data-parallel-size 4 \
  --enable-expert-parallel \
  --quantization ascend \
  --tokenizer-mode deepseek_v4 \
  --tool-call-parser deepseek_v4 --enable-auto-tool-choice \
  --reasoning-parser deepseek_v4 \
  --trust-remote-code \
  --max-model-len 131072 \
  --max-num-batched-tokens 8192 \
  --max-num-seqs 32 \
  --gpu-memory-utilization 0.90 \
  --block-size 128 \
  --safetensors-load-strategy prefetch \
  --no-enable-prefix-caching \
  --async-scheduling \
  --speculative-config "{\"method\":\"dspark\",\"num_speculative_tokens\":3,\"enforce_eager\":true}" \
  --compilation-config "{\"cudagraph_mode\":\"FULL_DECODE_ONLY\"}" \
  --additional-config "{\"ascend_compilation_config\":{\"enable_npugraph_ex\":true,\"enable_static_kernel\":false},\"enable_cpu_binding\":true,\"multistream_overlap_shared_expert\":false,\"enable_dsa_cp\":true,\"enable_fused_mc2\":1,\"enable_mlapo\":1}"
