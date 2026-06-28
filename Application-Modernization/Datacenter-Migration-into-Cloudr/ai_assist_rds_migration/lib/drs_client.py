#!/usr/bin/env python3
"""Huawei Cloud DRS API client for DRS migration automation.

Uses Huawei Cloud official DRS v5 SDK with AK/SK authentication.
Provides backward-compatible return structures for existing scripts.
"""

import time

from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkdrs.v5 import DrsClient as DRSV5Client
from huaweicloudsdkdrs.v5.model.action_params import ActionParams
from huaweicloudsdkdrs.v5.model.action_req import ActionReq
from huaweicloudsdkdrs.v5.model.base_endpoint import BaseEndpoint
from huaweicloudsdkdrs.v5.model.base_endpoint_config import BaseEndpointConfig
from huaweicloudsdkdrs.v5.model.cloud_base_info import CloudBaseInfo
from huaweicloudsdkdrs.v5.model.cloud_vpc_info import CloudVpcInfo
from huaweicloudsdkdrs.v5.model.compare_task_params import CompareTaskParams
from huaweicloudsdkdrs.v5.model.create_job_req import CreateJobReq
from huaweicloudsdkdrs.v5.model.create_job_request import CreateJobRequest
from huaweicloudsdkdrs.v5.model.delete_job_request import DeleteJobRequest
from huaweicloudsdkdrs.v5.model.endpoint_ssl_config import EndpointSslConfig
from huaweicloudsdkdrs.v5.model.execute_job_action_request import ExecuteJobActionRequest
from huaweicloudsdkdrs.v5.model.job_action_req import JobActionReq
from huaweicloudsdkdrs.v5.model.job_base_info import JobBaseInfo
from huaweicloudsdkdrs.v5.model.job_endpoint_info import JobEndpointInfo
from huaweicloudsdkdrs.v5.model.job_node_base_info import JobNodeBaseInfo
from huaweicloudsdkdrs.v5.model.job_node_info import JobNodeInfo
from huaweicloudsdkdrs.v5.model.job_node_spec_info import JobNodeSpecInfo
from huaweicloudsdkdrs.v5.model.job_node_vpc_info import JobNodeVpcInfo
from huaweicloudsdkdrs.v5.model.public_ip_config import PublicIpConfig
from huaweicloudsdkdrs.v5.model.show_compare_progress_request import ShowCompareProgressRequest
from huaweicloudsdkdrs.v5.model.show_health_compare_job_detail_request import ShowHealthCompareJobDetailRequest
from huaweicloudsdkdrs.v5.model.show_health_compare_job_list_request import ShowHealthCompareJobListRequest
from huaweicloudsdkdrs.v5.model.show_job_detail_request import ShowJobDetailRequest
from huaweicloudsdkdrs.v5.model.single_create_job_req import SingleCreateJobReq

from config_loader import get_huawei_cloud_config
from log_utils import get_logger, log_api_call, mask_sensitive

logger = get_logger("drs_client")

# DRS job status constants
STATUS_CREATE_FAILED = "CREATE_FAILED"
STATUS_CONFIGURATION = "CONFIGURATION"
STATUS_WAITING_FOR_START = "WAITING_FOR_START"
STATUS_STARTING = "STARTING"
STATUS_FULL_TRANS = "FULL_TRANS"
STATUS_INCR_TRANS = "INCR_TRANS"
STATUS_CUTOVERING = "CUTOVERING"
STATUS_COMPLETE = "COMPLETE"
STATUS_FAILED = "FAILED"
STATUS_PAUSED = "PAUSED"

READY_STATUSES = {STATUS_CONFIGURATION, STATUS_WAITING_FOR_START}
RUNNING_STATUSES = {STATUS_FULL_TRANS, STATUS_INCR_TRANS}
ABNORMAL_STATUSES = {STATUS_CREATE_FAILED, STATUS_FAILED, STATUS_PAUSED}

# Retry configuration
MAX_RETRIES = 3
RETRY_BACKOFF = 2


