"""Thin, lazy Huawei Cloud CSS/CES adapter.

The adapter contains no scaling policy. The E01 Runbook owns mutations and
selects either the Huawei SDK or the configured KooCLI adapter. Keeping SDK
imports lazy lets installation and policy tests run without cloud packages.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from koo_cli import KooCliError, ces_metrics as koo_ces_metrics
from koo_cli import ces_metric_samples as koo_ces_metric_samples
from koo_cli import cluster_snapshot as koo_cluster_snapshot
from koo_cli import request_id as koo_request_id
from koo_cli import scale_cluster as koo_scale_cluster
from koo_cli import uses_koo_cli


class CssCloudError(RuntimeError):
    pass


def _sdk_clients(credentials: dict[str, Any]):
    try:
        from huaweicloudsdkcore.auth.credentials import BasicCredentials
        from huaweicloudsdkcore.http.http_config import HttpConfig
        from huaweicloudsdkcss.v1 import CssClient
        from huaweicloudsdkcss.v1.region.css_region import CssRegion
        from huaweicloudsdkces.v1 import CesClient
        from huaweicloudsdkces.v1.region.ces_region import CesRegion
    except ImportError as exc:
        raise CssCloudError("Huawei Cloud CSS/CES SDK is not installed") from exc
    auth = BasicCredentials(
        ak=credentials["access_key_id"],
        sk=credentials["secret_access_key"],
        project_id=credentials["project_id"],
    )
    http = HttpConfig.get_default_config()
    http.timeout = (10, 30)
    css_builder = CssClient.new_builder().with_credentials(auth).with_http_config(http)
    ces_builder = CesClient.new_builder().with_credentials(auth).with_http_config(http)
    endpoint = credentials.get("css_endpoint")
    if endpoint:
        css_builder = css_builder.with_endpoint(endpoint)
    else:
        css_builder = css_builder.with_region(CssRegion.value_of(credentials["region"]))
    ces_builder = ces_builder.with_region(CesRegion.value_of(credentials["region"]))
    return css_builder.build(), ces_builder.build()


def _value(obj: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj[name]
        value = getattr(obj, name, None)
        if value is not None:
            return value
    return default


def cluster_snapshot(profile: dict[str, Any], credentials: dict[str, Any]) -> dict[str, Any]:
    if uses_koo_cli(profile):
        try:
            return koo_cluster_snapshot(profile)
        except KooCliError as exc:
            raise CssCloudError(str(exc)) from exc
    try:
        from huaweicloudsdkcss.v1 import ShowClusterDetailRequest
        css, _ = _sdk_clients(credentials)
        response = css.show_cluster_detail(
            ShowClusterDetailRequest(cluster_id=profile["cluster_id"])
        )
    except Exception as exc:
        if isinstance(exc, CssCloudError):
            raise
        raise CssCloudError(f"CSS cluster detail failed: {exc}") from exc
    instances = []
    for item in _value(response, "instances", default=[]) or []:
        instances.append({
            "id": _value(item, "id", default=""),
            "name": _value(item, "name", default=""),
            "type": _value(item, "type", default=""),
            "status": _value(item, "status", default=""),
            "az": _value(item, "availability_zone", "az", default=""),
        })
    data_nodes = [item for item in instances if item["type"] == "ess"]
    status = str(_value(response, "status", default="unknown")).casefold()
    return {
        "cluster_id": _value(response, "id", default=profile["cluster_id"]),
        "cluster_status": status,
        "cluster_healthy": status in {"200", "running", "available", "green"},
        "data_node_count": len(data_nodes),
        "instances": instances,
        "actions": list(_value(response, "actions", default=[]) or []),
        "action_progress": dict(_value(response, "action_progress", default={}) or {}),
        "failed_reason": _value(response, "failed_reason", default=None),
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }


def ces_metrics(profile: dict[str, Any], credentials: dict[str, Any],
                names: tuple[str, ...] = (
                    "status", "disk_util", "max_jvm_heap_usage", "max_cpu_usage",
                    "SearchRate", "SearchLatency", "IndexingRate", "IndexingLatency",
                )) -> dict[str, Any]:
    if uses_koo_cli(profile):
        try:
            return koo_ces_metrics(profile, names)
        except KooCliError as exc:
            raise CssCloudError(str(exc)) from exc
    try:
        from huaweicloudsdkces.v1 import ShowMetricDataRequest
        _, ces = _sdk_clients(credentials)
    except Exception as exc:
        if isinstance(exc, CssCloudError):
            raise
        raise CssCloudError(f"CES client setup failed: {exc}") from exc
    now = int(datetime.now(timezone.utc).timestamp() * 1000)
    values: dict[str, Any] = {}
    for name in names:
        try:
            response = ces.show_metric_data(ShowMetricDataRequest(
                namespace="SYS.ES",
                metric_name=name,
                dim_0=f"cluster_id,{profile['cluster_id']}",
                _from=now - 10 * 60 * 1000,
                to=now,
                period=60,
                filter="average",
            ))
            points = sorted(_value(response, "datapoints", default=[]) or [],
                            key=lambda item: _value(item, "timestamp", default=0) or 0,
                            reverse=True)
            point = points[0] if points else None
            values[name] = _value(point, "average", default=None) if point else None
        except Exception as exc:
            values[name] = None
    return values


def ces_metric_samples(profile: dict[str, Any], credentials: dict[str, Any],
                       names: tuple[str, ...] = (
                           "status", "disk_util", "max_jvm_heap_usage", "max_cpu_usage",
                           "SearchRate", "SearchLatency", "IndexingRate", "IndexingLatency",
                       )) -> dict[str, dict[str, Any]]:
    """Return CES values without losing provider sample timestamps."""
    if uses_koo_cli(profile):
        try:
            samples = koo_ces_metric_samples(profile, names)
            if samples and all(item.get("quality") == "error" for item in samples.values()):
                raise CssCloudError("CES returned no usable metrics: all metric reads failed")
            return samples
        except KooCliError as exc:
            raise CssCloudError(str(exc)) from exc
    try:
        from huaweicloudsdkces.v1 import ShowMetricDataRequest
        _, ces = _sdk_clients(credentials)
    except Exception as exc:
        if isinstance(exc, CssCloudError):
            raise
        raise CssCloudError(f"CES client setup failed: {exc}") from exc
    now = int(datetime.now(timezone.utc).timestamp() * 1000)
    values: dict[str, dict[str, Any]] = {}
    for name in names:
        try:
            response = ces.show_metric_data(ShowMetricDataRequest(
                namespace="SYS.ES", metric_name=name,
                dim_0=f"cluster_id,{profile['cluster_id']}",
                _from=now - 10 * 60 * 1000, to=now, period=60, filter="average",
            ))
            points = sorted(_value(response, "datapoints", default=[]) or [],
                            key=lambda item: _value(item, "timestamp", default=0) or 0,
                            reverse=True)
            point = points[0] if points else None
            values[name] = {
                "value": _value(point, "average", "value", default=None) if point else None,
                "observed_at": _value(point, "timestamp", "time", default=None) if point else None,
                "unit": _value(point, "unit", "unit_name", default=None) if point else None,
                "aggregation": "average", "source": "ces",
                "window_minutes": 10, "quality": "ok" if point else "empty",
            }
        except Exception as exc:
            values[name] = {"value": None, "quality": "error", "error": str(exc), "source": "ces"}
    if values and all(item.get("quality") == "error" for item in values.values()):
        raise CssCloudError("CES returned no usable metrics: all metric reads failed")
    return values


def scale_cluster(profile: dict[str, Any], credentials: dict[str, Any],
                  direction: str, delta: int) -> tuple[Any, str | None]:
    """Submit one already-authorized scale action through the selected adapter."""
    if uses_koo_cli(profile):
        try:
            response = koo_scale_cluster(profile, direction, delta)
            return response, koo_request_id(response)
        except KooCliError as exc:
            raise CssCloudError(str(exc)) from exc
    try:
        from huaweicloudsdkcss.v1 import (
            RoleExtendGrowReq, RoleExtendReq, ShrinkClusterReq, ShrinkNodeReq,
            UpdateExtendInstanceStorageRequest, UpdateShrinkClusterRequest,
        )
        css, _ = _sdk_clients(credentials)
        if direction == "scale_out":
            body = RoleExtendReq(
                grow=[RoleExtendGrowReq(type="ess", nodesize=delta, disksize=0)],
                is_auto_pay=1,
            )
            response = css.update_extend_instance_storage(
                UpdateExtendInstanceStorageRequest(cluster_id=profile["cluster_id"], body=body)
            )
        elif direction == "scale_in":
            body = ShrinkClusterReq(
                shrink=[ShrinkNodeReq(type="ess", reduced_node_num=delta)],
                operation_type="vm", cluster_load_check=True,
            )
            response = css.update_shrink_cluster(
                UpdateShrinkClusterRequest(cluster_id=profile["cluster_id"], body=body)
            )
        else:
            raise CssCloudError(f"unsupported CSS scaling direction: {direction}")
        return response, getattr(response, "request_id", None)
    except ImportError as exc:
        raise CssCloudError("Huawei Cloud CSS SDK is not installed") from exc
    except CssCloudError:
        raise
    except Exception as exc:
        raise CssCloudError(f"CSS scale request failed: {exc}") from exc
