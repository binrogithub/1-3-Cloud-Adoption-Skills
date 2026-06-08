"""Simplified configuration."""

from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # AI
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")

    # Thresholds - basic
    cpu_spike_threshold: float = Field(default=80, alias="CPU_SPIKE_THRESHOLD")
    disk_spike_threshold: float = Field(default=85, alias="DISK_SPIKE_THRESHOLD")

    # Thresholds - extended
    jvm_heap_spike_threshold: float = Field(default=85, alias="JVM_HEAP_SPIKE_THRESHOLD")
    search_latency_spike_threshold: float = Field(default=500, alias="SEARCH_LATENCY_SPIKE_THRESHOLD")
    indexing_latency_spike_threshold: float = Field(default=200, alias="INDEXING_LATENCY_SPIKE_THRESHOLD")
    thread_pool_queue_spike_threshold: int = Field(default=100, alias="THREAD_POOL_QUEUE_SPIKE_THRESHOLD")

    # AI diagnosis
    ai_diagnose_enabled: bool = Field(default=True, alias="AI_DIAGNOSE_ENABLED")
    ai_auto_fix_enabled: bool = Field(default=False, alias="AI_AUTO_FIX_ENABLED")

    # Node limits
    min_nodes: int = Field(default=2, alias="MIN_NODES")
    max_nodes: int = Field(default=10, alias="MAX_NODES")

    # Scale step (configurable)
    scale_out_step: int = Field(default=1, alias="SCALE_OUT_STEP")
    scale_in_step: int = Field(default=1, alias="SCALE_IN_STEP")

    # Cooldown
    scale_out_cooldown_minutes: int = Field(default=10, alias="SCALE_OUT_COOLDOWN_MINUTES")
    scale_in_cooldown_minutes: int = Field(default=30, alias="SCALE_IN_COOLDOWN_MINUTES")

    # Scale-in guard: minimum interval after scale-out before scale-in is allowed
    scale_in_delay_after_scale_out_minutes: int = Field(default=30, alias="SCALE_IN_DELAY_AFTER_SCALE_OUT_MINUTES")

    # Check interval
    check_interval_seconds: int = Field(default=60, alias="CHECK_INTERVAL_SECONDS")

    # Huawei Cloud
    huaweicloud_region: str = Field(default="", alias="HUAWEICLOUD_REGION")
    huaweicloud_project_id: str = Field(default="", alias="HUAWEICLOUD_PROJECT_ID")
    huaweicloud_sdk_ak: str = Field(default="", alias="HUAWEICLOUD_SDK_AK")
    huaweicloud_sdk_sk: str = Field(default="", alias="HUAWEICLOUD_SDK_SK")
    huaweicloud_css_endpoint: str = Field(default="", alias="HUAWEICLOUD_CSS_ENDPOINT")
    huaweicloud_ces_endpoint: str = Field(default="", alias="HUAWEICLOUD_CES_ENDPOINT")

    # Cluster
    cluster_id: str = Field(default="", alias="CLUSTER_ID")
    cluster_name: str = Field(default="css-cluster", alias="CLUSTER_NAME")

    # Mutation toggle
    css_mutation_enabled: bool = Field(default=False, alias="CSS_MUTATION_ENABLED")

    # Server
    server_host: str = Field(default="0.0.0.0", alias="SERVER_HOST")
    server_port: int = Field(default=5000, alias="SERVER_PORT")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
