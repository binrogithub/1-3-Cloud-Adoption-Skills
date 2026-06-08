"""Huawei Cloud CES metrics: multi-dimension collection for CSS cluster."""

import logging
from datetime import datetime, timezone
from typing import Optional

from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkcore.http.http_config import HttpConfig
from huaweicloudsdkces.v1 import CesClient, ShowMetricDataRequest
from huaweicloudsdkces.v1.region.ces_region import CesRegion

from config import Settings

logger = logging.getLogger(__name__)

NAMESPACE = "SYS.ES"

METRIC_DEFS = {
    # CPU
    "cpu_avg":              {"ces_name": "avg_cpu_usage",               "unit": "%",   "group": "cpu"},
    "cpu_max":              {"ces_name": "max_cpu_usage",               "unit": "%",   "group": "cpu"},
    # Disk
    "disk_usage_pct":       {"ces_name": "disk_util",                   "unit": "%",   "group": "disk"},
    "disk_io_util_max":     {"ces_name": "max_disk_io_util",            "unit": "%",   "group": "disk"},
    # JVM Heap
    "jvm_heap_max":         {"ces_name": "max_jvm_heap_usage",          "unit": "%",   "group": "jvm"},
    "jvm_heap_avg":         {"ces_name": "avg_jvm_heap_usage",          "unit": "%",   "group": "jvm"},
    # JVM GC
    "jvm_old_gc_time_avg":  {"ces_name": "avg_jvm_old_gc_time",         "unit": "ms",  "group": "jvm"},
    "jvm_young_gc_time_avg":{"ces_name": "avg_jvm_young_gc_time",       "unit": "ms",  "group": "jvm"},
    # Search / QPS
    "search_rate":          {"ces_name": "SearchRate",                  "unit": "ops", "group": "qps"},
    "search_latency":       {"ces_name": "SearchLatency",               "unit": "ms",  "group": "qps"},
    # Indexing / Write
    "indexing_rate":        {"ces_name": "IndexingRate",                "unit": "ops", "group": "qps"},
    "indexing_latency":     {"ces_name": "IndexingLatency",             "unit": "ms",  "group": "qps"},
    # Thread pool - queue
    "tp_search_queue":      {"ces_name": "sum_thread_pool_search_queue",       "unit": "个", "group": "thread_pool"},
    "tp_write_queue":       {"ces_name": "sum_thread_pool_write_queue",        "unit": "个", "group": "thread_pool"},
    "tp_force_merge_queue": {"ces_name": "sum_thread_pool_force_merge_queue",  "unit": "个", "group": "thread_pool"},
    "tp_refresh_queue":     {"ces_name": "sum_thread_pool_refresh_queue",      "unit": "个", "group": "thread_pool"},
    "tp_generic_queue":     {"ces_name": "sum_thread_pool_generic_queue",      "unit": "个", "group": "thread_pool"},
    "tp_management_queue":  {"ces_name": "sum_thread_pool_management_queue",   "unit": "个", "group": "thread_pool"},
    # Thread pool - rejected
    "tp_search_rejected":   {"ces_name": "sum_thread_pool_search_rejected",    "unit": "个", "group": "thread_pool"},
    "tp_write_rejected":    {"ces_name": "sum_thread_pool_write_rejected",     "unit": "个", "group": "thread_pool"},
    "tp_force_merge_rejected": {"ces_name": "sum_thread_pool_force_merge_rejected", "unit": "个", "group": "thread_pool"},
    "tp_refresh_rejected":  {"ces_name": "sum_thread_pool_refresh_rejected",   "unit": "个", "group": "thread_pool"},
    "tp_generic_rejected":  {"ces_name": "sum_thread_pool_generic_rejected",   "unit": "个", "group": "thread_pool"},
    "tp_management_rejected": {"ces_name": "sum_thread_pool_management_rejected", "unit": "个", "group": "thread_pool"},
    # Pending tasks
    "pending_tasks":        {"ces_name": "number_of_pending_tasks",            "unit": "个", "group": "thread_pool"},
    # Cluster status
    "cluster_status":       {"ces_name": "status",                      "unit": "",    "group": "cluster"},
    # HTTP
    "http_open_max":        {"ces_name": "max_current_opened_http_count","unit": "个", "group": "http"},
    # Load
    "load_avg_max":         {"ces_name": "max_load_average",            "unit": "",    "group": "load"},
}

