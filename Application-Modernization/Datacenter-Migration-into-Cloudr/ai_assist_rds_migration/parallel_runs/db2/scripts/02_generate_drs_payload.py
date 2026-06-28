#!/usr/bin/env python3
"""02_generate_drs_payload.py - Generate DRS migration task creation payload."""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from config_loader import get_source_db_config, get_target_db_config, is_dry_run, load_config
from log_utils import get_logger, mask_dict
from report_utils import append_migration_report, generate_report

logger = get_logger("02_generate_drs_payload")


def _first_sg(value):
    if isinstance(value, list):
        return value[0] if value else None
    if isinstance(value, str) and "," in value:
        return value.split(",", 1)[0].strip()
    return value


def _normalize_engine_type(value):
    if not value:
        return "mysql-to-mysql"
    vv = str(value).lower()
    if vv in ("mysql", "mysql-to-mysql"):
        return "mysql-to-mysql"
    return vv


def _resolve_db_type(engine_hint):
    vv = str(engine_hint or "").strip().lower()
    if "postgres" in vv:
        return "postgresql"
    if "mysql" in vv:
        return "mysql"
    return "mysql"


def _normalize_job_direction(value):
    if not value:
        return "up"
    vv = str(value).lower()
    if vv in ("in", "up"):
        return "up"
    if vv in ("out", "down"):
        return "down"
    return vv


def _resolve_endpoint_name(endpoint_type, meta_cfg):
    engine = str(meta_cfg.get("engine") or "mysql").strip().lower()

    if "mysql" in engine:
        if endpoint_type == "cloud":
            return "cloud_mysql"
        if endpoint_type == "ecs":
            return "ecs_mysql"
        return "mysql"
    if "postgres" in engine:
        if endpoint_type == "cloud":
            return "cloud_postgresql"
        if endpoint_type == "ecs":
            return "ecs_postgresql"
        return "postgresql"
    return meta_cfg.get("instance_name") or "mysql"


def _endpoint(role, db_cfg, meta_cfg, project_id, region, default_endpoint_type="cloud", db_type="mysql"):
    # role: so / ta
    ssl_enabled = bool(meta_cfg.get("ssl_enabled", False))
    sg = _first_sg(meta_cfg.get("security_group_id"))
    endpoint_type = str(meta_cfg.get("endpoint_type") or default_endpoint_type).strip().lower()
    endpoint_name = str(meta_cfg.get("endpoint_name") or _resolve_endpoint_name(endpoint_type, meta_cfg)).strip()

    endpoint_data = {
        "endpoint_name": endpoint_name,
        "db_port": str(db_cfg.get("port") or meta_cfg.get("port") or 3306),
        "db_user": db_cfg.get("user"),
        "db_password": db_cfg.get("password"),
    }
    if endpoint_type == "cloud":
        endpoint_data["instance_id"] = meta_cfg.get("instance_id")
        endpoint_data["instance_name"] = meta_cfg.get("instance_name")
    else:
        endpoint_data["ip"] = str(db_cfg.get("host") or meta_cfg.get("server_ip") or meta_cfg.get("eip") or "").strip()

    endpoint = {
        "db_type": db_type,
        "endpoint_type": endpoint_type,
        "endpoint_role": role,
        "endpoint": endpoint_data,
        "ssl": {
            "ssl_link": ssl_enabled,
        },
    }

    if role == "ta":
        endpoint["config"] = {
            "is_target_readonly": bool(meta_cfg.get("is_target_readonly", True)),
        }

    if endpoint_type in ("cloud", "ecs"):
        endpoint["cloud"] = {
            "region": region,
            "project_id": project_id,
        }

    if endpoint_type == "ecs":
        endpoint["vpc"] = {
            "vpc_id": meta_cfg.get("vpc_id"),
            "subnet_id": meta_cfg.get("subnet_id"),
            "security_group_id": sg,
        }

    return endpoint


