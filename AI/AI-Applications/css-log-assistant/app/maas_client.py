import json
from dataclasses import dataclass
from typing import Any, Dict, Generator, List, Optional

import httpx


@dataclass(frozen=True)
class MaaSConfig:
    api_key: str
    base_url: str
    model: str
    timeout_s: float = 120.0


class MaaSClient:
    def __init__(self, config: MaaSConfig):
        self._config = config
        self._client = httpx.Client(timeout=httpx.Timeout(self._config.timeout_s))

    def close(self):
        self._client.close()

    def _build_headers(self) -> Dict[str, str]:
        return {
            "x-api-key": self._config.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }

    def _build_payload(
        self,
        messages: List[Dict[str, Any]],
        system: Optional[str],
        temperature: float,
        max_tokens: int,
        stream: bool,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self._config.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
        }
        if system:
            payload["system"] = system
        return payload

    def messages_create(
        self,
        messages: List[Dict[str, Any]],
        system: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> tuple:
        url = self._config.base_url.rstrip("/") + "/messages"
        resp = self._client.post(
            url,
            headers=self._build_headers(),
            json=self._build_payload(messages, system, temperature, max_tokens, stream=False),
        )
        resp.raise_for_status()
        data = resp.json()
        thinking = None
        text = None
        for block in data["content"]:
            if block.get("type") == "thinking":
                thinking = block.get("thinking", "")
            elif block.get("type") == "text":
                text = block["text"]
        if text is None:
            raise RuntimeError(f"No text block in MAAS response: {data['content']}")
        return text, thinking

    def messages_stream(
        self,
        messages: List[Dict[str, Any]],
        system: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> Generator[Dict[str, Any], None, None]:
        """Stream MAAS response. Yields dicts: {"type": "thinking_delta", "text": "..."} or {"type": "text_delta", "text": "..."}."""
        url = self._config.base_url.rstrip("/") + "/messages"
        with self._client.stream(
            "POST",
            url,
            headers=self._build_headers(),
            json=self._build_payload(messages, system, temperature, max_tokens, stream=True),
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[len("data: "):]
                if data_str == "[DONE]":
                    break
                try:
                    event = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                event_type = event.get("type", "")
                if event_type == "content_block_delta":
                    delta = event.get("delta", {})
                    delta_type = delta.get("type", "")
                    if delta_type == "thinking_delta":
                        yield {"type": "thinking_delta", "text": delta.get("thinking", "")}
                    elif delta_type == "text_delta":
                        yield {"type": "text_delta", "text": delta.get("text", "")}

    def nl_to_es_query(self, question: str, index_pattern: str) -> tuple:
        system = (
            "You are a log search assistant. Convert the user question into a single Elasticsearch Query DSL request. "
            "Return ONLY a JSON object with keys: index, body. "
            "index must be an index pattern. body must be valid for Elasticsearch _search.\n\n"
            "Index schema (use these exact field names):\n"
            "- timestamp (type: date) — NOT @timestamp, use \"timestamp\" only\n"
            "- order_id, country, country_code, city (type: keyword)\n"
            "- restaurant_id, restaurant_name (keyword/text)\n"
            "- customer_id, driver_id (keyword)\n"
            "- order_status (keyword): delivered, preparing, in_transit, cancelled_by_customer, cancelled_by_restaurant, payment_failed, delivery_timeout, pending\n"
            "- total_amount (double), currency (keyword)\n"
            "- items_count, delivery_time_minutes (integer)\n"
            "- distance_km (double)\n"
            "- payment_method, platform (keyword)\n"
            "- error_code (keyword), error_message (text)\n\n"
            "Important: Always use \"timestamp\" for time fields, never \"@timestamp\"."
        )
        user = f"index_pattern: {index_pattern}\nquestion: {question}"
        content, thinking = self.messages_create(
            messages=[{"role": "user", "content": user}],
            system=system,
            temperature=0.0,
        )
        content = content.strip()
        if content.startswith("```"):
            content = content.strip("`")
            content = content.replace("json", "", 1).strip()
        return json.loads(content), thinking

    def summarize_results(self, question: str, results: Dict[str, Any]) -> tuple:
        system = (
            "You are a log analytics assistant. Answer the user's question using the Elasticsearch search results. "
            "Be concise and respond in English."
        )
        user = json.dumps({"question": question, "results": results}, ensure_ascii=False)
        text, thinking = self.messages_create(
            messages=[{"role": "user", "content": user}],
            system=system,
            temperature=0.2,
        )
        return text, thinking
