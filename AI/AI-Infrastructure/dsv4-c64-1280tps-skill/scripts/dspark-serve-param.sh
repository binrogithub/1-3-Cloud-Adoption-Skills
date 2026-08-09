#!/usr/bin/env bash
source /usr/local/Ascend/ascend-toolkit/set_env.sh 2>/dev/null || true
source /usr/local/Ascend/cann-9.0.0/share/info/ascendnpu-ir/bin/set_env.sh 2>/dev/null || true
source /usr/local/Ascend/nnal/atb/set_env.sh 2>/dev/null || true
export LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libjemalloc.so.2:${LD_PRELOAD:-}

# Parameters (with defaults)
TP=${TP:-4}
DP=${DP:-4}
MAX_SEQS=${MAX_SEQS:-32}
MAX_BATCH_TOKENS=${MAX_BATCH_TOKENS:-8192}
NUM_SPEC=${NUM_SPEC:-7}
FUSED_MC2=${FUSED_MC2:-0}
DSA_CP=${DSA_CP:-0}
MULTISTREAM=${MULTISTREAM:-1}
STATIC_KERNEL=${STATIC_KERNEL:-0}
GPU_MEM_UTIL=${GPU_MEM_UTIL:-0.90}
ENABLE_MLAPO=${ENABLE_MLAPO:-0}
ENABLE_PREFILL_MC2=${ENABLE_PREFILL_MC2:-0}

ADDITIONAL="{\"ascend_compilation_config\":{\"enable_npugraph_ex\":true,\"enable_static_kernel\":${STATIC_KERNEL}},\"enable_cpu_binding\":true,\"multistream_overlap_shared_expert\":${MULTISTREAM},\"enable_dsa_cp\":${DSA_CP},\"enable_fused_mc2\":${FUSED_MC2},\"enable_mlapo\":${ENABLE_MLAPO},\"enable_prefill_mc2\":${ENABLE_PREFILL_MC2}}"

exec vllm serve /data/models/DeepSeek-V4-Flash-0731-w8a8 \
  --host 0.0.0.0 --port 6697 \
  --served-model-name DeepSeek-V4-Flash-0731-w8a8 \
  --tensor-parallel-size ${TP} --data-parallel-size ${DP} \
  --enable-expert-parallel \
  --quantization ascend \
  --tokenizer-mode deepseek_v4 \
  --tool-call-parser deepseek_v4 --enable-auto-tool-choice \
  --reasoning-parser deepseek_v4 \
  --trust-remote-code \
  --max-model-len 131072 \
  --max-num-batched-tokens ${MAX_BATCH_TOKENS} \
  --max-num-seqs ${MAX_SEQS} \
  --gpu-memory-utilization ${GPU_MEM_UTIL} \
  --block-size 128 \
  --safetensors-load-strategy prefetch \
  --no-enable-prefix-caching \
  --async-scheduling \
  --speculative-config "{\"method\":\"dspark\",\"num_speculative_tokens\":${NUM_SPEC},\"enforce_eager\":true}" \
  --compilation-config "{\"cudagraph_mode\":\"FULL_DECODE_ONLY\"}" \
  --additional-config "${ADDITIONAL}"