class DRSClient:
    """Huawei Cloud DRS API client."""

    def __init__(self):
        config = get_huawei_cloud_config()
        self.ak = config["access_key"]
        self.sk = config["secret_key"]
        self.project_id = config["project_id"]
        self.region = config["region"]
        self.endpoint = f"https://drs.{self.region}.myhuaweicloud.com"

        credentials = BasicCredentials(self.ak, self.sk, self.project_id)
        self.client = DRSV5Client.new_builder().with_credentials(credentials).with_endpoint(self.endpoint).build()

        # In-process compare task -> job mapping (used by script 09 flow)
        self._compare_task_job_map = {}
        self._precheck_query_id_map = {}

    @staticmethod
    def _to_dict(obj):
        if obj is None:
            return None
        if isinstance(obj, dict):
            return obj
        if hasattr(obj, "to_dict"):
            return obj.to_dict()
        return obj

    @staticmethod
    def _as_str(v):
        if v is None:
            return None
        return str(v)

    @staticmethod
    def _normalize_engine_type(v):
        if not v:
            return "mysql-to-mysql"
        vv = str(v).lower()
        if vv in ("mysql", "mysql-to-mysql"):
            return "mysql-to-mysql"
        return vv

    @staticmethod
    def _normalize_job_direction(v):
        if not v:
            return "up"
        vv = str(v).lower()
        if vv in ("in", "up"):
            return "up"
        if vv in ("out", "down"):
            return "down"
        return vv

    @staticmethod
    def _first_sg(v):
        if isinstance(v, list):
            return v[0] if v else None
        if isinstance(v, str) and "," in v:
            return v.split(",", 1)[0].strip()
        return v

    def _call_with_retry(self, action_name, fn, request_obj):
        last_error = None
        req_dict = self._to_dict(request_obj)

        for attempt in range(MAX_RETRIES):
            try:
                resp = fn(request_obj)
                resp_dict = self._to_dict(resp)
                log_api_call(logger, action_name, req_dict, resp_dict)
                return resp
            except Exception as e:  # noqa: BLE001
                last_error = e
                logger.warning(
                    "API call failed (attempt %d/%d) %s: %s",
                    attempt + 1,
                    MAX_RETRIES,
                    action_name,
                    mask_sensitive(str(e)),
                )
                if attempt < MAX_RETRIES - 1:
                    wait_time = RETRY_BACKOFF ** attempt
                    logger.info("Retrying in %s seconds...", wait_time)
                    time.sleep(wait_time)

        raise last_error or RuntimeError(f"Unknown error in {action_name}")

    def _build_base_endpoint(self, data):
        if not data:
            return None
        return BaseEndpoint(
            id=data.get("id"),
            endpoint_name=data.get("endpoint_name"),
            ip=data.get("ip"),
            db_port=self._as_str(data.get("db_port")),
            db_user=data.get("db_user"),
            db_password=data.get("db_password"),
            instance_id=data.get("instance_id"),
            instance_name=data.get("instance_name"),
            db_name=data.get("db_name"),
        )

    def _build_cloud_base_info(self, data):
        if not data:
            return None
        return CloudBaseInfo(
            region=data.get("region"),
            project_id=data.get("project_id"),
            az_code=data.get("az_code"),
        )

    def _build_cloud_vpc_info(self, data):
        if not data:
            return None
        return CloudVpcInfo(
            vpc_id=data.get("vpc_id"),
            subnet_id=data.get("subnet_id"),
            security_group_id=self._first_sg(data.get("security_group_id")),
        )

    def _build_endpoint_config(self, data):
        if not data:
            return None
        return BaseEndpointConfig(is_target_readonly=data.get("is_target_readonly"), node_num=data.get("node_num"))

    def _build_ssl_config(self, data):
        if not data:
            return None
        return EndpointSslConfig(
            ssl_link=data.get("ssl_link"),
            ssl_cert_name=data.get("ssl_cert_name"),
            ssl_cert_key=data.get("ssl_cert_key"),
            ssl_cert_check_sum=data.get("ssl_cert_check_sum"),
            ssl_cert_password=data.get("ssl_cert_password"),
        )

    def _build_job_endpoint(self, data):
        if not data:
            return None
        return JobEndpointInfo(
            db_type=data.get("db_type"),
            endpoint_type=data.get("endpoint_type"),
            endpoint_role=data.get("endpoint_role"),
            endpoint=self._build_base_endpoint(data.get("endpoint") or {}),
            cloud=self._build_cloud_base_info(data.get("cloud") or {}),
            vpc=self._build_cloud_vpc_info(data.get("vpc") or {}),
            config=self._build_endpoint_config(data.get("config") or {}),
            ssl=self._build_ssl_config(data.get("ssl") or {}),
        )

    def _normalize_legacy_payload(self, payload):
        """Convert legacy v3-like payload into v5-like payload when needed."""
        if "base_info" in payload and "source_endpoint" in payload and "target_endpoint" in payload:
            return payload

        src = payload.get("source_endpoint", {})
        tgt = payload.get("target_endpoint", {})

        return {
            "base_info": {
                "name": payload.get("job_name"),
                "job_type": payload.get("job_type", "migration"),
                "engine_type": self._normalize_engine_type(payload.get("engine_type")),
                "job_direction": self._normalize_job_direction(payload.get("job_direction", "up")),
                "task_type": payload.get("task_type", "FULL_INCR_TRANS"),
                "net_type": payload.get("net_type", "eip"),
                "charging_mode": payload.get("charging_mode", "on_demand"),
                "description": payload.get("description", ""),
            },
            "source_endpoint": [
                {
                    "db_type": "mysql",
                    "endpoint_type": "offline",
                    "endpoint_role": "so",
                    "endpoint": {
                        "ip": src.get("ip"),
                        "db_port": self._as_str(src.get("port")),
                        "db_user": src.get("user"),
                        "db_password": src.get("password"),
                    },
                    "ssl": {"ssl_link": False},
                }
            ],
            "target_endpoint": [
                {
                    "db_type": "mysql",
                    "endpoint_type": "offline",
                    "endpoint_role": "ta",
                    "endpoint": {
                        "ip": tgt.get("ip"),
                        "db_port": self._as_str(tgt.get("port")),
                        "db_user": tgt.get("user"),
                        "db_password": tgt.get("password"),
                    },
                    "ssl": {"ssl_link": False},
                }
            ],
        }

    def _build_create_job_req(self, payload):
        job_data = payload.get("job") if isinstance(payload, dict) and "job" in payload else payload
        job_data = self._normalize_legacy_payload(job_data or {})

        base_info_raw = dict(job_data.get("base_info") or {})
        base_info_raw["engine_type"] = self._normalize_engine_type(base_info_raw.get("engine_type"))
        base_info_raw["job_direction"] = self._normalize_job_direction(base_info_raw.get("job_direction"))
        base_info = JobBaseInfo(
            name=base_info_raw.get("name"),
            job_type=base_info_raw.get("job_type"),
            engine_type=base_info_raw.get("engine_type"),
            job_direction=base_info_raw.get("job_direction"),
            task_type=base_info_raw.get("task_type"),
            net_type=base_info_raw.get("net_type"),
            charging_mode=base_info_raw.get("charging_mode"),
            description=base_info_raw.get("description"),
            enterprise_project_id=base_info_raw.get("enterprise_project_id"),
            is_open_fast_clean=base_info_raw.get("is_open_fast_clean"),
        )

        src_eps = [self._build_job_endpoint(ep) for ep in (job_data.get("source_endpoint") or [])]
        src_eps = [ep for ep in src_eps if ep is not None]

        tgt_eps = [self._build_job_endpoint(ep) for ep in (job_data.get("target_endpoint") or [])]
        tgt_eps = [ep for ep in tgt_eps if ep is not None]

        node_info_raw = job_data.get("node_info") or {}
        node_info = None
        if node_info_raw:
            node_info = JobNodeInfo(
                spec=JobNodeSpecInfo(node_type=((node_info_raw.get("spec") or {}).get("node_type"))),
                vpc=JobNodeVpcInfo(
                    vpc_id=((node_info_raw.get("vpc") or {}).get("vpc_id")),
                    subnet_id=((node_info_raw.get("vpc") or {}).get("subnet_id")),
                    security_group_id=self._first_sg((node_info_raw.get("vpc") or {}).get("security_group_id")),
                    custom_node_ip=((node_info_raw.get("vpc") or {}).get("custom_node_ip")),
                ),
                base_info=JobNodeBaseInfo(
                    availability_zone=((node_info_raw.get("base_info") or {}).get("availability_zone")),
                    instance_type=((node_info_raw.get("base_info") or {}).get("instance_type")),
                    arch=((node_info_raw.get("base_info") or {}).get("arch")),
                    role=((node_info_raw.get("base_info") or {}).get("role")),
                ),
            )

        public_ip_list = []
        for ip_cfg in (job_data.get("public_ip_list") or []):
            public_ip_list.append(
                PublicIpConfig(id=ip_cfg.get("id"), public_ip=ip_cfg.get("public_ip"), type=ip_cfg.get("type"))
            )

        return CreateJobReq(
            base_info=base_info,
            source_endpoint=src_eps,
            target_endpoint=tgt_eps,
            node_info=node_info,
            public_ip_list=public_ip_list or None,
        )

    def _show_job(self, job_id, detail_type="detail", query_id=None):
        req = ShowJobDetailRequest(job_id=job_id, type=detail_type, query_id=query_id)
        resp = self._call_with_retry("show_job_detail", self.client.show_job_detail, req)
        return (self._to_dict(resp) or {}).get("job", {})

    @staticmethod
    def _normalize_done_status(raw_status):
        status = (raw_status or "").upper()
        if status in {"SUCCESS", "SUCCEEDED", "COMPLETED", "COMPLETE", "FINISHED", "FINISH"}:
            return "SUCCESS"
        if status in {"FAIL", "FAILED", "ERROR"}:
            return "FAILED"
        return "RUNNING"

    def create_job(self, payload):
        req_body = SingleCreateJobReq(job=self._build_create_job_req(payload))
        req = CreateJobRequest(body=req_body)
        resp = self._call_with_retry("create_job", self.client.create_job, req)
        result = self._to_dict(resp) or {}
        logger.info("DRS job created: %s", result.get("id", "unknown"))
        return result

    def get_job_status(self, job_id):
        detail = self._show_job(job_id, detail_type="detail")
        return {"status": detail.get("status", "UNKNOWN"), "job": detail}

    def test_connection(self, job_id, endpoint_type="so"):
        detail = self._show_job(job_id, detail_type="detail")

        role = "so" if endpoint_type == "so" else "ta"
        endpoints_key = "source_endpoint" if role == "so" else "target_endpoint"
        endpoints = detail.get(endpoints_key) or []
        selected = None
        for ep in endpoints:
            if (ep.get("endpoint_role") or "").lower() == role:
                selected = ep
                break
        if not selected and endpoints:
            selected = endpoints[0]
        if not selected:
            raise RuntimeError(f"No endpoint found for role={role} in job detail")

        action_params = ActionParams(endpoints=[self._build_job_endpoint(selected)])
        action = ActionReq(action_name="network", action_params=action_params)
        req = ExecuteJobActionRequest(job_id=job_id, body=JobActionReq(job=action))
        action_resp = self._call_with_retry("execute_job_action_network", self.client.execute_job_action, req)
        action_result = self._to_dict(action_resp) or {}

        target_ip = ((selected.get("endpoint") or {}).get("ip") or "").strip()
        query_id = action_result.get("query_id")
        timeout = 180
        interval = 5
        elapsed = 0
        final_item = None

        while elapsed <= timeout:
            job = self._show_job(job_id, detail_type="network", query_id=query_id)
            network_results = job.get("network_results") or []
            if network_results:
                if target_ip:
                    for item in network_results:
                        if (item.get("ip") or "").strip() == target_ip:
                            final_item = item
                if final_item is None:
                    final_item = network_results[-1]

                item_status = self._normalize_done_status(final_item.get("status"))
                if item_status in {"SUCCESS", "FAILED"}:
                    break

                success_flag = final_item.get("success")
                if success_flag is True:
                    item_status = "SUCCESS"
                    break
                if success_flag is False:
                    item_status = "FAILED"
                    break

            time.sleep(interval)
            elapsed += interval

        if final_item is None:
            return {
                "status": "RUNNING",
                "query_id": action_result.get("query_id"),
                "message": "network test result not ready",
            }

        success = final_item.get("success") is True
        status = "SUCCESS" if success else self._normalize_done_status(final_item.get("status"))
        if status == "RUNNING" and final_item.get("success") is False:
            status = "FAILED"

        return {
            "status": status,
            "query_id": query_id,
            "network_result": final_item,
        }

    def run_precheck(self, job_id):
        action = ActionReq(action_name="precheck", action_params=ActionParams(precheck_mode="forStartJob"))
        req = ExecuteJobActionRequest(job_id=job_id, body=JobActionReq(job=action))
        resp = self._call_with_retry("execute_job_action_precheck", self.client.execute_job_action, req)
        result = self._to_dict(resp) or {}
        self._precheck_query_id_map[job_id] = result.get("query_id")
        return result

    def get_precheck_result(self, job_id):
        query_id = self._precheck_query_id_map.get(job_id)
        detail = self._show_job(job_id, detail_type="precheck", query_id=query_id)
        precheck = detail.get("precheck_result") or {}
        if not precheck and detail:
            precheck = detail

        raw_process_raw = str(precheck.get("process") or "").strip()
        raw_process = raw_process_raw.upper()
        process_percent = None
        if raw_process_raw.endswith("%"):
            try:
                process_percent = int(raw_process_raw.rstrip("%").strip())
            except Exception:  # noqa: BLE001
                process_percent = None

        raw_items = precheck.get("precheck_results") or []
        has_pending_items = False
        if isinstance(raw_items, list):
            has_pending_items = any(not str((item or {}).get("result") or "").strip() for item in raw_items)

        fail_states = {"FAIL", "FAILED", "ERROR"}
        run_states = {"RUNNING", "WAITING", "PENDING", "IN_PROGRESS", "INPROGRESS"}
        done_states = {"PASS", "PASSED", "SUCCESS", "COMPLETED", "COMPLETE", "FINISH", "FINISHED"}

        if raw_process in fail_states:
            overall = "FAILED"
        elif raw_process in run_states:
            overall = "RUNNING"
        elif process_percent is not None:
            if process_percent < 100:
                overall = "RUNNING"
            elif has_pending_items:
                overall = "RUNNING"
            else:
                overall = "COMPLETE"
        elif (precheck.get("result") is True or precheck.get("result") is False or raw_process in done_states) and not has_pending_items:
            overall = "COMPLETE"
        else:
            overall = "RUNNING"

        items = []
        for item in raw_items:
            raw_result = (item.get("result") or "").upper()
            if raw_result in {"PASS", "PASSED", "SUCCESS", "OK", "TRUE"}:
                norm = "PASS"
            elif raw_result in {"FAIL", "FAILED", "ERROR", "FALSE"}:
                norm = "FAIL"
            elif raw_result in {"WARN", "WARNING"}:
                norm = "WARN"
            else:
                norm = raw_result or "PENDING"

            items.append(
                {
                    "name": item.get("item", "unknown"),
                    "status": norm,
                    "message": item.get("failed_reason") or item.get("raw_error_msg") or item.get("data") or "",
                }
            )

        return {
            "status": overall,
            "precheck_status": overall,
            "results": items,
            "precheck_results": items,
            "raw": precheck,
        }

    def start_job(self, job_id):
        action = ActionReq(action_name="start", action_params=ActionParams())
        req = ExecuteJobActionRequest(job_id=job_id, body=JobActionReq(job=action))
        resp = self._call_with_retry("execute_job_action_start", self.client.execute_job_action, req)
        return self._to_dict(resp) or {"status": "accepted"}

    def stop_job(self, job_id):
        action = ActionReq(action_name="stop", action_params=ActionParams())
        req = ExecuteJobActionRequest(job_id=job_id, body=JobActionReq(job=action))
        resp = self._call_with_retry("execute_job_action_stop", self.client.execute_job_action, req)
        return self._to_dict(resp) or {"status": "accepted"}

    def delete_job(self, job_id):
        req = DeleteJobRequest(job_id=job_id)
        resp = self._call_with_retry("delete_job", self.client.delete_job, req)
        return self._to_dict(resp) or {"status": "accepted"}

    def get_job_progress(self, job_id):
        detail = self._show_job(job_id, detail_type="progress")
        progress = detail.get("progress_info") or {}

        delay = progress.get("incr_trans_delay")
        if (delay is None or delay == "") and progress.get("incr_trans_delay_millis"):
            try:
                delay = float(progress.get("incr_trans_delay_millis")) / 1000.0
            except Exception:  # noqa: BLE001
                delay = "N/A"

        return {
            "full_trans": {"progress": progress.get("progress", "N/A")},
            "incr_trans": {"delay": delay if delay is not None else "N/A"},
            "progress_info": progress,
            "transfer_status": progress.get("transfer_status"),
        }

    def _list_compare_job_ids(self, job_id):
        req = ShowHealthCompareJobListRequest(job_id=job_id, offset=0, limit=100)
        resp = self._call_with_retry("show_health_compare_job_list", self.client.show_health_compare_job_list, req)
        data = self._to_dict(resp) or {}
        jobs = data.get("compare_jobs") or []
        return [j.get("id") for j in jobs if j.get("id")]

    def create_compare_task(self, job_id, compare_type="data"):
        before = set(self._list_compare_job_ids(job_id))

        compare_kind = "object" if str(compare_type).lower() == "object" else "lines"
        action = ActionReq(
            action_name="create_compare",
            action_params=ActionParams(compare_task_param=CompareTaskParams(type=compare_kind)),
        )
        req = ExecuteJobActionRequest(job_id=job_id, body=JobActionReq(job=action))
        resp = self._call_with_retry("execute_job_action_create_compare", self.client.execute_job_action, req)
        data = self._to_dict(resp) or {}

        created_id = None
        for _ in range(24):
            after = set(self._list_compare_job_ids(job_id))
            new_ids = [x for x in after if x not in before]
            if new_ids:
                created_id = sorted(new_ids)[-1]
                break
            time.sleep(5)

        if created_id:
            self._compare_task_job_map[created_id] = job_id
            return {"id": created_id, "compare_task_id": created_id, "status": "accepted", "query_id": data.get("query_id")}

        return {"status": "accepted", "query_id": data.get("query_id")}

    def get_compare_result(self, compare_task_id):
        job_id = self._compare_task_job_map.get(compare_task_id)
        if not job_id:
            return {"status": "RUNNING", "error": "compare task mapping not found", "compare_task_id": compare_task_id}

        detail_req = ShowHealthCompareJobDetailRequest(job_id=job_id, compare_job_id=compare_task_id)
        detail_resp = self._call_with_retry(
            "show_health_compare_job_detail", self.client.show_health_compare_job_detail, detail_req
        )
        detail = self._to_dict(detail_resp) or {}

        prog_req = ShowCompareProgressRequest(job_id=job_id, compare_job_id=compare_task_id)
        prog_resp = self._call_with_retry("show_compare_progress", self.client.show_compare_progress, prog_req)
        progress = self._to_dict(prog_resp) or {}

        status = self._normalize_done_status(detail.get("status"))

        full_info = progress.get("full_info") or {}
        incre_info = progress.get("incre_info") or {}
        diff_count = full_info.get("recheck_entities")
        if diff_count is None:
            diff_count = incre_info.get("recheck_entities")
        if diff_count is None:
            diff_count = 0

        return {
            "status": status,
            "compare_task_id": compare_task_id,
            "detail": detail,
            "progress": progress,
            "diff_count": diff_count,
        }

    def update_job(self, job_id, payload):
        raise NotImplementedError(
            "update_job is not implemented for this automation path. "
            "Use dedicated v5 update-job APIs when configuration changes are needed."
        )


def get_drs_client():
    """Get a DRS client instance."""
    return DRSClient()
