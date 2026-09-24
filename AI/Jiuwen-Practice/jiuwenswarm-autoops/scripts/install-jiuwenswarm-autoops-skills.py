#!/usr/bin/env python3
"""Install AutoOps TUI skills and configure the JiuwenSwarm runtime."""
import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = (
    "autoops-project-manager",
    "autoops-css-auto",
    "autoops-log-investigator",
    "autoops-metrics-observer",
    "autoops-event-investigator",
    "autoops-netops",
    "autoops-runbook-operator",
    "autoops-ansible-operator",
    "autoops-recovery-verifier",
)
BOOTSTRAP_SOURCE = ROOT / "config" / "autoops-agent-bootstrap.md"
BOOTSTRAP_MARKER = "## JiuwenSwarm AutoOps 默认入口"
DEPLOYMENT_MODES = {"preserve-existing", "full-access-test"}
AUTOOPS_LEADER_PERSONA = (
    "AutoOps Project Manager。处理运维请求时先遵循 autoops-project-manager Skill，"
    "在第一次工具调用前选择一个已发布路由；每个用户回合最多调用一次。"
    "明确 NOLI/NetOps/A10 或固网 FTTH/PON/OLT/ONT/BNG/PPPoE 请求只调用一次 ProjectManager NetOps 路由；其写操作由该路由拒绝，不走通用主机恢复。"
    "NetOps 结果带 simulated=true 时，最终答复必须醒目标注为合成演示数据，不能描述为真实客户故障。"
    "恢复、修复、回滚、重启或验证恢复意图优先于诊断；有 service 时只调用一次 orchestrator confirm，"
    "必须保留原 service 并带 --mode confirm --machine-output；返回 INPUT_ERROR/未发布/不支持/等待审批也立即停止，"
    "不得去掉 machine-output 重试、猜 service 名或回退日志、指标、事件、Kubernetes、watch、status 或 workflow。"
    "没有 service 时报告缺少范围并停止，不得先查日志、指标、事件、Kubernetes 或 control 状态。"
    "值守请求只调用一次 watch-policy；用户未提供 profile-ref 时直接报告缺项，不得搜索文件猜测；"
    "缺少 profile 或返回输入边界时立即停止，不得查询 status、"
    "修改其他策略、启动 watcher 或再次复核。"
    "继续刚才的任务若当前会话没有 task_id/result，直接报告 Continuity Gap 并零工具调用结束；"
    "不得调用 view_task、cron、control/status 或搜索其他 workspace 猜测历史任务。"
    "机器输出过大被 TUI 保存到临时文件时，只报告已返回摘要和覆盖边界，不得读取或解析临时文件。"
    "ProjectManager、确定性调查入口、观测适配器和 swarmflow 任一路由返回后，"
    "包括 swarmflow 的 launched、PARTIAL、INCOMPLETE 或 FAILED，立即停止所有工具调用并据此回答。"
    "swarmflow 前不得预检文件；若运行时针对同一 run_id 暴露一次 async_task_output，只允许等待一次，"
    "随后立即结束。不得读取 workflow journal、文件或主机来补证据，不得重复路由，不得把空结果改成更大范围查询。"
    "写操作仍必须使用项目发布的授权边界。"
)


def yaml_key(key):
    """Render the small, fixed set of YAML mapping keys used by this installer."""
    return "'*'" if key == "*" else key


def mapping_bounds(lines, key, indent, start=0, end=None):
    """Find a simple YAML mapping and its indented body without reformatting YAML."""
    end = len(lines) if end is None else end
    prefix = " " * indent + yaml_key(key) + ":"
    for index in range(start, end):
        if lines[index].startswith(prefix) and lines[index][len(prefix):].strip() in {"", "#"}:
            body_end = index + 1
            while body_end < end:
                text = lines[body_end]
                if text and not text.startswith(" " * (indent + 1)) and not text.lstrip().startswith("#"):
                    break
                body_end += 1
            return index, body_end
    return None


def ensure_mapping(lines, path):
    """Ensure a nested block mapping exists and return its body bounds.

    JiuwenSwarm's generated config uses block mappings for these keys. Keeping this
    narrow updater avoids a YAML dependency and preserves comments and unrelated
    customer configuration.
    """
    start, end, indent = 0, len(lines), 0
    for key in path:
        found = mapping_bounds(lines, key, indent, start, end)
        if found is None:
            lines.insert(end, " " * indent + yaml_key(key) + ":\n")
            found = (end, end + 1)
        index, end = found
        start, indent = index + 1, indent + 2
    return start, end, indent


