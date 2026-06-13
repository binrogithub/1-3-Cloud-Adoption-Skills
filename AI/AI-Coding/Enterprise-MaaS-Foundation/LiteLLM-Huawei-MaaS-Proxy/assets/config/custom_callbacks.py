"""
Custom LiteLLM callback that:
  1. Emits TTFT, TPOT, and ITL as Prometheus histograms.
  2. Routes requests containing image content to the vision-openrouter model group.
  3. Detects search intent and injects Exa web search results before calling the model.

TTFT  = completion_start_time - api_call_start_time  (streaming only)
TPOT  = total_latency / output_tokens
ITL   = (end_time - completion_start_time) / max(output_tokens - 1, 1)  (streaming only)
"""

import os
import re

from litellm.integrations.custom_logger import CustomLogger
from prometheus_client import Histogram


IMAGE_ROUTER_MODEL = "vision-openrouter"

_SEARCH_RE = re.compile(
    r"搜索|新闻|最新|今天|今日|current|latest|today|news|search",
    re.IGNORECASE,
)


def _latest_user_text(data: dict) -> str:
    # Responses API uses "input"; chat completions uses "messages".
    for key in ("messages", "input"):
        msgs = data.get(key) or []
        for msg in reversed(msgs):
            if not isinstance(msg, dict) or msg.get("role") != "user":
                continue
            content = msg.get("content", "")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return " ".join(
                    block.get("text", "")
                    for block in content
                    if isinstance(block, dict)
                    and block.get("type") in ("text", "input_text")
                    and block.get("text")
                    and "<system-reminder>" not in block.get("text", "")
                )
    return ""


def _is_search_intent(data: dict) -> bool:
    return bool(_SEARCH_RE.search(_latest_user_text(data)))


async def _fetch_exa(query: str, api_key: str, num_results: int = 5) -> str:
    try:
        import httpx

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.exa.ai/search",
                headers={"x-api-key": api_key, "Content-Type": "application/json"},
                json={"query": query, "numResults": num_results, "contents": {"text": True}},
            )
        if not resp.is_success:
            print(f"[ExaSearch] HTTP {resp.status_code}")
            return ""
        results = resp.json().get("results", [])
        if not results:
            return ""
        lines = []
        for i, item in enumerate(results, 1):
            title = item.get("title", "Untitled")
            url = item.get("url") or item.get("id", "")
            published = item.get("publishedDate", "unknown date")
            text = str(item.get("text") or item.get("summary", "")).replace("\n", " ")[:900]
            lines.append(f"{i}. {title}\nURL: {url}\nPublished: {published}\nSnippet: {text}")
        return f"Web search results for: {query}\n\n" + "\n\n".join(lines)
    except Exception as e:
        print(f"[ExaSearch] error: {e}")
        return ""


def _inject_search_results(data: dict, results: str) -> None:
    instruction = (
        "Answer only from the injected web search results above. "
        "Include source URLs from those results. "
        "Do not call any search, fetch, or shell tools."
    )

    for key in ("messages", "input"):
        msgs = data.get(key)
        if not isinstance(msgs, list):
            continue
        for i in range(len(msgs) - 1, -1, -1):
            msg = msgs[i]
            if msg.get("role") != "user":
                continue
            content = msg.get("content", "")
            if isinstance(content, str):
                msgs[i] = {**msg, "content": content + f"\n\n{results}"}
            elif isinstance(content, list):
                msgs[i] = {**msg, "content": content + [{"type": "text", "text": f"\n\n{results}"}]}
            break
        break

    if "input" in data and "messages" not in data:
        existing = data.get("instructions") or ""
        data["instructions"] = (existing + "\n\n" + instruction).lstrip()
    else:
        system = data.get("system")
        if isinstance(system, str):
            data["system"] = system + "\n\n" + instruction
        elif isinstance(system, list):
            data["system"] = list(system) + [{"type": "text", "text": instruction}]
        else:
            data["system"] = [{"type": "text", "text": instruction}]


def _has_image_content(messages) -> bool:
    """Return True if any message contains OpenAI or Anthropic image blocks."""
    if not messages or not isinstance(messages, list):
        return False
    for message in messages:
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") in ("image_url", "image"):
                return True
    return False


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
    """Custom callback that emits metrics and mutates requests before dispatch."""

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

            slo = kwargs.get("standard_logging_object") or {}
            model = slo.get("model") or kwargs.get("model", "unknown")
            model_group = slo.get("model_group") or model
            api_provider = slo.get("custom_llm_provider") or "unknown"

            labels = {"model": model, "model_group": model_group, "api_provider": api_provider}

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

            start_ts = _to_timestamp(start_time)
            end_ts = _to_timestamp(end_time)
            api_start_ts = _to_timestamp(api_call_start_time)
            comp_start_ts = _to_timestamp(completion_start_time)

            if stream and api_start_ts and comp_start_ts:
                ttft_seconds = comp_start_ts - api_start_ts
                if ttft_seconds > 0:
                    self.ttft.labels(**labels).observe(ttft_seconds)

            if output_tokens > 0 and start_ts and end_ts:
                total_latency = end_ts - start_ts
                self.tpot.labels(**labels).observe(total_latency / output_tokens)

                if stream and comp_start_ts:
                    streaming_duration = end_ts - comp_start_ts
                    if streaming_duration > 0 and output_tokens > 1:
                        self.itl.labels(**labels).observe(streaming_duration / (output_tokens - 1))

        except Exception as e:
            print(f"[PrometheusTTFTTPOTITL] Error: {e}")

    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        """Redirect image requests to OpenRouter; inject Exa results for search intent."""
        messages = data.get("messages", [])

        if _has_image_content(messages):
            original_model = data.get("model", "unknown")
            data["model"] = IMAGE_ROUTER_MODEL
            print(f"[ImageRouter] image detected, {original_model!r} -> {IMAGE_ROUTER_MODEL!r}")
            return data

        if _is_search_intent(data):
            exa_key = os.environ.get("EXA_API_KEY", "")
            if exa_key:
                query = _latest_user_text(data)[:500]
                results = await _fetch_exa(query, exa_key)
                if results:
                    _inject_search_results(data, results)
                    print(f"[ExaSearch] injected {len(results)} chars for: {query[:60]!r}")
                else:
                    print("[ExaSearch] no results returned")
            else:
                print("[ExaSearch] EXA_API_KEY not set")

        return data

    async def async_pre_call_deployment_hook(self, kwargs, call_type):
        try:
            call_type_value = getattr(call_type, "value", str(call_type))
            tools = kwargs.get("tools") or []
            if call_type_value == "aresponses":
                repaired_tools = []
                for tool in tools:
                    if not isinstance(tool, dict):
                        repaired_tools.append(tool)
                        continue
                    function = tool.get("function") or {}
                    function_name = function.get("name") if isinstance(function, dict) else None
                    if tool.get("type") == "function" and function_name:
                        repaired_tools.append(
                            {
                                "type": "function",
                                "name": function_name,
                                "description": function.get("description", ""),
                                "parameters": function.get("parameters") or {"type": "object"},
                            }
                        )
                    else:
                        repaired_tools.append(tool)
                kwargs["tools"] = repaired_tools
        except Exception as e:
            print(f"[PrometheusTTFTTPOTITL] Tool repair error: {e}")
        return kwargs


# Module-level instance picked up by LiteLLM's get_instance_fn()
my_prometheus_logger = PrometheusTTFTTPOTITL()
