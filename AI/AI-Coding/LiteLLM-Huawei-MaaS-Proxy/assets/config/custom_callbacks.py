"""
Custom LiteLLM callback that emits TTFT, TPOT, and ITL as Prometheus histograms.

These metrics are registered on the default prometheus_client REGISTRY,
so they appear alongside built-in metrics on the /metrics endpoint.

TTFT  = completion_start_time - api_call_start_time  (streaming only)
TPOT  = total_latency / output_tokens
ITL   = (end_time - completion_start_time) / max(output_tokens - 1, 1)  (streaming only)
"""

from datetime import datetime
from litellm.integrations.custom_logger import CustomLogger
from prometheus_client import Histogram


def _to_timestamp(val):
    """Convert datetime or numeric to a float unix timestamp."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if hasattr(val, "timestamp"):
        return val.timestamp()
    return None


class PrometheusTTFTTPOTITL(CustomLogger):
    """Custom callback that emits TTFT, TPOT, and ITL as Prometheus histograms."""

    def __init__(self):
        super().__init__()

        self.ttft = Histogram(
            "litellm_custom_ttft_seconds",
            "Time to first token in seconds (streaming only)",
            labelnames=["model", "model_group", "api_provider"],
            buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
        )

        self.tpot = Histogram(
            "litellm_custom_tpot_seconds",
            "Time per output token in seconds",
            labelnames=["model", "model_group", "api_provider"],
            buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 5.0),
        )

        self.itl = Histogram(
            "litellm_custom_itl_seconds",
            "Inter-token latency in seconds (average between successive tokens, streaming only)",
            labelnames=["model", "model_group", "api_provider"],
            buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 5.0),
        )

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        try:
            stream = kwargs.get("stream", False)
            completion_start_time = kwargs.get("completion_start_time")
            api_call_start_time = kwargs.get("api_call_start_time")

            # Model info from standard_logging_object or kwargs
            slo = kwargs.get("standard_logging_object") or {}
            model = slo.get("model") or kwargs.get("model", "unknown")
            model_group = slo.get("model_group") or model
            api_provider = slo.get("custom_llm_provider") or "unknown"

            labels = {"model": model, "model_group": model_group, "api_provider": api_provider}

            # Output tokens from response_obj
            output_tokens = 0
            if response_obj is not None:
                usage = None
                if hasattr(response_obj, "get"):
                    usage = response_obj.get("usage")
                elif hasattr(response_obj, "usage"):
                    usage = response_obj.usage
                if usage is not None:
                    if isinstance(usage, dict):
                        output_tokens = usage.get("completion_tokens", 0) or 0
                    elif hasattr(usage, "completion_tokens"):
                        output_tokens = usage.completion_tokens or 0

            # Convert timestamps
            start_ts = _to_timestamp(start_time)
            end_ts = _to_timestamp(end_time)
            api_start_ts = _to_timestamp(api_call_start_time)
            comp_start_ts = _to_timestamp(completion_start_time)

            # --- TTFT (streaming only) ---
            if stream and api_start_ts and comp_start_ts:
                ttft_seconds = comp_start_ts - api_start_ts
                if ttft_seconds > 0:
                    self.ttft.labels(**labels).observe(ttft_seconds)

            # --- TPOT & ITL ---
            if output_tokens > 0 and start_ts and end_ts:
                total_latency = end_ts - start_ts

                # TPOT = total_latency / output_tokens
                tpot_seconds = total_latency / output_tokens
                self.tpot.labels(**labels).observe(tpot_seconds)

                # ITL (streaming only) = streaming_duration / (output_tokens - 1)
                if stream and comp_start_ts:
                    streaming_duration = end_ts - comp_start_ts
                    if streaming_duration > 0 and output_tokens > 1:
                        itl_seconds = streaming_duration / (output_tokens - 1)
                        self.itl.labels(**labels).observe(itl_seconds)

        except Exception as e:
            print(f"[PrometheusTTFTTPOTITL] Error: {e}")


# Module-level instance picked up by LiteLLM's get_instance_fn()
my_prometheus_logger = PrometheusTTFTTPOTITL()