# Extra metrics only collected during diagnosis (not in regular cycle)
DIAGNOSIS_METRIC_DEFS = {
    "unassigned_shards":        {"ces_name": "number_of_unassigned_shards",       "unit": "个", "group": "diagnosis"},
    "shard_doc_exceed":         {"ces_name": "shard_doc_exceed_threshold_count",  "unit": "个", "group": "diagnosis"},
    "write_fail_alias":         {"ces_name": "write_fail_alias_error",            "unit": "个", "group": "diagnosis"},
    "write_fail_doc_count":     {"ces_name": "write_fail_documents_count_exceed", "unit": "个", "group": "diagnosis"},
    "write_fail_field_count":   {"ces_name": "write_fail_fields_count_exceed",    "unit": "个", "group": "diagnosis"},
    "write_fail_shard_count":   {"ces_name": "write_fail_shards_count_exceed",    "unit": "个", "group": "diagnosis"},
    "write_fail_index_block":   {"ces_name": "write_fail_index_blocks_write",     "unit": "个", "group": "diagnosis"},
    "write_fail_mapping":       {"ces_name": "write_fail_mapping_malformed",      "unit": "个", "group": "diagnosis"},
    "index_create_fail":        {"ces_name": "number_of_index_creation_failures", "unit": "个", "group": "diagnosis"},
}


def build_ces_client(settings: Settings) -> CesClient:
    credentials = BasicCredentials(
        ak=settings.huaweicloud_sdk_ak,
        sk=settings.huaweicloud_sdk_sk,
        project_id=settings.huaweicloud_project_id or None,
    )
    http_config = HttpConfig.get_default_config()
    http_config.timeout = (30, 60)
    builder = CesClient.new_builder().with_http_config(http_config).with_credentials(credentials)
    if settings.huaweicloud_ces_endpoint:
        builder = builder.with_endpoint(settings.huaweicloud_ces_endpoint)
    else:
        builder = builder.with_region(CesRegion.value_of(settings.huaweicloud_region))
    return builder.build()


def _query_metric(
    client: CesClient,
    cluster_id: str,
    metric_name: str,
    period: int = 60,
    filt: str = "average",
    from_minutes: int = 30,
) -> float:
    now = int(datetime.now(timezone.utc).timestamp() * 1000)
    request = ShowMetricDataRequest(
        namespace=NAMESPACE,
        metric_name=metric_name,
        dim_0=f"cluster_id,{cluster_id}",
        _from=now - (from_minutes * 60 * 1000),
        to=now,
        period=period,
        filter=filt,
    )
    try:
        response = client.show_metric_data(request)
        datapoints = sorted(response.datapoints or [], key=lambda d: d.timestamp or 0, reverse=True)
        for point in datapoints:
            val = getattr(point, filt, None)
            if val is not None:
                return float(val)
    except Exception as exc:
        logger.warning("metric_query_failed metric=%s error=%s", metric_name, exc)
    return 0.0


def collect_metrics(client: CesClient, cluster_id: str) -> dict:
    """Collect all metrics defined in METRIC_DEFS. Returns dict with all keys + timestamp."""
    result = {}
    for key, defn in METRIC_DEFS.items():
        result[key] = round(_query_metric(client, cluster_id, defn["ces_name"]), 2)
    result["timestamp"] = datetime.now(timezone.utc).isoformat()
    return result


def collect_diagnosis_metrics(client: CesClient, cluster_id: str) -> dict:
    """Collect extra metrics for cluster diagnosis."""
    result = {}
    for key, defn in DIAGNOSIS_METRIC_DEFS.items():
        result[key] = round(_query_metric(client, cluster_id, defn["ces_name"]), 2)
    return result


CLUSTER_STATUS_MAP = {
    0: ("available", "green"),
    1: ("replica_missing", "yellow"),
    2: ("data_missing", "red"),
    3: ("unknown", "gray"),
}


def interpret_cluster_status(status_value: float) -> dict:
    """Map CES status metric value to human-readable info."""
    sv = int(status_value) if status_value is not None else 3
    label, color = CLUSTER_STATUS_MAP.get(sv, ("unknown", "gray"))
    return {"value": sv, "label": label, "color": color, "healthy": sv == 0}
