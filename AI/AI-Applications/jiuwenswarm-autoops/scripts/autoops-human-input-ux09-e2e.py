#!/usr/bin/env python3
"""Run the UX-09 acceptance matrix against project-owned boundaries.

The matrix uses temporary profiles and state for deterministic checks.  A
real TUI history is accepted only when supplied (or when the known live test
history exists); it is never synthesized by this script.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from autoops_context import resolve
from autoops_intent import is_host_system_request, parse_request, parse_time_window
from autoops_project_manager import classify, user_view


def profile(profile_id="orders-v1", *, target="host-a", environment="prod", display_name="订单服务"):
    return {
        "schema_version": 1, "profile_id": profile_id, "application_id": "orders",
        "application": "orders", "display_name": display_name,
        "visibility": "customer", "lifecycle": "active",
        "canonical_object_id": "orders:prod:host-a",
        "target_id": target, "scope_id": "orders-prod", "environment": environment,
        "services": [{"service_id": "orders-api", "aliases": ["orders", "orders.service"],
                      "sources": [{"kind": "journal", "unit": "orders-api.service"}]}],
    }


def write_profiles(directory: Path, *values: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for index, value in enumerate(values):
        (directory / f"profile-{index}.json").write_text(
            json.dumps(value, ensure_ascii=False), encoding="utf-8")


def run_json(command: list[str], env: dict[str, str] | None = None) -> dict:
    result = subprocess.run(command, cwd=ROOT, env=env, text=True,
                            capture_output=True, check=False)
    if not result.stdout.strip():
        raise AssertionError(result.stderr.strip() or "command returned no JSON")
    return json.loads(result.stdout)


def check_live_history(history: Path) -> None:
    payload = run_json([sys.executable, str(ROOT / "scripts" / "tui-history-completion-check.py"), str(history)])
    if not payload.get("ready"):
        raise AssertionError(f"TUI history is not complete: {payload}")
    events = []
    for line in history.read_text(encoding="utf-8").splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    calls = [str((event.get("tool_call") or {}).get("arguments", ""))
             for event in events if event.get("event_type") == "chat.tool_call"
             and (event.get("tool_call") or {}).get("name") == "bash"]
    pm_calls = [call for call in calls if "autoops-project-manager.py" in call]
    if not pm_calls or any("--service" in call for call in pm_calls):
        raise AssertionError("live TUI history did not prove a host-system PM call without service")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the UX-09 AutoOps input acceptance matrix.")
    parser.add_argument("--live-history", type=Path,
                        default=Path("/root/.jiuwenswarm/agent/sessions/ux09-live-20260913-r2/history.jsonl"))
    args = parser.parse_args(argv)
    cases = []

    def case(case_id: str, title: str, function, *, live=False):
        try:
            function()
            cases.append({"id": case_id, "title": title, "status": "PASS-" + ("TUI" if live else "BOUNDARY")})
        except Exception as exc:
            cases.append({"id": case_id, "title": title, "status": "FAIL", "error": str(exc)})

    case("UI-AC01", "真实 TUI 主机日志路由", lambda: check_live_history(args.live_history), live=True)
    case("UI-AC02", "默认候选排除测试对象", lambda: _case_hidden_profile())
    case("UI-AC03", "中文显示名与 unit 别名", lambda: _case_aliases())
    case("UI-AC04", "环境目标歧义保留", lambda: _case_ambiguity())
    case("UI-AC05", "等价 profile 去重与多服务歧义", lambda: _case_duplicates())
    case("UI-AC06", "local 目标与 local 应用区分", lambda: _case_local())
    case("UI-AC07", "自然时间解析", lambda: _case_time())
    case("UI-AC08", "空数据不等于正常", lambda: _case_result_states())
    case("UI-AC09", "异常根因联动路由", lambda: _case_root_cause())
    case("UI-AC10", "自然语言查根因", lambda: _case_root_cause())
    case("UI-AC11", "修复动作保持确认门", lambda: _case_confirmation())
    case("UI-AC12", "数据源状态可区分", lambda: _case_result_states())
    case("UI-AC13", "TUI history 完成边界", lambda: check_live_history(args.live_history), live=True)
    case("UI-AC14", "安装策略可发布", lambda: _case_installer())
    case("UI-AC15", "登记路径并复用 profile", lambda: _case_registration())
    case("UI-AC16", "值守状态使用控制入口", lambda: _case_watch_control())
    print(json.dumps({"schema_version": 1, "suite": "UX-09", "cases": cases,
                      "passed": sum(item["status"].startswith("PASS") for item in cases),
                      "failed": sum(item["status"] == "FAIL" for item in cases)},
                     ensure_ascii=False, indent=2))
    return 0 if all(item["status"] != "FAIL" for item in cases) else 1


def _case_hidden_profile():
    with tempfile.TemporaryDirectory() as directory:
        value = profile("demo-test", display_name="AutoOps 演示服务")
        value["visibility"] = "test"
        result = resolve(application="demo", profile_dir=Path(directory))
        write_profiles(Path(directory), value)
        result = resolve(application="demo", profile_dir=Path(directory))
        assert result["status"] == "NOT_FOUND", result


def _case_aliases():
    with tempfile.TemporaryDirectory() as directory:
        write_profiles(Path(directory), profile())
        result = resolve(application="订单服务", profile_dir=Path(directory))
        assert result["status"] == "RESOLVED", result
        result = resolve(service="orders.service", profile_dir=Path(directory))
        assert result["status"] == "RESOLVED", result


def _case_ambiguity():
    with tempfile.TemporaryDirectory() as directory:
        first = profile("orders-prod", target="host-a", environment="prod")
        second = profile("orders-test", target="host-b", environment="test")
        second["canonical_object_id"] = "orders:test:host-b"
        write_profiles(Path(directory), first, second)
        result = resolve(application="orders", profile_dir=Path(directory))
        assert result["status"] == "AMBIGUOUS", result


def _case_duplicates():
    with tempfile.TemporaryDirectory() as directory:
        first = profile("orders-v1")
        second = json.loads(json.dumps(first)); second["profile_id"] = "orders-v2"
        write_profiles(Path(directory), first, second)
        result = resolve(application="orders", profile_dir=Path(directory))
        assert result["status"] == "RESOLVED" and result["deduplicated_profiles"], result


def _case_local():
    assert is_host_system_request("查询本机系统日志")
    assert not is_host_system_request("查看 local 应用日志", application="local")
    assert parse_request("查询本机系统日志")["scope"]["target_ref"] == "local"


def _case_time():
    assert parse_time_window("检查最近一小时日志")["minutes"] == 60
    today = parse_time_window("检查今天的日志")
    assert today["expression"] == "今天" and today["start"].endswith("T00:00:00+08:00")
    assert parse_time_window("检查日志")["minutes"] == 1440


def _case_result_states():
    intent = parse_request("运维 Linux 系统日志")
    assert user_view(intent, "local", {"status": "empty"})["adapter_status"] == "evidence_insufficient"
    assert user_view(intent, "local", {"status": "unavailable"})["adapter_status"] == "data_source_unavailable"
    assert user_view(intent, "local", {"status": "no_anomaly"})["adapter_status"] == "no_anomaly"


def _case_root_cause():
    epic, role = classify("为什么失败", None, "orders-api", "ensure")
    assert (epic, role) == ("E05+E06", "observability-investigator")


def _case_confirmation():
    with tempfile.TemporaryDirectory() as directory:
        env = os.environ | {"AUTOOPS_STATE_DB": str(Path(directory) / "state.db"),
                             "JIUWENSWARM_AUTOOPS_CONFIG_DIR": str(Path(directory) / "config")}
        result = run_json([sys.executable, str(ROOT / "scripts" / "autoops-project-manager.py"),
                           "--request", "预览确保服务运行", "--service", "autoops-demo",
                           "--target", "test-host-01"], env)
        assert result["status"] == "PENDING_CONFIRMATION" and result["execution_mode"] == "dry-run", result


def _case_installer():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        result = run_json([sys.executable, str(ROOT / "scripts" / "install-autoops-runtime.py"),
                           "--source-root", str(ROOT), "--install-root", str(root / "install"),
                           "--config-root", str(root / "etc"), "--state-root", str(root / "state"),
                           "--systemd-root", str(root / "systemd")])
        assert result["status"] == ["READY"]
        policy = json.loads((root / "install/config/autoops-input-policy.json").read_text())
        assert policy["default_scope"] == "host_system"


def _case_registration():
    with tempfile.TemporaryDirectory() as directory:
        profile_dir = Path(directory) / "profiles"
        result = run_json([sys.executable, str(ROOT / "scripts" / "autoops-context-register.py"),
                           "--profile-id", "pay-v1", "--application-id", "payments",
                           "--application", "payments", "--display-name", "支付服务",
                           "--service", "payments-api", "--service-alias", "payments.service",
                           "--target", "host-a", "--scope-id", "payments-prod",
                           "--journal-unit", "payments-api.service", "--profile-dir", str(profile_dir)])
        assert result["status"] == "REGISTERED"
        resolved = resolve(application="支付服务", profile_dir=profile_dir)
        assert resolved["status"] == "RESOLVED"


def _case_watch_control():
    with tempfile.TemporaryDirectory() as directory:
        result = run_json([sys.executable, str(ROOT / "scripts" / "autoops-control.py"),
                           "--action", "status", "--state-dir", directory,
                           "--state-db", str(Path(directory) / "state.db")])
        assert result["status"] == "OK" and result["action"] == "status"


if __name__ == "__main__":
    raise SystemExit(main())
