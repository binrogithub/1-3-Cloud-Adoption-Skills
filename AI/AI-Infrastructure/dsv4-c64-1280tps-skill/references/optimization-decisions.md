# Optimization Decisions — Why Each Choice Was Made

## Optimizations Applied (in order of impact)

### 1. Fused MC2 (`enable_fused_mc2=1`) — Main Effect +23%

**Why**: Profile showed MoeDistributeDispatchV2 alone occupies 59% of critical
path. Fused MC2 replaces the sequential dispatch → FFN → combine pipeline with
a fused `dispatch_ffn_combine/mega_moe` operator, directly attacking the
dominant cost.

**How**: Set `enable_fused_mc2=1` in `--additional-config`. This automatically
disables `multistream_overlap_shared_expert` (mutex enforced by code).

**Measurement**: 796 → 979 tok/s (+23.0%)

**Constraints**:
- Cannot coexist with `enable_mc2_hierarchy_comm` (startup crash)
- Forces `multistream_overlap_shared_expert=false`
- Replaces (not augments) the standard MC2 path

### 2. DSpark3 (`num_speculative_tokens=3`) — +53% cumulative

**Why**: At C64 high concurrency, DSpark7's 7 speculative tokens per sequence
create 64×8=512 tokens for verification per step. High rejection rate wastes
compute. DSpark3 reduces to 64×4=256, improving effective throughput.

**How**: Set `num_speculative_tokens=3` in `--speculative-config`.

**Measurement**: 979 → 1,221 tok/s (+24.5% incremental over Fused MC2)

**Constraints**:
- `num_spec + 1` must be divisible by `tensor_parallel_size` (TP4)
- Valid values: 3, 7, 11, 15... (DSpark5 = 6, not divisible by 4 → crash)

### 3. MLAPO (`enable_mlapo=1`) — +55% cumulative

**Why**: Multi-head Latent Attention Pool optimization reduces attention
computation overhead. SparseAttnSharedkv was 0.9% in profile — small but
MLAPO may also optimize memory access patterns.

**How**: Set `enable_mlapo=1` in `--additional-config`.

**Measurement**: 1,221 → 1,235 tok/s (+1.1% incremental, within noise but
consistent across runs)

### 4. DSA-CP (`enable_dsa_cp=true`) — +91% cumulative, +36% incremental

**Why**: DSA Compressor Pipeline enables overlapping DSA compression with
other computation. Previously caused regression when used alone with DSpark7
(642-710 tok/s), but produces strong synergy with Fused MC2 + DSpark3.

**How**: Set `enable_dsa_cp=true` in `--additional-config`.

**Measurement**: 1,235 → 1,523 tok/s (+23.3% incremental)

**Key insight**: This is a classic interaction effect. DSA-CP alone is harmful,
but with Fused MC2 (which changes the communication pattern) + DSpark3 (which
changes the batch composition), the three together create a positive synergy.
Single-factor A/B testing would have rejected DSA-CP and missed this gain.

## Optimizations Excluded (with evidence)

### seq64 + max-num-seqs=64 + batch16k
- **Result**: 838 tok/s (-15% vs Fused MC2 seq32)
- **Reason**: Larger batch lowers DSpark acceptance rate. More sequences compete
  for the same NPU resources, increasing rejection rate and wasting speculative
  compute. Historical data also showed seq64 = 632 tok/s (baseline).

### DSpark5 (num_spec=5)
- **Result**: Startup failure
- **Reason**: `num_spec + 1 = 6` not divisible by `tensor_parallel_size = 4`.
  Error: "Can't determine cudagraph shapes that are both a multiple of 6 and 4"

### enable_mc2_hierarchy_comm
- **Result**: Startup failure
- **Reason**: Mutually exclusive with `enable_fused_mc2`. Error: "fused mc2 op
  cannot be used with hierarchy communication"

### enforce_eager=false
- **Result**: Worse (historical, verified in prior testing)
- **Reason**: Drafter FULL ACLGraph is unstable/slower on DSV4

### CPU KV offload
- **Result**: Worse (historical)
- **Reason**: Fixed-ISL benchmark never triggers offload; connector has fixed
  overhead

### block32 + prefix-cache
- **Result**: Worse (historical)
- **Reason**: Fixed-ISL benchmark has no prefix reuse; block management overhead
  exceeds cache gain

### DSA-CP alone (without Fused MC2)
- **Result**: 642-710 tok/s (regression vs 796 baseline)
- **Reason**: Without Fused MC2 changing the communication pattern, DSA-CP
  adds overhead without benefit. Only works as part of the Fused MC2 + DSpark3
  combination.

## TP4 Compatibility Constraint

```
num_speculative5 + 1 must be divisible by tensor_parallel_size (4)

Valid:   num_spec=3  (4/4=1)  ✅
Valid:   num_spec=7  (8/4=2)  ✅
Valid:   num_spec=11 (12/4=3) ✅
Invalid: num_spec=5  (6%4=2)  ❌ startup crash
Invalid: num_spec=1  (2%4=2)  ❌ startup crash
```
