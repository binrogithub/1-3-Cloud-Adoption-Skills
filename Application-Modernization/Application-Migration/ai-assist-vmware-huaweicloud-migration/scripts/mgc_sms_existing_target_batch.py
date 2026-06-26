#!/usr/bin/env python3
import json
import os
import re
import sys
import time
from typing import Dict, List, Optional, Tuple

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from mgc_migrate import (
    Config,
    HcApiClient,
    cleanup_terminal_tasks_for_source,
    create_sms_migproject,
    create_sms_task,
    get_candidate_eip_types,
    get_server_fixed_and_floating_ip,
    get_server_primary_fixed_ip,
    get_server_primary_floating_ip,
    get_server_security_group_ids,
    get_server_vpc_id,
    get_sms_source_detail,
    get_sms_source_server,
    get_vpc_default_security_group_id,
    has_security_group_rule,
    list_sms_tasks,
    normalize_ip_prefix,
    print_step,
    start_sms_task,
    get_sms_task_state,
    unique_nonempty,
    write_json_file,
)


class SecurityGroupRuleQuotaExceeded(RuntimeError):
    pass


def env_required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError("Missing required environment variable: %s" % name)
    return value


def env_default(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip()


def env_default_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return int(raw.strip())


def env_csv(name: str) -> List[str]:
    raw = os.getenv(name, "")
    out: List[str] = []
    for item in raw.split(","):
        val = item.strip()
        if val and val not in out:
            out.append(val)
    return out


def list_projects(client: HcApiClient) -> List[dict]:
    rsp = client.request_json("GET", "https://iam.myhuaweicloud.com/v3/projects", params={"enabled": "true"})
    return rsp.get("projects", []) or []


def get_project_name_by_id(client: HcApiClient, project_id: str) -> str:
    for p in list_projects(client):
        if str(p.get("id") or "").strip() == project_id:
            return str(p.get("name") or "").strip()
    return ""


def try_get_ecs_server(client: HcApiClient, region: str, project_id: str, server_id: str) -> Optional[dict]:
    try:
        rsp = client.request_json(
            "GET",
            "https://ecs.%s.myhuaweicloud.com/v1/%s/cloudservers/%s" % (region, project_id, server_id),
        )
    except Exception:
        return None
    return rsp.get("server") or None


def find_source_server(
    source_client: HcApiClient,
    source_vm_id: str,
    preferred_region: str,
    preferred_project_id: str,
) -> dict:
    projects = list_projects(source_client)
    if not projects:
        raise RuntimeError("No IAM projects found for source account")

    checked: List[Tuple[str, str]] = []

    def candidates() -> List[Tuple[str, str]]:
        out: List[Tuple[str, str]] = []
        if preferred_region and preferred_project_id:
            out.append((preferred_region, preferred_project_id))
        for p in projects:
            region = str(p.get("name") or "").strip()
            pid = str(p.get("id") or "").strip()
            if not region or not pid:
                continue
            pair = (region, pid)
            if pair not in out:
                out.append(pair)
        return out

    for region, pid in candidates():
        checked.append((region, pid))
        server = try_get_ecs_server(source_client, region, pid, source_vm_id)
        if not server:
            continue
        return {
            "source_vm_id": source_vm_id,
            "source_region": region,
            "source_project_id": pid,
            "source_name": str(server.get("name") or ""),
            "source_fixed_ip": get_server_primary_fixed_ip(server),
            "source_floating_ip": get_server_primary_floating_ip(server),
        }

    raise RuntimeError(
        "Source ECS not found for id=%s. Checked projects=%s" % (
            source_vm_id,
            json.dumps(checked, ensure_ascii=False),
        )
    )


def list_project_servers(client: HcApiClient, region: str, project_id: str) -> List[dict]:
    rsp = client.request_json(
        "GET",
        "https://ecs.%s.myhuaweicloud.com/v1/%s/cloudservers/detail" % (region, project_id),
        params={"limit": "200"},
    )
    return rsp.get("servers", []) or []


def find_target_server_by_fixed_ip(
    dest_client: HcApiClient,
    target_fixed_ip: str,
    preferred_region: str,
    preferred_project_id: str,
) -> dict:
    projects = list_projects(dest_client)
    if not projects:
        raise RuntimeError("No IAM projects found for destination account")

    search_pairs: List[Tuple[str, str]] = []
    if preferred_region and preferred_project_id:
        search_pairs.append((preferred_region, preferred_project_id))
    for p in projects:
        region = str(p.get("name") or "").strip()
        pid = str(p.get("id") or "").strip()
        if not region or not pid:
            continue
        pair = (region, pid)
        if pair not in search_pairs:
            search_pairs.append(pair)

    for region, pid in search_pairs:
        try:
            servers = list_project_servers(dest_client, region, pid)
        except Exception:
            continue
        for s in servers:
            fixed = get_server_primary_fixed_ip(s)
            if fixed != target_fixed_ip:
                continue
            return {
                "target_vm_id": str(s.get("id") or ""),
                "target_name": str(s.get("name") or ""),
                "target_region": region,
                "target_project_id": pid,
                "target_project_name": region,
                "target_fixed_ip": fixed,
                "target_floating_ip": get_server_primary_floating_ip(s),
                "target_status": str(s.get("status") or ""),
                "target_vpc_id": get_server_vpc_id(s),
            }

    raise RuntimeError("Destination ECS not found by fixed_ip=%s" % target_fixed_ip)


def find_port_id_for_server(
    client: HcApiClient,
    region: str,
    project_id: str,
    server_id: str,
    fixed_ip: str,
) -> str:
    rsp = client.request_json(
        "GET",
        "https://vpc.%s.myhuaweicloud.com/v1/%s/ports" % (region, project_id),
        params={"device_id": server_id},
    )
    ports = rsp.get("ports", []) or []
    if not ports:
        raise RuntimeError("No VPC port found for server=%s" % server_id)

    for p in ports:
        for ip_item in p.get("fixed_ips", []) or []:
            if str(ip_item.get("ip_address") or "").strip() == fixed_ip:
                pid = str(p.get("id") or "").strip()
                if pid:
                    return pid

    pid = str(ports[0].get("id") or "").strip()
    if not pid:
        raise RuntimeError("No valid port id found for server=%s" % server_id)
    return pid


def ensure_target_eip(
    client: HcApiClient,
    region: str,
    project_id: str,
    server_id: str,
    fixed_ip: str,
    bandwidth_mbps: int,
) -> str:
    _, floating_ip = get_server_fixed_and_floating_ip(client, region, project_id, server_id)
    if floating_ip:
        return floating_ip

    port_id = find_port_id_for_server(client, region, project_id, server_id, fixed_ip)
    discovered = get_candidate_eip_types(client, region, project_id)
    eip_types: List[str] = []
    for candidate in ["5_bgp"] + list(discovered):
        val = str(candidate or "").strip()
        if not val:
            continue
        # v1 create endpoint expects pool type like "5_bgp", not "EIP".
        if "_" not in val:
            continue
        if val not in eip_types:
            eip_types.append(val)
    if not eip_types:
        eip_types = ["5_bgp"]

    def try_rebind_idle_eip() -> str:
        rsp = client.request_json(
            "GET",
            "https://vpc.%s.myhuaweicloud.com/v1/%s/publicips" % (region, project_id),
        )
        publicips = rsp.get("publicips", []) or []
        for item in publicips:
            eip_id = str(item.get("id") or "").strip()
            old_port_id = str(item.get("port_id") or "").strip()
            if not eip_id or not old_port_id:
                continue
            try:
                port_rsp = client.request_json(
                    "GET",
                    "https://vpc.%s.myhuaweicloud.com/v1/%s/ports/%s" % (region, project_id, old_port_id),
                )
            except Exception:
                continue
            port = port_rsp.get("port") or {}
            # Only reuse detached EIPs to avoid impacting running ECS.
            if str(port.get("device_id") or "").strip():
                continue
            client.request_json(
                "PUT",
                "https://vpc.%s.myhuaweicloud.com/v1/%s/publicips/%s" % (region, project_id, eip_id),
                body={"publicip": {"port_id": None}},
            )
            try:
                client.request_json(
                    "PUT",
                    "https://vpc.%s.myhuaweicloud.com/v1/%s/publicips/%s" % (region, project_id, eip_id),
                    body={"publicip": {"port_id": port_id}},
                )
            except Exception as exc:
                err = str(exc).lower()
                if "vpc.0510" in err and "already associated with port" in err:
                    # Keep best effort when backend association state is still converging.
                    time.sleep(2)
                    client.request_json(
                        "PUT",
                        "https://vpc.%s.myhuaweicloud.com/v1/%s/publicips/%s" % (region, project_id, eip_id),
                        body={"publicip": {"port_id": port_id}},
                    )
                else:
                    raise
            for _ in range(30):
                _, floating = get_server_fixed_and_floating_ip(client, region, project_id, server_id)
                if floating:
                    return floating
                time.sleep(2)
        return ""

    last_err: Optional[Exception] = None
    quota_exceeded = False
    for eip_type in eip_types:
        body = {
            "publicip": {"type": eip_type},
            "bandwidth": {
                "name": "vm-migrate-%s" % server_id[:8],
                "size": int(bandwidth_mbps),
                "share_type": "PER",
                "charge_mode": "traffic",
            },
            "port_id": port_id,
        }
        created_eip_id = ""
        try:
            rsp = client.request_json(
                "POST",
                "https://vpc.%s.myhuaweicloud.com/v1/%s/publicips" % (region, project_id),
                body=body,
            )
            created_eip_id = str((rsp.get("publicip") or {}).get("id") or "").strip()
        except Exception as exc:
            last_err = exc
            err = str(exc)
            if "EIP.7905" in err or "quota exceeded" in err.lower():
                quota_exceeded = True
                continue
            if "EIP.7904" in err or "not available" in err.lower():
                continue
            if "already" in err.lower() and "bound" in err.lower():
                break
            continue

        for _ in range(60):
            _, floating_ip = get_server_fixed_and_floating_ip(client, region, project_id, server_id)
            if floating_ip:
                return floating_ip
            time.sleep(3)

        # Some regions return success but do not actually bind in create path.
        if created_eip_id:
            try:
                client.request_json(
                    "PUT",
                    "https://vpc.%s.myhuaweicloud.com/v1/%s/publicips/%s"
                    % (region, project_id, created_eip_id),
                    body={"publicip": {"port_id": port_id}},
                )
            except Exception:
                pass

            for _ in range(30):
                _, floating_ip = get_server_fixed_and_floating_ip(client, region, project_id, server_id)
                if floating_ip:
                    return floating_ip
                time.sleep(2)

    _, floating_ip = get_server_fixed_and_floating_ip(client, region, project_id, server_id)
    if floating_ip:
        return floating_ip

    if quota_exceeded:
        floating_ip = try_rebind_idle_eip()
        if floating_ip:
            return floating_ip

    if last_err is not None:
        raise RuntimeError("Failed to create/bind EIP for server=%s: %s" % (server_id, str(last_err)))
    raise RuntimeError("Failed to create/bind EIP for server=%s" % server_id)


def create_target_sg_rule(
    client: HcApiClient,
    region: str,
    project_id: str,
    security_group_id: str,
    direction: str,
    remote_ip_prefix: str,
    description: str,
) -> bool:
    body = {
        "security_group_rule": {
            "security_group_id": security_group_id,
            "direction": direction,
            "ethertype": "IPv4",
            "remote_ip_prefix": normalize_ip_prefix(remote_ip_prefix),
            "description": description,
        }
    }
    try:
        client.request_json(
            "POST",
            "https://vpc.%s.myhuaweicloud.com/v1/%s/security-group-rules" % (region, project_id),
            body=body,
        )
        return True
    except Exception as exc:
        err = str(exc).lower()
        if "vpc.0614" in err or "quota exceeded" in err:
            raise SecurityGroupRuleQuotaExceeded(str(exc))
        if (
            "already exists" in err
            or "already exist" in err
            or "security group rule has existed" in err
            or "vpc.0608" in err
        ):
            return False
        raise


def find_or_create_migration_security_group(
    client: HcApiClient,
    region: str,
    project_id: str,
    vpc_id: str,
    description: str,
    target_server_id: str,
) -> str:
    name = "vm-migration-%s" % target_server_id[:8]

    def find_existing() -> str:
        rsp = client.request_json(
            "GET",
            "https://vpc.%s.myhuaweicloud.com/v1/%s/security-groups" % (region, project_id),
            params={"vpc_id": vpc_id},
        )
        for sg in rsp.get("security_groups", []) or []:
            if str(sg.get("name") or "").strip() == name:
                sg_id = str(sg.get("id") or "").strip()
                if sg_id:
                    return sg_id
        return ""

    existing = find_existing()
    if existing:
        return existing

    try:
        rsp = client.request_json(
            "POST",
            "https://vpc.%s.myhuaweicloud.com/v1/%s/security-groups" % (region, project_id),
            body={"security_group": {"name": name, "description": description, "vpc_id": vpc_id}},
        )
        sg_id = str((rsp.get("security_group") or {}).get("id") or "").strip()
        if sg_id:
            return sg_id
    except Exception as exc:
        err = str(exc).lower()
        if "already exists" not in err and "already exist" not in err:
            raise

    existing = find_existing()
    if existing:
        return existing
    raise RuntimeError("Failed to create/find migration security group '%s'" % name)


def attach_security_group_to_server(
    client: HcApiClient,
    region: str,
    project_id: str,
    server_id: str,
    security_group_id: str,
) -> bool:
    rsp = client.request_json(
        "GET",
        "https://ecs.%s.myhuaweicloud.com/v1/%s/cloudservers/%s" % (region, project_id, server_id),
    )
    server = rsp.get("server") or {}
    sg_ids = get_server_security_group_ids(server)
    if security_group_id in sg_ids:
        return False

    try:
        client.request_json(
            "POST",
            "https://ecs.%s.myhuaweicloud.com/v1/%s/cloudservers/%s/action" % (region, project_id, server_id),
            body={"addSecurityGroup": {"id": security_group_id}},
        )
        return True
    except Exception as exc:
        err = str(exc).lower()
        if "already" in err and "security group" in err:
            return False
        raise


def ensure_target_security_group_rules(
    client: HcApiClient,
    region: str,
    project_id: str,
    target_server_id: str,
    target_vpc_id: str,
    source_fixed_ip: str,
    source_floating_ip: str,
    description: str,
) -> Dict[str, object]:
    server_rsp = client.request_json(
        "GET",
        "https://ecs.%s.myhuaweicloud.com/v1/%s/cloudservers/%s" % (region, project_id, target_server_id),
    )
    server = server_rsp.get("server") or {}

    sg_ids = get_server_security_group_ids(server)
    fallback_default_sg = ""
    if not sg_ids:
        fallback_default_sg = get_vpc_default_security_group_id(client, region, project_id, target_vpc_id)
        sg_ids = [fallback_default_sg]

    peer_ips = unique_nonempty([source_fixed_ip, source_floating_ip])
    required_pairs: List[Tuple[str, str]] = []
    for peer in peer_ips:
        for direction in ("ingress", "egress"):
            required_pairs.append((direction, peer))

    if not required_pairs:
        return {
            "target_security_group_ids": sg_ids,
            "target_vpc_default_security_group_id": fallback_default_sg,
            "target_security_group_rules_created": 0,
            "target_peer_ips": peer_ips,
            "target_migration_security_group_id": "",
        }

    sg_rules: Dict[str, List[dict]] = {}
    for sg_id in sg_ids:
        sg = client.request_json(
            "GET",
            "https://vpc.%s.myhuaweicloud.com/v1/%s/security-groups/%s" % (region, project_id, sg_id),
        ).get("security_group") or {}
        sg_rules[sg_id] = sg.get("security_group_rules", []) or []

    def list_missing_pairs() -> List[Tuple[str, str]]:
        missing: List[Tuple[str, str]] = []
        for direction, peer in required_pairs:
            covered = False
            for rules in sg_rules.values():
                if has_security_group_rule(rules, direction, peer):
                    covered = True
                    break
            if not covered:
                missing.append((direction, peer))
        return missing

    created = 0
    missing = list_missing_pairs()

    # Add missing rules to as few attached SGs as possible (least-rule SG first).
    candidate_sg_ids = sorted(sg_ids, key=lambda x: len(sg_rules.get(x, [])))
    for sg_id in candidate_sg_ids:
        if not missing:
            break

        quota_hit = False
        for direction, peer in list(missing):
            try:
                added = create_target_sg_rule(
                    client=client,
                    region=region,
                    project_id=project_id,
                    security_group_id=sg_id,
                    direction=direction,
                    remote_ip_prefix=peer,
                    description=description,
                )
            except SecurityGroupRuleQuotaExceeded:
                quota_hit = True
                break

            if added:
                created += 1
            # Keep in-memory rules in sync for duplicate-race and next checks.
            sg_rules.setdefault(sg_id, []).append(
                {
                    "direction": direction,
                    "ethertype": "IPv4",
                    "remote_ip_prefix": normalize_ip_prefix(peer),
                }
            )
            missing = list_missing_pairs()
        if quota_hit:
            continue

    migration_sg_id = ""
    if missing:
        # Existing SGs are full. Create/attach a dedicated migration SG and write only missing rules there.
        migration_sg_id = find_or_create_migration_security_group(
            client=client,
            region=region,
            project_id=project_id,
            vpc_id=target_vpc_id,
            description=description,
            target_server_id=target_server_id,
        )
        attached = attach_security_group_to_server(
            client=client,
            region=region,
            project_id=project_id,
            server_id=target_server_id,
            security_group_id=migration_sg_id,
        )
        if attached:
            sg_ids.append(migration_sg_id)

        migration_rules = client.request_json(
            "GET",
            "https://vpc.%s.myhuaweicloud.com/v1/%s/security-groups/%s" % (region, project_id, migration_sg_id),
        ).get("security_group") or {}
        sg_rules[migration_sg_id] = migration_rules.get("security_group_rules", []) or []

        for direction, peer in list(missing):
            if has_security_group_rule(sg_rules[migration_sg_id], direction, peer):
                continue
            if create_target_sg_rule(
                client=client,
                region=region,
                project_id=project_id,
                security_group_id=migration_sg_id,
                direction=direction,
                remote_ip_prefix=peer,
                description=description,
            ):
                created += 1
                sg_rules[migration_sg_id].append(
                    {
                        "direction": direction,
                        "ethertype": "IPv4",
                        "remote_ip_prefix": normalize_ip_prefix(peer),
                    }
                )
        missing = list_missing_pairs()
        if missing:
            raise RuntimeError(
                "Failed to ensure destination SG rules for target=%s, missing=%s"
                % (target_server_id, json.dumps(missing, ensure_ascii=False))
            )

    return {
        "target_security_group_ids": sg_ids,
        "target_vpc_default_security_group_id": fallback_default_sg,
        "target_security_group_rules_created": created,
        "target_peer_ips": peer_ips,
        "target_migration_security_group_id": migration_sg_id,
    }


def make_cfg_for_task(
    source_vm_id: str,
    source_region: str,
    target_region: str,
    target_region_name: str,
    target_server_name: str,
    sms_endpoint: str,
    eip_bandwidth_mbps: int,
    result_path: str,
) -> Config:
    return Config(
        ak="",
        sk="",
        source_server_id=source_vm_id,
        source_region=source_region,
        target_region=target_region,
        target_region_name=target_region_name,
        target_vpc_name="",
        target_vpc_cidr="",
        target_subnet_cidr="",
        target_image_id="existing-target",
        target_server_name=target_server_name,
        target_flavor_id="",
        target_admin_password="",
        eip_bandwidth_mbps=eip_bandwidth_mbps,
        root_volume_type="SSD",
        data_volume_type="SSD",
        sms_endpoint=sms_endpoint,
        preferred_migration_method="sms",
        enable_rsync_fallback=False,
        source_private_ip="",
        extra_peer_ips=[],
        rsync_source_host="",
        rsync_source_port=22,
        rsync_source_user="root",
        rsync_source_password="",
        rsync_target_host="",
        rsync_target_port=22,
        rsync_target_user="root",
        rsync_target_password="",
        rsync_source_paths=["/"],
        rsync_staging_dir="/tmp",
        rsync_incremental_rounds=1,
        rsync_timeout_sec=1200,
        rsync_common_args="",
        rsync_excludes=[],
        rsync_cutover_stop_cmd="",
        rsync_cutover_start_cmd="",
        rsync_target_finalize_cmd="",
        enable_vpn_bridge=False,
        enable_target_vpn_client=False,
        vpn_server_public_ip="",
        vpn_server_port=1194,
        vpn_client_common_name="",
        vpn_client_static_ip="",
        result_path=result_path,
    )


def resolve_region_name_from_tasks(client: HcApiClient, sms_endpoint: str, region_id: str) -> str:
    try:
        for t in list_sms_tasks(client, sms_endpoint):
            if str(t.get("region_id") or "").strip() == region_id:
                val = str(t.get("region_name") or "").strip()
                if val:
                    return val
    except Exception:
        pass

    default_map = {
        "ap-southeast-3": "AP-Singapore",
        "ap-southeast-4": "AP-Bangkok",
    }
    return default_map.get(region_id, region_id)


def main() -> int:
    source_ak = env_required("SOURCE_ACCESS_KEY")
    source_sk = env_required("SOURCE_SECRET_KEY")
    source_region_hint = env_default("SOURCE_REGION", "")
    source_project_id_hint = env_default("SOURCE_PROJECT_ID", "")

    dest_ak = env_required("DESTINATION_ACCESS_KEY")
    dest_sk = env_required("DESTINATION_SECRET_KEY")
    dest_region_hint = env_default("DESTINATION_REGION", "")
    dest_project_id_hint = env_default("DESTINATION_PROJECT_ID", "")
    dest_region_name_input = env_default("DESTINATION_REGION_NAME", "")

    source_server_ids = env_csv("SOURCE_SERVER_IDS")
    if not source_server_ids:
        raise RuntimeError("SOURCE_SERVER_IDS is empty")

    sms_endpoint = env_default("SMS_ENDPOINT", "https://sms.ap-southeast-3.myhuaweicloud.com").rstrip("/")
    eip_bandwidth_mbps = env_default_int("EIP_BANDWIDTH_MBPS", 100)
    sg_rule_description = env_default("SG_RULE_DESCRIPTION", "虚拟机迁移")
    result_path = env_default("RESULT_PATH", "./out/migration_result.json")

    source_client = HcApiClient(source_ak, source_sk)
    dest_client = HcApiClient(dest_ak, dest_sk)

    print_step("Accepting SMS privacy agreements on destination account")
    dest_client.request_json("POST", "%s/v3/privacy-agreements" % sms_endpoint, body={})

    resolved_items: List[dict] = []
    used_target_vm_ids: Dict[str, str] = {}

    for source_vm_id in source_server_ids:
        print_step("Resolving source ECS and destination target ECS for %s" % source_vm_id)
        source_item = find_source_server(
            source_client=source_client,
            source_vm_id=source_vm_id,
            preferred_region=source_region_hint,
            preferred_project_id=source_project_id_hint,
        )
        source_fixed_ip = str(source_item.get("source_fixed_ip") or "").strip()
        if not source_fixed_ip:
            raise RuntimeError("Source VM %s has no fixed IP" % source_vm_id)

        target_item = find_target_server_by_fixed_ip(
            dest_client=dest_client,
            target_fixed_ip=source_fixed_ip,
            preferred_region=dest_region_hint,
            preferred_project_id=dest_project_id_hint,
        )

        target_vm_id = str(target_item.get("target_vm_id") or "").strip()
        if not target_vm_id:
            raise RuntimeError("Mapped target VM id is empty for source %s" % source_vm_id)
        if target_vm_id in used_target_vm_ids:
            raise RuntimeError(
                "Target VM %s is mapped by multiple sources: %s and %s"
                % (target_vm_id, used_target_vm_ids[target_vm_id], source_vm_id)
            )
        used_target_vm_ids[target_vm_id] = source_vm_id

        resolved_items.append(
            {
                **source_item,
                **target_item,
            }
        )

    target_region_set = sorted({str(x.get("target_region") or "").strip() for x in resolved_items})
    target_project_set = sorted({str(x.get("target_project_id") or "").strip() for x in resolved_items})
    if len(target_region_set) != 1 or len(target_project_set) != 1:
        raise RuntimeError(
            "Target ECS mappings are not in one region/project: regions=%s projects=%s"
            % (json.dumps(target_region_set, ensure_ascii=False), json.dumps(target_project_set, ensure_ascii=False))
        )

    target_region = target_region_set[0]
    target_project_id = target_project_set[0]
    target_project_name = str(resolved_items[0].get("target_project_name") or target_region)

    target_region_name = dest_region_name_input or resolve_region_name_from_tasks(dest_client, sms_endpoint, target_region)
    print_step("Using target region=%s project=%s region_name=%s" % (target_region, target_project_id, target_region_name))

    migproject_id = ""
    migproject_error = ""
    try:
        seed = resolved_items[0]
        seed_cfg = make_cfg_for_task(
            source_vm_id=str(seed.get("source_vm_id") or "seed"),
            source_region=str(seed.get("source_region") or ""),
            target_region=target_region,
            target_region_name=target_region_name,
            target_server_name=str(seed.get("target_name") or "target"),
            sms_endpoint=sms_endpoint,
            eip_bandwidth_mbps=eip_bandwidth_mbps,
            result_path=result_path,
        )
        print_step("Creating SMS migration project")
        migproject_id = create_sms_migproject(dest_client, seed_cfg)
    except Exception as exc:
        migproject_error = str(exc)
        print_step("Create migration project failed, continue with existing projects: %s" % migproject_error)

    results: List[dict] = []

    for item in resolved_items:
        source_vm_id = str(item.get("source_vm_id") or "")
        source_name = str(item.get("source_name") or "")
        source_fixed_ip = str(item.get("source_fixed_ip") or "")
        source_floating_ip = str(item.get("source_floating_ip") or "")
        source_region = str(item.get("source_region") or "")

        target_vm_id = str(item.get("target_vm_id") or "")
        target_name = str(item.get("target_name") or "")
        target_vpc_id = str(item.get("target_vpc_id") or "")

        print_step("Ensuring EIP on target VM %s (%s)" % (target_vm_id, target_name))
        target_floating_ip = ensure_target_eip(
            client=dest_client,
            region=target_region,
            project_id=target_project_id,
            server_id=target_vm_id,
            fixed_ip=str(item.get("target_fixed_ip") or ""),
            bandwidth_mbps=eip_bandwidth_mbps,
        )

        print_step("Ensuring destination security group rules for target VM %s" % target_vm_id)
        sg_result = ensure_target_security_group_rules(
            client=dest_client,
            region=target_region,
            project_id=target_project_id,
            target_server_id=target_vm_id,
            target_vpc_id=target_vpc_id,
            source_fixed_ip=source_fixed_ip,
            source_floating_ip=source_floating_ip,
            description=sg_rule_description,
        )

        print_step("Resolving SMS source object for %s" % source_vm_id)
        sms_source = get_sms_source_server(
            dest_client,
            sms_endpoint,
            source_vm_id,
            fallback_name=source_name,
            fallback_ip=source_fixed_ip,
        )
        source_sms_id = str(sms_source.get("id") or "").strip()
        if not source_sms_id:
            raise RuntimeError("SMS source id is empty for source vm %s" % source_vm_id)
        sms_source_detail = get_sms_source_detail(dest_client, sms_endpoint, source_sms_id)

        cleanup_result = cleanup_terminal_tasks_for_source(dest_client, sms_endpoint, source_sms_id)
        active_tasks = cleanup_result.get("active_tasks") or []
        if active_tasks:
            raise RuntimeError(
                "Source %s still has active SMS tasks: %s"
                % (source_vm_id, json.dumps(active_tasks, ensure_ascii=False))
            )

        task_cfg = make_cfg_for_task(
            source_vm_id=source_vm_id,
            source_region=source_region,
            target_region=target_region,
            target_region_name=target_region_name,
            target_server_name=target_name,
            sms_endpoint=sms_endpoint,
            eip_bandwidth_mbps=eip_bandwidth_mbps,
            result_path=result_path,
        )

        print_step("Creating SMS task for source %s -> target %s" % (source_vm_id, target_vm_id))
        task_id = create_sms_task(
            client=dest_client,
            cfg=task_cfg,
            source_sms_id=source_sms_id,
            source_server=sms_source_detail,
            target_vm_id=target_vm_id,
            target_project_id=target_project_id,
            target_project_name=target_project_name,
        )

        print_step("Starting SMS task %s" % task_id)
        start_sms_task(dest_client, sms_endpoint, task_id)
        task_state = get_sms_task_state(dest_client, sms_endpoint, task_id)

        results.append(
            {
                "source_vm_id": source_vm_id,
                "source_name": source_name,
                "source_region": source_region,
                "source_project_id": str(item.get("source_project_id") or ""),
                "source_fixed_ip": source_fixed_ip,
                "source_floating_ip": source_floating_ip,
                "source_sms_server_id": source_sms_id,
                "target_vm_id": target_vm_id,
                "target_name": target_name,
                "target_region": target_region,
                "target_project_id": target_project_id,
                "target_fixed_ip": str(item.get("target_fixed_ip") or ""),
                "target_floating_ip": target_floating_ip,
                "target_security_group_ids": sg_result.get("target_security_group_ids", []),
                "target_security_group_rules_created": sg_result.get("target_security_group_rules_created", 0),
                "target_peer_ips": sg_result.get("target_peer_ips", []),
                "precheck_task_cleanup": cleanup_result,
                "task_id": task_id,
                "task_state": task_state,
            }
        )

    output = {
        "mode": "sms_existing_target_batch",
        "requested_source_server_ids": source_server_ids,
        "source_project_id_input": source_project_id_hint,
        "source_region_input": source_region_hint,
        "destination_project_id_input": dest_project_id_hint,
        "destination_region_input": dest_region_hint,
        "resolved_target_project_id": target_project_id,
        "resolved_target_region": target_region,
        "resolved_target_region_name": target_region_name,
        "migration_project_id": migproject_id,
        "migration_project_create_error": migproject_error,
        "security_group_rule_description": sg_rule_description,
        "eip_bandwidth_mbps": eip_bandwidth_mbps,
        "results": results,
        "generated_at": int(time.time()),
    }

    write_json_file(result_path, output)
    print_step("Completed batch migration start. Result written to %s" % result_path)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("[MGC-BATCH][ERROR] %s" % str(exc), file=sys.stderr)
        sys.exit(1)