def set_scalar(lines, path, key, value):
    """Set one scalar under a block mapping, preserving all other YAML text."""
    start, end, indent = ensure_mapping(lines, path)
    prefix = " " * indent + yaml_key(key) + ":"
    replacement = f"{prefix} {value}\n"
    for index in range(start, end):
        if lines[index].startswith(prefix):
            lines[index] = replacement
            return
    lines.insert(end, replacement)


def _existing_scalar(lines, path, key):
    """Read a scalar from the narrow YAML subset without creating mappings."""
    start, end, indent = 0, len(lines), 0
    for part in path:
        found = mapping_bounds(lines, part, indent, start, end)
        if found is None:
            return None
        index, end = found
        start, indent = index + 1, indent + 2
    prefix = " " * indent + yaml_key(key) + ":"
    for index in range(start, end):
        if lines[index].startswith(prefix):
            return lines[index][len(prefix):].strip()
    return None


def configure_runtime(config_file, deployment_mode=None):
    """Enable routing policy and apply permission policy only when requested."""
    config_file = Path(config_file).expanduser()
    if not config_file.is_file() or config_file.is_symlink():
        fail(f"JiuwenSwarm config must be a regular file: {config_file}")
    lines = config_file.read_text(encoding="utf-8").splitlines(keepends=True)
    original = list(lines)
    deployment_mode = deployment_mode or os.environ.get("AUTOOPS_DEPLOYMENT_MODE", "preserve-existing")
    if deployment_mode not in DEPLOYMENT_MODES:
        fail(f"Unsupported deployment mode: {deployment_mode}")

    set_scalar(lines, ("modes", "team", "*"), "enable_swarmflow", "true")
    set_scalar(lines, ("modes", "team", "jiuwen_team"), "enable_swarmflow", "true")
    # The team leader is the only model-facing coordinator. Keep the terminal
    # route contract in the installed persona as well as in AGENT.md/Skills,
    # because a freshly created team workspace may snapshot its persona before
    # it loads the project skill library.
    set_scalar(lines, ("modes", "team", "jiuwen_team", "leader"),
               "persona", json.dumps(AUTOOPS_LEADER_PERSONA, ensure_ascii=False))
    # TUI sessions must start in Team mode; this is the config equivalent of
    # entering `/swarmflow on` before submitting the first request.
    set_scalar(lines, ("channels", "tui"), "default_mode", "team")
    if deployment_mode == "full-access-test":
        set_scalar(lines, ("modes", "team", "jiuwen_team"), "enable_permissions", "false")
        set_scalar(lines, ("permissions",), "enabled", "false")
        set_scalar(lines, ("permissions", "defaults"), "*", "allow")
        set_scalar(lines, ("permissions", "external_directory"), "*", "allow")

    changed = lines != original
    if changed:
        backup = config_file.with_name(config_file.name + ".autoops.bak")
        if not backup.exists():
            shutil.copy2(config_file, backup)
        temporary = config_file.with_name(config_file.name + ".autoops.tmp")
        temporary.write_text("".join(lines), encoding="utf-8")
        os.chmod(temporary, config_file.stat().st_mode & 0o777)
        temporary.replace(config_file)
    return {"path": str(config_file), "changed": changed, "deployment_mode": deployment_mode,
            "permission_policy": "full-access-test" if deployment_mode == "full-access-test" else "preserved"}


def fail(message):
    print(json.dumps({"status": "INPUT_ERROR", "error": message}))
    raise SystemExit(2)


def render_project_paths(text, project_root=None):
    """Render project-owned command paths for the actual installed checkout."""
    root = Path(project_root or ROOT).resolve()
    return text.replace("/root/Jiuwenswarm_AutoOps", str(root))


def validate_skill_sources(project_root=None):
    """Validate every source Skill before changing customer configuration."""
    root = Path(project_root or ROOT).resolve()
    for name in SKILLS:
        source = root / "skills" / name
        if source.is_symlink() or not source.is_dir() or not (source / "SKILL.md").is_file():
            fail(f"Invalid project skill: {name}")
        if (source / "SKILL.md").is_symlink():
            fail(f"Invalid project skill file: {name}/SKILL.md")
    return root


def stage_skill(source, destination, project_root):
    """Build one rendered Skill in a temporary sibling directory."""
    staged = Path(tempfile.mkdtemp(prefix=f".{source.name}.autoops-", dir=destination))
    try:
        shutil.rmtree(staged)
        shutil.copytree(source, staged)
        skill_file = staged / "SKILL.md"
        skill_file.write_text(render_project_paths(skill_file.read_text(encoding="utf-8"), project_root),
                              encoding="utf-8")
        return staged
    except Exception:
        shutil.rmtree(staged, ignore_errors=True)
        raise


