"""Huawei Cloud CSS executor: data-node (ess) scale-out / scale-in only."""

import logging
from datetime import datetime, timezone
from typing import Any

from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkcore.http.http_config import HttpConfig
from huaweicloudsdkcss.v1 import (
    CssClient,
    RoleExtendGrowReq,
    RoleExtendReq,
    ShrinkClusterReq,
    ShrinkNodeReq,
    ShowClusterDetailRequest,
    UpdateExtendInstanceStorageRequest,
    UpdateShrinkClusterRequest,
)
from huaweicloudsdkcss.v1.region.css_region import CssRegion

from config import Settings

logger = logging.getLogger(__name__)

NODE_TYPE = "ess"  # data nodes only


def build_css_client(settings: Settings) -> CssClient:
    credentials = BasicCredentials(
        ak=settings.huaweicloud_sdk_ak,
        sk=settings.huaweicloud_sdk_sk,
        project_id=settings.huaweicloud_project_id or None,
    )
    http_config = HttpConfig.get_default_config()
    http_config.timeout = (30, 60)
    builder = CssClient.new_builder().with_http_config(http_config).with_credentials(credentials)
    if settings.huaweicloud_css_endpoint:
        builder = builder.with_endpoint(settings.huaweicloud_css_endpoint)
    else:
        builder = builder.with_region(CssRegion.value_of(settings.huaweicloud_region))
    return builder.build()


def get_cluster_detail(client: CssClient, cluster_id: str) -> dict[str, Any]:
    """Get full cluster detail including all instances."""
    return _get_cluster_state(client, cluster_id)


def get_data_node_count(client: CssClient, cluster_id: str) -> int:
    state = _get_cluster_state(client, cluster_id)
    return sum(1 for inst in state["instances"] if inst["type"] == NODE_TYPE)


def get_cluster_info(client: CssClient, cluster_id: str) -> dict:
    state = _get_cluster_state(client, cluster_id)
    data_nodes = [inst for inst in state["instances"] if inst["type"] == NODE_TYPE]
    return {
        "cluster_id": state["cluster_id"],
        "cluster_name": state["name"],
        "cluster_status": state["status"],
        "data_node_count": len(data_nodes),
        "instances": state["instances"],
    }


def scale_out(client: CssClient, settings: Settings, delta: int) -> dict:
    if not settings.css_mutation_enabled:
        return {"action": "scale_out", "status": "skipped", "message": "CSS_MUTATION_ENABLED=false"}
    try:
        grow_req = RoleExtendGrowReq(type=NODE_TYPE, nodesize=delta, disksize=0)
        body = RoleExtendReq(grow=[grow_req], is_auto_pay=1)
        request = UpdateExtendInstanceStorageRequest(cluster_id=settings.cluster_id, body=body)
        client.update_extend_instance_storage(request)
        return {"action": "scale_out", "status": "success", "delta": delta, "node_type": NODE_TYPE}
    except Exception as exc:
        logger.error("scale_out_failed: %s", exc)
        return {"action": "scale_out", "status": "failed", "message": str(exc)}


def scale_in(client: CssClient, settings: Settings, delta: int) -> dict:
    if not settings.css_mutation_enabled:
        return {"action": "scale_in", "status": "skipped", "message": "CSS_MUTATION_ENABLED=false"}
    current = get_data_node_count(client, settings.cluster_id)
    # CSS rejects reducing half or more data nodes in one request
    max_delta = max(0, (current - 1) // 2)
    delta = min(delta, max_delta, current - settings.min_nodes)
    if delta <= 0:
        return {"action": "scale_in", "status": "skipped", "message": "delta clamped to 0"}
    try:
        shrink_node = ShrinkNodeReq(type=NODE_TYPE, reduced_node_num=delta)
        body = ShrinkClusterReq(shrink=[shrink_node], agency_name="", operation_type="", cluster_load_check=True)
        request = UpdateShrinkClusterRequest(cluster_id=settings.cluster_id, body=body)
        client.update_shrink_cluster(request)
        return {"action": "scale_in", "status": "success", "delta": delta, "node_type": NODE_TYPE}
    except Exception as exc:
        logger.error("scale_in_failed: %s", exc)
        return {"action": "scale_in", "status": "failed", "message": str(exc)}


def _get_cluster_state(client: CssClient, cluster_id: str) -> dict[str, Any]:
    request = ShowClusterDetailRequest(cluster_id=cluster_id)
    response = client.show_cluster_detail(request)
    if not response or not getattr(response, "id", None):
        raise RuntimeError(f"CSS cluster not accessible: {cluster_id}")
    instances = []
    for inst in getattr(response, "instances", []) or []:
        instances.append({
            "id": getattr(inst, "id", ""),
            "name": getattr(inst, "name", ""),
            "type": getattr(inst, "type", ""),
            "status": getattr(inst, "status", ""),
            "spec_code": getattr(inst, "spec_code", ""),
        })
    return {
        "cluster_id": getattr(response, "id", cluster_id),
        "name": getattr(response, "name", ""),
        "status": getattr(response, "status", ""),
        "instances": instances,
    }