def build_payload():
    """Build the DRS v5 job creation payload.

    Returns:
        Dictionary with the complete DRS job creation payload.
    """
    config = load_config()
    src_db = get_source_db_config()
    tgt_db = get_target_db_config()

    region = config.get("region")
    source_meta = config.get("source", {})
    target_meta = config.get("target", {})
    src_project = ((config.get("accounts", {}).get("source_account_a", {}) or {}).get("project_id"))
    tgt_project = ((config.get("accounts", {}).get("target_account_b", {}) or {}).get("project_id"))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    job_name = f"{config.get('job_name_prefix', 'drs-migration')}_{timestamp}"

    base_info = {
        "name": job_name,
        "job_type": config.get("job_type", "migration"),
        "engine_type": _normalize_engine_type(config.get("engine_type", "mysql")),
        "job_direction": _normalize_job_direction(config.get("job_direction", "up")),
        "task_type": config.get("task_type", "FULL_INCR_TRANS"),
        "net_type": config.get("net_type", "eip"),
        "charging_mode": config.get("charging_mode", "on_demand"),
        "description": config.get("job_description", ""),
    }

    net_type = str(config.get("net_type", "eip")).strip().lower()
    db_type = _resolve_db_type(config.get("engine_type"))
    src_default_type = "offline" if net_type == "eip" else "cloud"
    tgt_default_type = "cloud"

    source_endpoint = [
        _endpoint(
            "so",
            src_db,
            source_meta,
            src_project,
            region,
            default_endpoint_type=src_default_type,
            db_type=db_type,
        ),
    ]
    target_endpoint = [
        _endpoint(
            "ta",
            tgt_db,
            target_meta,
            tgt_project,
            region,
            default_endpoint_type=tgt_default_type,
            db_type=db_type,
        ),
    ]

    drs_instance = config.get("drs_instance", {})
    node_sg = _first_sg(drs_instance.get("security_group_id")) or _first_sg(target_meta.get("security_group_id"))
    node_vpc_id = target_meta.get("vpc_id")
    node_subnet_id = drs_instance.get("subnet_id") or target_meta.get("subnet_id")

    node_instance_type = str(drs_instance.get("instance_type") or "").strip().lower()
    node_arch = str(drs_instance.get("arch") or "").strip().lower()
    az_cfg = drs_instance.get("az", {}) or {}
    az_primary = (az_cfg.get("primary") or "").strip()
    az_standby = (az_cfg.get("standby") or az_primary).strip()
    if node_instance_type == "single":
        availability_zone = az_primary
    elif node_instance_type:
        availability_zone = f"{az_primary},{az_standby}" if az_primary else ""
    else:
        availability_zone = az_primary

    node_base_info = {
        "availability_zone": availability_zone,
    }
    if node_instance_type:
        node_base_info["instance_type"] = node_instance_type
    if node_arch:
        node_base_info["arch"] = node_arch

    node_info = {
        "spec": {
            "node_type": str(config.get("specification", "high")),
        },
        "vpc": {
            "vpc_id": node_vpc_id,
            "subnet_id": node_subnet_id,
            "security_group_id": node_sg,
        },
        "base_info": node_base_info,
    }

    public_ip_list = []
    if str(config.get("net_type", "")).lower() == "eip":
        eip_id = drs_instance.get("public_ip_id")
        eip_addr = drs_instance.get("public_ip")
        if eip_id or eip_addr:
            public_ip_list.append(
                {
                    "id": eip_id,
                    "public_ip": eip_addr,
                    "type": "master",
                }
            )

    payload = {
        "base_info": base_info,
        "source_endpoint": source_endpoint,
        "target_endpoint": target_endpoint,
        "node_info": node_info,
        "public_ip_list": public_ip_list,
    }

    return payload


def main():
    """Main entry point."""
    start_time = time.time()
    dry_run = is_dry_run()
    logger.info(f"Generating DRS payload (dry_run={dry_run})")

    try:
        payload = build_payload()
    except Exception as e:  # noqa: BLE001
        logger.error(f"Failed to build payload: {e}")
        append_migration_report("generate_payload", "FAILED", details={"error": str(e)})
        sys.exit(1)

    report_path = generate_report("drs_payload", payload, stage="generate_payload", status="SUCCESS")
    logger.info(f"Payload saved to: {report_path}")

    masked_payload = mask_dict(payload)
    logger.info(f"Payload summary:\n{json.dumps(masked_payload, indent=2, ensure_ascii=False)}")

    duration = int(time.time() - start_time)
    append_migration_report("generate_payload", "SUCCESS", duration_seconds=duration)

    logger.info("DRS payload generation completed successfully")
    sys.exit(0)


if __name__ == "__main__":
    main()