def configure_agent_bootstrap(workspace_file):
    """Install the AutoOps routing rule into JiuwenSwarm's global Agent bootstrap."""
    workspace_file = Path(workspace_file).expanduser()
    if workspace_file.is_symlink():
        fail(f"Agent bootstrap must be a regular file: {workspace_file}")
    if not BOOTSTRAP_SOURCE.is_file():
        fail(f"Missing project bootstrap template: {BOOTSTRAP_SOURCE}")
    workspace_file.parent.mkdir(parents=True, exist_ok=True)
    current = workspace_file.read_text(encoding="utf-8") if workspace_file.exists() else ""
    addition = render_project_paths(BOOTSTRAP_SOURCE.read_text(encoding="utf-8")).rstrip() + "\n"
    if BOOTSTRAP_MARKER not in current:
        temporary = workspace_file.with_name(workspace_file.name + ".autoops.tmp")
        temporary.write_text(current.rstrip() + "\n\n" + addition, encoding="utf-8")
        temporary.replace(workspace_file)
        return {"path": str(workspace_file), "changed": True}
    # The project owns the marked AutoOps route block. Refresh only its route
    # sentence so new capabilities become visible after a repeat install while
    # preserving all customer text outside that block.
    source_route = next((line for line in addition.splitlines() if line.startswith("当用户输入涉及")), None)
    source_netops = next((line for line in addition.splitlines() if line.startswith("明确的 NOLI、NetOps")), None)
    source_role_route = next((line for line in addition.splitlines() if line.startswith("不要把普通运维请求")), None)
    source_guard = next((line for line in addition.splitlines() if line.startswith("在 AutoOps 路由中，模型允许")), None)
    source_complex = next((line for line in addition.splitlines() if line.startswith("对于明确要求复杂根因")), None)
    source_terminal = next((line for line in addition.splitlines() if line.startswith("对于未满足上述多角色条件")), None)
    source_followup = next((line for line in addition.splitlines() if line.startswith("对于“继续刚才的任务")), None)
    source_watch = next((line for line in addition.splitlines() if line.startswith("对于包含“值守")), None)
    source_recovery = next((line for line in addition.splitlines() if line.startswith("对于未提供可信授权")), None)
    source_verification = next((line for line in addition.splitlines() if line.startswith("恢复验证也必须")), None)
    source_workflow = next((line for line in addition.splitlines() if line.startswith("对于用户明确要求验证项目已发布的原生 AutoOps 工作流")), None)
    source_backtrace = next((line for line in addition.splitlines() if line.startswith("只涉及一个日志能力")), None)
    lines = current.splitlines(keepends=True)
    changed = False
    if source_netops:
        for index, line in enumerate(lines):
            if line.startswith("明确的 NOLI、NetOps"):
                replacement = source_netops + "\n"
                if line != replacement:
                    lines[index] = replacement
                    changed = True
                break
        else:
            marker_index = next((index for index, line in enumerate(lines)
                                 if line.startswith(BOOTSTRAP_MARKER)), None)
            if marker_index is not None:
                lines.insert(marker_index + 1, source_netops + "\n")
                changed = True
    if source_route:
        for index, line in enumerate(lines):
            if line.startswith("当用户输入涉及"):
                ending = "\n" if line.endswith("\n") else ""
                replacement = source_route + ending
                if line != replacement:
                    lines[index] = replacement
                    changed = True
                break
    if source_role_route:
        role_route_found = False
        for index, line in enumerate(lines):
            if line.startswith("不要把普通运维请求"):
                ending = "\n" if line.endswith("\n") else ""
                replacement = source_role_route + ending
                if line != replacement:
                    lines[index] = replacement
                    changed = True
                role_route_found = True
                break
        if not role_route_found:
            for index, line in enumerate(lines):
                if line.startswith("当用户输入涉及"):
                    lines.insert(index + 1, source_role_route + "\n")
                    changed = True
                    break
    if source_guard:
        guard_found = False
        for index, line in enumerate(lines):
            if line.startswith("在 AutoOps 路由中，模型允许"):
                ending = "\n" if line.endswith("\n") else ""
                replacement = source_guard + ending
                if line != replacement:
                    lines[index] = replacement
                    changed = True
                guard_found = True
                break
        if not guard_found:
            for index, line in enumerate(lines):
                if line.startswith("不要把普通运维请求当作闲聊"):
                    lines.insert(index + 1, source_guard + "\n")
                    changed = True
                    break
    if source_complex:
        complex_found = False
        for index, line in enumerate(lines):
            if line.startswith("对于明确要求复杂根因"):
                ending = "\n" if line.endswith("\n") else ""
                replacement = source_complex + ending
                if line != replacement:
                    lines[index] = replacement
                    changed = True
                complex_found = True
                break
        if not complex_found:
            insert_at = next((index + 1 for index, line in enumerate(lines)
                              if line.startswith("在 AutoOps 路由中，模型允许")), len(lines))
            lines.insert(insert_at, source_complex + "\n")
            changed = True
    if source_terminal:
        terminal_found = False
        for index, line in enumerate(lines):
            if line.startswith(("对于根因、关联或历史溯源请求", "对于未满足上述多角色条件")):
                ending = "\n" if line.endswith("\n") else ""
                replacement = source_terminal + ending
                if line != replacement:
                    lines[index] = replacement
                    changed = True
                terminal_found = True
                break
        if not terminal_found:
            insert_at = next((index for index, line in enumerate(lines)
                              if line.startswith("只有明确的非运维问题")), len(lines))
            lines.insert(insert_at, source_terminal + "\n")
            changed = True
    if source_followup:
        followup_found = False
        for index, line in enumerate(lines):
            if line.startswith("对于“继续刚才的任务"):
                ending = "\n" if line.endswith("\n") else ""
                replacement = source_followup + ending
                if line != replacement:
                    lines[index] = replacement
                    changed = True
                followup_found = True
                break
        if not followup_found:
            lines.append(source_followup + "\n")
            changed = True
    if source_watch:
        watch_found = False
        for index, line in enumerate(lines):
            if line.startswith("对于包含“值守"):
                ending = "\n" if line.endswith("\n") else ""
                replacement = source_watch + ending
                if line != replacement:
                    lines[index] = replacement
                    changed = True
                watch_found = True
                break
        if not watch_found:
            insert_at = next((index for index, line in enumerate(lines)
                              if line.startswith("对于‘继续刚才的任务") or line.startswith("对于“继续刚才的任务")), len(lines))
            lines.insert(insert_at, source_watch + "\n")
            changed = True
    if source_recovery:
        recovery_found = False
        for index, line in enumerate(lines):
            if line.startswith("对于未提供可信授权"):
                ending = "\n" if line.endswith("\n") else ""
                replacement = source_recovery + ending
                if line != replacement:
                    lines[index] = replacement
                    changed = True
                recovery_found = True
                break
        if not recovery_found:
            insert_at = next((index for index, line in enumerate(lines)
                              if line.startswith("恢复任务若上一轮已返回")), len(lines))
            lines.insert(insert_at, source_recovery + "\n")
            changed = True
    if source_verification:
        verification_found = False
        for index, line in enumerate(lines):
            if line.startswith("恢复验证也必须"):
                ending = "\n" if line.endswith("\n") else ""
                replacement = source_verification + ending
                if line != replacement:
                    lines[index] = replacement
                    changed = True
                verification_found = True
                break
        if not verification_found:
            insert_at = next((index for index, line in enumerate(lines)
                              if line.startswith("对于未提供可信授权")), len(lines))
            lines.insert(insert_at, source_verification + "\n")
            changed = True
    if source_workflow:
        workflow_found = False
        for index, line in enumerate(lines):
            if line.startswith("对于用户明确要求验证项目已发布的原生 AutoOps 工作流"):
                ending = "\n" if line.endswith("\n") else ""
                replacement = source_workflow + ending
                if line != replacement:
                    lines[index] = replacement
                    changed = True
                workflow_found = True
                break
        if not workflow_found:
            insert_at = next((index + 1 for index, line in enumerate(lines)
                              if line.startswith("对于 E01/E02 写操作")), len(lines))
            lines.insert(insert_at, source_workflow + "\n")
            changed = True
    if source_backtrace:
        backtrace_found = False
        for index, line in enumerate(lines):
            if line.startswith(("带“有问题再往前查", "只涉及一个日志能力")):
                ending = "\n" if line.endswith("\n") else ""
                replacement = source_backtrace + ending
                if line != replacement:
                    lines[index] = replacement
                    changed = True
                backtrace_found = True
                break
        if not backtrace_found:
            insert_at = next((index for index, line in enumerate(lines)
                              if line.startswith("只有明确的非运维问题")), len(lines))
            lines.insert(insert_at, source_backtrace + "\n")
            changed = True
    if changed:
        temporary = workspace_file.with_name(workspace_file.name + ".autoops.tmp")
        temporary.write_text("".join(lines), encoding="utf-8")
        temporary.replace(workspace_file)
        return {"path": str(workspace_file), "changed": True}
    return {"path": str(workspace_file), "changed": False}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--skills-dir", default=os.environ.get("JIUWENSWARM_AGENT_SKILLS_DIR", str(Path.home() / ".jiuwenswarm/agent/workspace/skills")))
    parser.add_argument("--config-file", default=os.environ.get("JIUWENSWARM_CONFIG_FILE", str(Path.home() / ".jiuwenswarm/config/config.yaml")))
    parser.add_argument("--deployment-mode", choices=sorted(DEPLOYMENT_MODES),
                        default=os.environ.get("AUTOOPS_DEPLOYMENT_MODE", "preserve-existing"))
    parser.add_argument("--skip-runtime-config", action="store_true")
    parser.add_argument("--skip-agent-bootstrap", action="store_true")
    args = parser.parse_args(argv)
    project_root = validate_skill_sources()
    runtime = None if args.skip_runtime_config else configure_runtime(args.config_file, args.deployment_mode)
    bootstrap = None if args.skip_agent_bootstrap else configure_agent_bootstrap(
        os.environ.get("JIUWENSWARM_AGENT_BOOTSTRAP", str(Path.home() / ".jiuwenswarm/agent/workspace/AGENT.md"))
    )
    destination = Path(args.skills_dir).expanduser()
    if destination.is_symlink():
        fail("Skill library directory must not be a symlink.")
    destination.mkdir(parents=True, exist_ok=True)
    installed = []
    staged_entries = []
    backups = {}
    published = []
    manifest = destination / "autoops-install-manifest.json"
    manifest_original = None
    manifest_mode = None
    try:
        # Check every destination before the first replacement. This prevents a
        # late symlink or file conflict from producing a partial Skill refresh.
        for name in SKILLS:
            target = destination / name
            if target.is_symlink():
                fail(f"Refusing to replace symlinked skill: {target}")
            if target.exists() and not target.is_dir():
                fail(f"Refusing to replace non-directory skill: {target}")
        for name in SKILLS:
            source = project_root / "skills" / name
            staged_entries.append((name, destination / name, stage_skill(source, destination, project_root)))

        for name, target, staged in staged_entries:
            if target.exists():
                backup = Path(tempfile.mkdtemp(prefix=f".{name}.autoops-backup-", dir=destination))
                backup.rmdir()
                target.rename(backup)
                backups[target] = backup
            staged.rename(target)
            published.append(target)
            installed.append(name)

        if manifest.is_symlink():
            fail(f"Refusing to replace symlinked manifest: {manifest}")
        if manifest.exists():
            manifest_original = manifest.read_bytes()
            manifest_mode = manifest.stat().st_mode & 0o777
        temporary = manifest.with_name(manifest.name + ".autoops.tmp")
        temporary.write_text(json.dumps({"source": str(project_root), "skills": installed}, indent=2) + "\n",
                               encoding="utf-8")
        os.replace(temporary, manifest)
        os.chmod(manifest, 0o600)
    except Exception:
        # Restore every previous Skill in reverse publish order and remove all
        # staged/new content. The customer directory remains usable after an
        # interrupted upgrade.
        for target in reversed(published):
            if target.exists() or target.is_symlink():
                shutil.rmtree(target, ignore_errors=True)
                if target.is_symlink():
                    target.unlink()
        for target, backup in backups.items():
            if backup.exists() and not target.exists():
                backup.rename(target)
        for _, _, staged in staged_entries:
            shutil.rmtree(staged, ignore_errors=True)
        for backup in backups.values():
            shutil.rmtree(backup, ignore_errors=True)
        temporary = manifest.with_name(manifest.name + ".autoops.tmp")
        if temporary.exists():
            temporary.unlink()
        if manifest_original is None:
            if manifest.exists() and not manifest.is_dir():
                manifest.unlink()
        else:
            manifest.write_bytes(manifest_original)
            if manifest_mode is not None:
                os.chmod(manifest, manifest_mode)
        raise
    else:
        for backup in backups.values():
            shutil.rmtree(backup, ignore_errors=True)
        for _, _, staged in staged_entries:
            shutil.rmtree(staged, ignore_errors=True)
    print(json.dumps({"status": "READY", "skills_dir": str(destination), "installed": installed, "runtime": runtime, "bootstrap": bootstrap}))


if __name__ == "__main__":
    main()
