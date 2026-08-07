# DSV4 DSpark Deployment Pitfalls (Verified)

Each pitfall below was hit during deployment and confirmed with a root-cause
fix. Follow the fix column to avoid repeating.

## 1. Wrong image version — DSpark unsupported

**Symptom**
```
vllm serve: error: argument --speculative-config/-sc: Value method:dspark cannot be converted to <function loads at ...>
```
or `mtp` method:
```
KeyError: 'mtp.0.head.weight'
```

**Root cause**: The `v0.22.1rc1-a3` image does NOT contain `dspark_proposer.py`
(only `mtp` method). The 0731 weights are a DSpark model with no
`mtp.0.head.weight`, so `method:mtp` also fails.

**Fix**: Use `quay.io/ascend/vllm-ascend:DeepSeekV4-flash-0731-a3` (vLLM 0.25.1+).
Verify:
```bash
docker run --rm <image> find / -name "dspark_proposer*"
```

## 2. JSON quoting broken by bash heredoc

**Symptom**
```
argument --speculative-config/-sc: Value method:dspark cannot be converted
Invalid JSON: key must be a string at line 1 column 2
input_value='{kv_connector:RecomputeC...}'   # note: no quotes
```

**Root cause**: Passing `--speculative-config '{"method":"dspark",...}'` through
`docker run ... bash -c '... --speculative-config '"'"'{"method":...}'"'"' ...'`
loses the inner double-quotes after bash expansion. The JSON arrives as
`{method:dspark,...}` (unquoted keys).

**Fix**: Write the full `vllm serve` command to a script file
(`/root/dspark-serve.sh`) using a quoted heredoc `<<"SERVE"`, then mount it into
the container and run `bash /dspark-serve.sh`. The heredoc with quoted delimiter
prevents all expansion.

## 3. enable_multithread_load must be bool

**Symptom**
```
ValueError: enable_multithread_load must be a bool, got str
```

**Root cause**: v0.22.1rc1 accepted `"enable_multithread_load":"true"` (string);
v0.25.1 strict-types it to bool.

**Fix**: Use `"enable_multithread_load":true` (no quotes around true).

## 4. multithread_load incompatible with prefetch

**Symptom**
```
ValueError: enable_multithread_load does not support safetensors_load_strategy='prefetch'; the multi-thread loader only implements the default lazy strategy.
```

**Root cause**: v0.25.1 forbids combining multithread load with the prefetch
safetensors strategy.

**Fix**: Remove `--model-loader-extra-config` entirely. Keep
`--safetensors-load-strategy prefetch` (faster for 294GB model). Load is slightly
slower without multithread but succeeds.

## 5. Connector name is the registration key, not the class name

**Symptom**
```
Unsupported connector type: RecomputeCPUOffloadConnectorV1
```

**Root cause**: The class is `RecomputeCPUOffloadConnectorV1` but it is
registered under the key `RecomputeCPUOffloadConnector`. The `--kv-transfer-config`
`kv_connector` field takes the registration key.

**Fix**:
```json
{"kv_connector":"RecomputeCPUOffloadConnector", ...}
```
Check the registry:
```bash
docker run --rm <image> grep -n "register_connector" \
  /vllm-workspace/vllm-ascend/vllm_ascend/distributed/kv_transfer/__init__.py
```

## 6. Image pull unstable from inference host

**Symptom**: `docker pull` hangs on `Retrying in N second` for hours; layers
download but never `Pull complete`.

**Fix**: Wrap in a retry loop and let docker reuse cached layers:
```bash
for i in 1 2 3 4 5; do
  docker pull quay.io/ascend/vllm-ascend:DeepSeekV4-flash-0731-a3 && break
  echo "attempt $i failed, retry"; sleep 10
done
```
If the inference host's egress to quay.io is persistently bad, pull on a host
with better connectivity, then `docker save | ssh docker load` (note: this needs
~7GB free on the relay host and is bandwidth-limited by the relay→inference link).

## 7. Old Qwen containers occupying NPU die

**Symptom**: `RuntimeError: torch_npu detected, but NPU device is not available`
+ `dcmi model initialized failed, because the device is used. ret is -8020`

**Root cause**: Previous Qwen sglang containers still hold the die.

**Fix**: `docker stop` / `docker rm -f` all containers using `/dev/davinci*`
before launching DSV4. Verify with `npu-smi info` (all die should show 0% AICore
and low HBM before launch).
