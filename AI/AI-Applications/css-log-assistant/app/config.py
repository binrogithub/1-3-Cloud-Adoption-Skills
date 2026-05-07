import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


@dataclass(frozen=True)
class AppConfig:
    es_url: str
    es_username: Optional[str]
    es_password: Optional[str]
    es_insecure: bool
    index_pattern: str
    mcp_sse_url: Optional[str]
    maas_api_key: str
    maas_base_url: str
    maas_model: str


def load_config() -> AppConfig:
    es_url = os.environ.get("ES_URL")
    if not es_url:
        raise RuntimeError("ES_URL is required")

    maas_api_key = os.environ.get("MAAS_API_KEY")
    if not maas_api_key:
        raise RuntimeError("MAAS_API_KEY is required")

    maas_model = os.environ.get("MAAS_MODEL")
    if not maas_model:
        raise RuntimeError("MAAS_MODEL is required")

    return AppConfig(
        es_url=es_url,
        es_username=os.environ.get("ES_USERNAME"),
        es_password=os.environ.get("ES_PASSWORD"),
        es_insecure=os.environ.get("ES_INSECURE", "false").lower() in {"1", "true", "yes"},
        index_pattern=os.environ.get("ES_INDEX_PATTERN", "food_delivery_logs-*"),
        mcp_sse_url=os.environ.get("MCP_SSE_URL"),
        maas_api_key=maas_api_key,
        maas_base_url=os.environ.get("MAAS_BASE_URL", "https://api-ap-southeast-1.modelarts-maas.com/anthropic/v1"),
        maas_model=maas_model,
    )

