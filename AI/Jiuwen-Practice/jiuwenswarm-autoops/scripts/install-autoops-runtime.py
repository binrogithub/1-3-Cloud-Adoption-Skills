#!/usr/bin/env python3
"""Materialize the project-owned AutoOps runtime for a new host.

This installer publishes glue configuration and lifecycle units.  It does not
install or modify JiuwenSwarm, the upstream TUI, observability servers, or
execution engines. Project-owned runtime assets are refreshed on every run;
customer-owned configuration outside the runtime is preserved.
"""
from __future__ import annotations

import argparse
import grp
import hashlib
import json
import os
import pwd
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from autoops_datasource_health import probe as probe_datasource


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ASSET_FILES = (
    "components.env",
    "config/compensation-registry.json",
    "config/jiuwenswarm.maas.env.example",
    "config/loki.env.example",
    "config/maas.env.example",
    "config/model.env.example",
    "config/opensearch.env.example",
    "config/noli.env.example",
    "config/prometheus.env.example",
    "config/rundeck-e2e.env.example",
    "config/rundeck.env.example",
    "config/autoops-agent-bootstrap.md",
    "config/css.env.example",
    "config/css/business.example.json",
    "config/css/business.schema.json",
    "config/css/pressure-24h.example.json",
    "config/css/pressure-2-to-10-wave.example.json",
    "config/css/requirements.txt",
    "config/rundeck-jobs.json",
    "scripts/autoops-runtime-backup.py",
    "scripts/css-live-pressure.py",
    "scripts/css-24h-pressure.py",
    "scripts/css_run_state.py",
    "scripts/css_action_ledger.py",
    "scripts/css-scale-runbook.py",
    "scripts/css-reconcile.py",
    "scripts/css_reconcile.py",
    "scripts/css_config.py",
    "scripts/css_cloud.py",
    "scripts/css_capability.py",
    "scripts/css_policy.py",
    "scripts/css_metrics.py",
    "scripts/css_business_verification.py",
    "scripts/css_capacity_forecast.py",
    "scripts/css_migrate.py",
    "scripts/css_collector.py",
    "scripts/css_history.py",
    "scripts/css_stability_soak.py",
    "scripts/css_collection_efficiency.py",
    "scripts/css_tui_role_chain_check.py",
    "scripts/css_install_self_check.py",
    "scripts/css_stability_release_gate.py",
    "scripts/koo_cli.py",
    "scripts/netops-noli.py",
    "config/systemd/jiuwenswarm-autoops-alert-dispatch.service",
    "config/systemd/jiuwenswarm-autoops-alert-dispatch.timer",
    "config/systemd/jiuwenswarm-autoops-alertmanager.service",
    "config/systemd/jiuwenswarm-autoops-watch.service",
    "config/systemd/jiuwenswarm-autoops-watch.timer",
    "config/systemd/jiuwenswarm-autoops-css-watch.service",
    "config/systemd/jiuwenswarm-autoops-css-watch.timer",
    "config/authorization/preauthorization.example.json",
    "config/authorization/service-policy.json",
    "runbooks/ansible/host-inspect.yml",
    "runbooks/ansible/host-ensure-service.yml",
    "config/acceptance/route-cases-v1.json",
    "config/acceptance/css-stability-v1.json",
    "docs/css-stability-50-scenarios-spec.md",
    "docs/css-tui-role-chain-validation.md",
    "docs/css-stability-real-validation-report.md",
    "docs/css-upgrade-and-recovery.md",
    "docs/css-stability-test-issues.md",
)
CONFIG_FILES = (
    "capability-registry.json",
    "workflow-registry.json",
    "ro00-compatibility-matrix.json",
    "autoops-input-policy.json",
    "observability-policy.json",
    "project-manager-actions.json",
    "service-verification.json",
)
CONFIG_DIRS = ("alloy", "css", "kubernetes", "monitoring", "roles", "rundeck", "service-profiles")
SYSTEMD_FILES = (
    "jiuwenswarm-autoops-alert-dispatch.service",
    "jiuwenswarm-autoops-alert-dispatch.timer",
    "jiuwenswarm-autoops-alertmanager.service",
    "jiuwenswarm-autoops-watch.service",
    "jiuwenswarm-autoops-watch.timer",
    "jiuwenswarm-autoops-css-watch.service",
    "jiuwenswarm-autoops-css-watch.timer",
)
RUNTIME_DOC_FILES = (
    "docs/css-stability-50-scenarios-spec.md",
    "docs/css-tui-role-chain-validation.md",
    "docs/css-stability-real-validation-report.md",
    "docs/css-upgrade-and-recovery.md",
    "docs/css-stability-test-issues.md",
)
SWARMFLOW_FILES = (
    "service-recovery-v1.py",
    "ro00-readonly-validation.py",
    "ro05-parallel-observability-v1.py",
    "e03-kubernetes-validation-v1.py",
    "css-autoscale-v1.py",
)
MANAGED_MARKER = "# Managed by JiuwenSwarm AutoOps installer"
DEFAULT_SYSTEMD_ROOT = Path("/etc/systemd/system")
LOCAL_OBSERVABILITY = (
    ("loki", "loki.env", "LOKI", "/ready", "ready"),
    ("prometheus", "prometheus.env", "PROMETHEUS", "/-/ready", None),
    ("opensearch", "opensearch.env", "OPENSEARCH", "/", None),
)


def validate_account_name(value: str, field: str) -> None:
    if not value or len(value) > 32 or not value.replace("-", "a").replace("_", "a").isalnum() \
            or not value[0].isalpha():
        raise ValueError(f"{field} must be a local system account name")


def is_service_accessible(path: Path) -> bool:
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        return False
    return Path("/root") not in (resolved, *resolved.parents)


def service_python(explicit: Path | None) -> Path:
    candidates = [explicit] if explicit else [
        Path("/usr/bin/python3"), Path("/usr/bin/python3.12"), Path("/usr/bin/python3.11"),
        Path("/usr/bin/python3.10"), Path("/usr/bin/python3.9"),
    ]
    for candidate in candidates:
        if candidate is None or not candidate.is_file() or not os.access(candidate, os.X_OK):
            continue
        if not is_service_accessible(candidate):
            continue
        check = subprocess.run([
            str(candidate), "-c", "import sys; raise SystemExit(sys.version_info < (3, 9))",
        ], check=False, capture_output=True, text=True)
        if check.returncode == 0:
            return candidate.resolve()
    if explicit:
        raise ValueError(f"python executable is unavailable, below Python 3.9, or inaccessible to services: {explicit}")
    raise ValueError("no service-accessible Python 3.9+ interpreter was found; pass --python-executable")


def component_values(source_root: Path) -> dict[str, str]:
    """Read endpoint values without evaluating the shell env file."""
    path = source_root / "components.env"
    values: dict[str, str] = {}
    if not path.is_file() or path.is_symlink():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.endswith("_HTTP_HOST") or key.endswith("_HTTP_PORT"):
            values[key] = value.strip().strip('"').strip("'")
    return values


def local_endpoint(prefix: str, values: dict[str, str]) -> str | None:
    override = os.environ.get(f"AUTOOPS_LOCAL_{prefix}_URL", "").strip()
    if override:
        return override.rstrip("/")
    host = values.get(f"{prefix}_HTTP_HOST", "")
    port = values.get(f"{prefix}_HTTP_PORT", "")
    if not host or not port.isdigit() or not 1 <= int(port) <= 65535:
        return None
    return f"http://{host}:{port}"


def endpoint_ready(base_url: str, path: str, expected_body: str | None) -> bool:
    parsed = urllib.parse.urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
        return False
    request = urllib.request.Request(f"{base_url.rstrip('/')}{path}", method="GET")
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=3) as response:
            body = response.read(128).decode("utf-8", errors="replace").strip()
            return 200 <= response.status < 300 and (expected_body is None or body == expected_body)
    except (OSError, urllib.error.URLError, ValueError):
        return False


def local_env_content(name: str, base_url: str) -> str:
    header = "# Managed by JiuwenSwarm AutoOps local datasource discovery.\n"
    if name == "loki":
        return header + (
            f'LOKI_BASE_URL="{base_url}"\nLOKI_TENANT_ID=""\nLOKI_BEARER_TOKEN=""\n'
            'LOKI_SERVICE_LABEL="service"\nLOKI_TIMEOUT_SECONDS="15"\n'
            'AUTOOPS_OBSERVABILITY_MAX_WINDOW_MINUTES="1440"\nAUTOOPS_LOCAL_JOURNAL_FALLBACK="1"\n'
        )
    if name == "prometheus":
        return header + (
            f'PROMETHEUS_BASE_URL="{base_url}"\nPROMETHEUS_BEARER_TOKEN=""\n'
            'PROMETHEUS_TIMEOUT_SECONDS="10"\nPROMETHEUS_VERIFY_TLS="1"\n'
        )
    return header + (
        f'OPENSEARCH_BASE_URL="{base_url}"\nOPENSEARCH_API_KEY=""\n'
        'OPENSEARCH_BEARER_TOKEN=""\nOPENSEARCH_USERNAME=""\nOPENSEARCH_PASSWORD=""\n'
        'OPENSEARCH_TIMEOUT_SECONDS="10"\nOPENSEARCH_VERIFY_TLS="1"\n'
    )


def configure_local_observability(source_root: Path, config_root: Path,
                                  transaction: "InstallTransaction") -> list[str]:
    """Publish only absent local endpoint settings after health checks."""
    values = component_values(source_root)
    status = []
    for name, filename, prefix, path, expected_body in LOCAL_OBSERVABILITY:
        destination = config_root / filename
        if destination.exists():
            regular(destination)
            status.append(f"{name}:preserved")
            continue
        base_url = local_endpoint(prefix, values)
        if not base_url:
            status.append(f"{name}:unavailable")
            continue
        health = probe_datasource(name, {f"{prefix}_BASE_URL": base_url}, timeout=3)
        if health.get("capability_ready") is not True:
            status.append(f"{name}:unavailable")
            continue
        atomic_write(destination, local_env_content(name, base_url), 0o640, transaction)
        status.append(f"{name}:configured")
    return status


def ensure_service_account(user: str, group: str, state_root: Path) -> tuple[int, int]:
    """Create the dedicated local account used by managed systemd units."""
    validate_account_name(user, "service user")
    validate_account_name(group, "service group")
    try:
        group_record = grp.getgrnam(group)
    except KeyError:
        groupadd = shutil.which("groupadd")
        if not groupadd:
            raise ValueError(f"service group {group!r} is missing and groupadd is unavailable")
        subprocess.run([groupadd, "--system", group], check=True, capture_output=True, text=True)
        group_record = grp.getgrnam(group)
    try:
        user_record = pwd.getpwnam(user)
    except KeyError:
        useradd = shutil.which("useradd")
        if not useradd:
            raise ValueError(f"service user {user!r} is missing and useradd is unavailable")
        subprocess.run([
            useradd, "--system", "--no-create-home", "--home-dir", str(state_root),
            "--shell", "/sbin/nologin", "--gid", group, user,
        ], check=True, capture_output=True, text=True)
        user_record = pwd.getpwnam(user)
    if user_record.pw_gid != group_record.gr_gid:
        raise ValueError(f"service user {user!r} does not use requested group {group!r}")
    ensure_journal_access(user, user_record.pw_gid)
    return user_record.pw_uid, group_record.gr_gid


def ensure_journal_access(user: str, primary_gid: int) -> None:
    """Allow the default service identity to read local systemd journal logs."""
    if user == "root":
        return
    try:
        journal_group = grp.getgrnam("systemd-journal")
    except KeyError as exc:
        raise ValueError("systemd-journal group is required for local log investigations") from exc
    if journal_group.gr_gid in os.getgrouplist(user, primary_gid):
        return
    usermod = shutil.which("usermod")
    if not usermod:
        raise ValueError("usermod is required to grant systemd-journal access to the AutoOps service account")
    subprocess.run([usermod, "--append", "--groups", "systemd-journal", user],
                   check=True, capture_output=True, text=True)


def set_state_owner(state_root: Path, uid: int, gid: int) -> None:
    """Give the service account only the state paths owned by AutoOps.

    The shared state root may also host a local k3s data directory. Do not walk
    that tree or alter container filesystem ownership while installing AutoOps.
    """
    paths = [state_root]
    for name in ("watch",):
        path = state_root / name
        if not path.exists():
            continue
        if path.is_symlink() or not path.is_dir():
            raise ValueError(f"invalid AutoOps state directory: {path}")
        for root, directories, files in os.walk(path, followlinks=False):
            root_path = Path(root)
            if root_path.is_symlink():
                raise ValueError(f"refusing symlink in AutoOps state: {root_path}")
            paths.append(root_path)
            for child in [*directories, *files]:
                child_path = root_path / child
                if child_path.is_symlink():
                    raise ValueError(f"refusing symlink in AutoOps state: {child_path}")
                paths.append(child_path)
    for name in ("events.jsonl", "autoops-state.db", "notifications.jsonl"):
        path = state_root / name
        if not path.exists():
            continue
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"invalid AutoOps state file: {path}")
        paths.append(path)
    for path in paths:
        os.chown(path, uid, gid)


def set_config_access(config_root: Path, gid: int) -> None:
    """Grant the service group access only to declared external settings.

    Configuration stays owned by the installing administrator. The service
    group receives traverse access to the configuration directories and read
    access to the known env and authorization files it must consume. Unknown
    customer files are deliberately left untouched.
    """
    regular(config_root, directory=True)
    os.chown(config_root, -1, gid)
    os.chmod(config_root, 0o710)
    authorization = config_root / "authorization"
    if authorization.exists():
        regular(authorization, directory=True)
        os.chown(authorization, -1, gid)
        os.chmod(authorization, 0o710)
    # Published customer profiles, policies and job bindings are read by the
    # dedicated service group. Restrict traversal to project-declared trees;
    # unknown customer files remain untouched.
    for directory_name in ("alloy", "css", "kubernetes", "monitoring", "roles", "rundeck", "service-profiles"):
        directory = config_root / directory_name
        if not directory.exists():
            continue
        regular(directory, directory=True)
        for current, directories, files in os.walk(directory, followlinks=False):
            current_path = Path(current)
            os.chown(current_path, -1, gid)
            os.chmod(current_path, 0o750)
            for name in directories + files:
                child = current_path / name
                if child.is_symlink():
                    raise ValueError(f"refusing symlink in customer configuration: {child}")
                if child.is_dir():
                    os.chown(child, -1, gid)
                    os.chmod(child, 0o750)
                elif child.is_file():
                    os.chown(child, -1, gid)
                    os.chmod(child, 0o640)
    managed_files = (
        "runtime.json",
        "maas.env", "maas.env.example", "loki.env", "loki.env.example",
        "opensearch.env", "opensearch.env.example", "prometheus.env", "prometheus.env.example",
        "authorization/preauthorization.json", "authorization/preauthorization.example.json",
    )
    for relative in managed_files:
        path = config_root / relative
        if not path.exists():
            continue
        regular(path)
        os.chown(path, -1, gid)
        os.chmod(path, 0o640)


class InstallTransaction:
    """Track files and directories changed by one install attempt.

    Asset validation happens before publishing, while this transaction protects
    against destination-side failures that can only be found during publish
    (for example a customer-created symlink or a conflicting directory).
    """

    def __init__(self) -> None:
        self._files: list[tuple[Path, bool, bytes | None, int | None]] = []
        self._file_paths: set[Path] = set()
        self._directories: list[Path] = []

    def track_directory(self, path: Path) -> None:
        if path not in self._directories:
            self._directories.append(path)

    def snapshot_file(self, path: Path) -> None:
        if path in self._file_paths:
            return
        if path.is_symlink():
            raise ValueError(f"refusing symlink path: {path}")
        if path.exists():
            regular(path)
            stat = path.stat()
            self._files.append((path, True, path.read_bytes(), stat.st_mode & 0o777))
        else:
            self._files.append((path, False, None, None))
        self._file_paths.add(path)

    def rollback(self) -> None:
        for path, existed, content, mode in reversed(self._files):
            if existed:
                if path.is_symlink():
                    path.unlink()
                path.write_bytes(content or b"")
                if mode is not None:
                    os.chmod(path, mode)
            elif path.exists() or path.is_symlink():
                if path.is_dir() and not path.is_symlink():
                    shutil.rmtree(path)
                else:
                    path.unlink()
        for path in reversed(self._directories):
            try:
                path.rmdir()
            except (FileNotFoundError, OSError):
                pass


def regular(path: Path, *, directory: bool = False) -> None:
    if path.is_symlink():
        raise ValueError(f"refusing symlink path: {path}")
    if path.exists() and ((directory and not path.is_dir()) or (not directory and not path.is_file())):
        raise ValueError(f"unexpected path type: {path}")


def ensure_dir(path: Path, mode: int, transaction: InstallTransaction | None = None) -> None:
    regular(path, directory=True)
    missing: list[Path] = []
    cursor = path
    while not cursor.exists():
        missing.append(cursor)
        cursor = cursor.parent
    path.mkdir(parents=True, exist_ok=True)
    if transaction:
        for created in reversed(missing):
            transaction.track_directory(created)
    os.chmod(path, mode)


def atomic_write(path: Path, content: str, mode: int,
                 transaction: InstallTransaction | None = None) -> None:
    regular(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if transaction:
        transaction.snapshot_file(path)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def copy_if_absent(source: Path, destination: Path, *, mode: int = 0o640, parent_mode: int = 0o750,
                   transaction: InstallTransaction | None = None) -> str:
    regular(source)
    if destination.is_symlink():
        raise ValueError(f"refusing symlink destination: {destination}")
    ensure_dir(destination.parent, parent_mode, transaction)
    if destination.exists():
        regular(destination)
        os.chmod(destination, mode)
        return "preserved"
    if transaction:
        transaction.snapshot_file(destination)
    shutil.copy2(source, destination)
    os.chmod(destination, mode)
    return "installed"


def configure_css_runtime_env(config_root: Path, transaction: InstallTransaction,
                              result: dict[str, list[str]]) -> dict[str, object]:
    """Bind the CSS watcher to one unambiguous customer profile.

    A profile ID is configuration, not a secret. Auto-selecting is safe only
    when the customer config contains exactly one regular cluster profile;
    multiple profiles require an explicit css.env so installation cannot pick
    the wrong production resource.
    """
    env_path = config_root / "css.env"
    if env_path.is_symlink():
        raise ValueError(f"refusing symlink CSS environment: {env_path}")
    if env_path.exists():
        regular(env_path)
        os.chmod(env_path, 0o640)
        return {"status": "PRESERVED", "path": str(env_path)}
    clusters = config_root / "css" / "clusters"
    profiles = []
    if clusters.is_dir() and not clusters.is_symlink():
        for path in sorted(clusters.glob("*.json")):
            if path.is_symlink() or not path.is_file():
                continue
            value = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(value, dict) and value.get("profile_id"):
                profiles.append(str(value["profile_id"]))
    if len(profiles) != 1:
        return {"status": "NOT_CONFIGURED", "path": str(env_path),
                "profile_candidates": profiles}
    atomic_write(env_path, f"AUTOOPS_CSS_PROFILE_ID={profiles[0]}\n", 0o640, transaction)
    result["installed"].append(str(env_path))
    return {"status": "CONFIGURED", "path": str(env_path), "profile_id": profiles[0]}


def copy_managed(source: Path, destination: Path, *, mode: int = 0o640, parent_mode: int = 0o750,
                 transaction: InstallTransaction | None = None) -> str:
    """Refresh one project-owned asset while retaining rollback protection."""
    regular(source)
    if destination.is_symlink():
        raise ValueError(f"refusing symlink destination: {destination}")
    ensure_dir(destination.parent, parent_mode, transaction)
    if destination.exists():
        regular(destination)
        if destination.read_bytes() == source.read_bytes():
            os.chmod(destination, mode)
            return "preserved"
        if transaction:
            transaction.snapshot_file(destination)
        shutil.copy2(source, destination)
        os.chmod(destination, mode)
        return "updated"
    if transaction:
        transaction.snapshot_file(destination)
    shutil.copy2(source, destination)
    os.chmod(destination, mode)
    return "installed"


def publish_tree(source: Path, destination: Path, result: dict[str, list[str]],
                 transaction: InstallTransaction | None = None, *, mode: int = 0o640,
                 directory_mode: int = 0o750, refresh: bool = False) -> None:
    regular(source, directory=True)
    ensure_dir(destination, directory_mode, transaction)
    for source_file in sorted(source.rglob("*")):
        if "__pycache__" in source_file.parts or source_file.suffix == ".pyc":
            continue
        relative = source_file.relative_to(source)
        destination_file = destination / relative
        if source_file.is_symlink():
            raise ValueError(f"source tree contains symlink: {source_file}")
        if source_file.is_dir():
            ensure_dir(destination_file, directory_mode, transaction)
            continue
        if not source_file.is_file():
            raise ValueError(f"unsupported source entry: {source_file}")
        copier = copy_managed if refresh else copy_if_absent
        result[copier(source_file, destination_file, mode=mode, parent_mode=directory_mode,
                      transaction=transaction)].append(str(destination_file))


def migrate_customer_changes(source: Path, installed: Path, customer: Path,
                             transaction: InstallTransaction) -> list[str]:
    """Preserve changed legacy runtime defaults before a managed refresh."""
    migrated: list[str] = []
    if not installed.is_dir():
        return migrated
    for source_file in sorted(source.rglob("*")):
        if not source_file.is_file() or source_file.is_symlink():
            continue
        relative = source_file.relative_to(source)
        old_file = installed / relative
        new_file = customer / relative
        if not old_file.is_file() or old_file.is_symlink() or new_file.exists():
            continue
        if old_file.read_bytes() == source_file.read_bytes():
            continue
        ensure_dir(new_file.parent, 0o750, transaction)
        if transaction:
            transaction.snapshot_file(new_file)
        shutil.copy2(old_file, new_file)
        os.chmod(new_file, 0o640)
        migrated.append(str(new_file))
    return migrated


def read_json_asset(path: Path, *, require_schema: bool = True) -> dict[str, object]:
    regular(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON asset: {path}: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON asset must be an object: {path}")
    if require_schema and value.get("schema_version") != 1:
        raise ValueError(f"JSON asset must have schema_version 1: {path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_file_records(roots: tuple[tuple[str, Path], ...], manifest: Path) -> list[dict[str, object]]:
    """Describe managed files without copying customer configuration values."""
    records: list[dict[str, object]] = []
    for root_name, root in roots:
        if not root.exists():
            continue
        if root.is_symlink():
            raise ValueError(f"refusing symlink manifest root: {root}")
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.is_symlink() or path == manifest:
                continue
            stat = path.stat()
            records.append({
                "root": root_name,
                "path": str(path),
                "relative_path": str(path.relative_to(root)),
                "sha256": sha256_file(path),
                "mode": format(stat.st_mode & 0o7777, "04o"),
                "ownership": {"uid": stat.st_uid, "gid": stat.st_gid},
            })
    return records


def validate_assets(source_root: Path) -> None:
    """Reject semantically invalid project defaults before publishing anything."""
    for relative in CONFIG_FILES:
        read_json_asset(source_root / "config" / relative,
                        require_schema=relative != "project-manager-actions.json")
    input_policy = read_json_asset(source_root / "config" / "autoops-input-policy.json")
    if input_policy.get("default_scope") != "host_system" or not isinstance(input_policy.get("default_target"), str):
        raise ValueError("autoops-input-policy.json must publish a host-system default target")
    if not isinstance(input_policy.get("default_window_minutes"), int) or not 1 <= input_policy["default_window_minutes"] <= 10080:
        raise ValueError("autoops-input-policy.json default_window_minutes is invalid")
    for relative in ("monitoring/autoops-demo-watch.json",):
        policy = read_json_asset(source_root / "config" / relative, require_schema=False)
        if policy.get("apiVersion") != "autoops.jiuwen/v1":
            raise ValueError(f"invalid MonitoringPolicy apiVersion: {source_root / 'config' / relative}")
        if policy.get("kind") != "MonitoringPolicy" or not isinstance(policy.get("spec"), dict):
            raise ValueError(f"invalid MonitoringPolicy asset: {source_root / 'config' / relative}")
    profile_dir = source_root / "config" / "service-profiles"
    for path in sorted(profile_dir.glob("*.json")):
        profile = read_json_asset(path)
        if not isinstance(profile.get("profile_id"), str) or not profile["profile_id"]:
            raise ValueError(f"ServiceProfile profile_id is required: {path}")
        if not isinstance(profile.get("services"), list) or not profile["services"]:
            raise ValueError(f"ServiceProfile services are required: {path}")
    verification = read_json_asset(source_root / "config" / "service-verification.json")
    if not isinstance(verification.get("services"), dict) or not verification["services"]:
        raise ValueError("service-verification.json must publish at least one service")
    kubernetes = read_json_asset(source_root / "config" / "kubernetes" / "workloads.json")
    clusters = kubernetes.get("clusters")
    if not isinstance(clusters, dict) or not clusters:
        raise ValueError("workloads.json must publish at least one Kubernetes cluster")
    for cluster_name, cluster in clusters.items():
        if not isinstance(cluster_name, str) or not isinstance(cluster, dict):
            raise ValueError("workloads.json cluster entries are invalid")
        if not isinstance(cluster.get("enabled"), bool):
            raise ValueError(f"workloads.json enabled is required: {cluster_name}")
        if not isinstance(cluster.get("context"), str) or not cluster["context"]:
            raise ValueError(f"workloads.json context is required: {cluster_name}")
        if not isinstance(cluster.get("kubeconfig_env"), str) or not cluster["kubeconfig_env"]:
            raise ValueError(f"workloads.json kubeconfig_env is required: {cluster_name}")
        workloads = cluster.get("workloads")
        if not isinstance(workloads, dict) or not workloads:
            raise ValueError(f"workloads.json must publish workloads: {cluster_name}")
        for workload_id, workload in workloads.items():
            if not isinstance(workload_id, str) or not isinstance(workload, dict):
                raise ValueError(f"workloads.json workload entry is invalid: {cluster_name}")
            required = ("namespace", "kind", "name", "selector", "baseline_replicas", "service", "restore_job")
            if any(not isinstance(workload.get(field), str) or not workload[field]
                   for field in required if field != "baseline_replicas"):
                raise ValueError(f"workloads.json workload fields are invalid: {cluster_name}/{workload_id}")
            if workload.get("kind") != "Deployment" or not isinstance(workload.get("baseline_replicas"), int) \
                    or workload["baseline_replicas"] < 1:
                raise ValueError(f"workloads.json workload baseline is invalid: {cluster_name}/{workload_id}")
            business_verification = workload.get("business_verification")
            if business_verification is not None:
                if not isinstance(business_verification, dict) \
                        or not isinstance(business_verification.get("health_url"), str) \
                        or not business_verification["health_url"].strip():
                    raise ValueError(f"workloads.json business_verification is invalid: {cluster_name}/{workload_id}")
                attempts = business_verification.get("probe_attempts", 7)
                interval = business_verification.get("probe_interval_seconds", 10)
                if not isinstance(attempts, int) or not 1 <= attempts <= 60 \
                        or not isinstance(interval, int) or not 0 <= interval <= 3600:
                    raise ValueError(f"workloads.json business verification window is invalid: {cluster_name}/{workload_id}")
    preauthorization = read_json_asset(source_root / "config" / "authorization" / "preauthorization.example.json")
    if preauthorization.get("status") != "DISABLED":
        raise ValueError("preauthorization.example.json must be disabled by default")
    for relative in RUNTIME_ASSET_FILES:
        regular(source_root / relative)


def render_unit(source: Path, *, install_root: Path, config_root: Path, state_root: Path,
                service_user: str, service_group: str, python_executable: Path) -> str:
    regular(source)
    text = source.read_text(encoding="utf-8")
    replacements = {
        "/opt/Jiuwenswarm_AutoOps": str(install_root),
        "/etc/jiuwenswarm-autoops": str(config_root),
        "/var/lib/jiuwenswarm-autoops": str(state_root),
        "User=jiuwenswarm-autoops": f"User={service_user}",
        "Group=jiuwenswarm-autoops": f"Group={service_group}",
        "/usr/bin/python3": str(python_executable),
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return f"{MANAGED_MARKER}\n{text}"


def install(args: argparse.Namespace) -> dict[str, object]:
    source_root = args.source_root.resolve()
    install_root = args.install_root.resolve()
    state_root = args.state_root.resolve()
    config_root = args.config_root.resolve()
    systemd_root = args.systemd_root.resolve()
    python_executable = service_python(args.python_executable)
    for required in (source_root / "config", source_root / "scripts", source_root / "skills"):
        regular(required, directory=True)
    validate_assets(source_root)

    result: dict[str, list[str]] = {"installed": [], "updated": [], "preserved": []}
    transaction = InstallTransaction()
    try:
        managed_host_install = (
            args.create_service_account
            and systemd_root == DEFAULT_SYSTEMD_ROOT
            and os.geteuid() == 0
            and args.service_user != "root"
        )
        service_identity: tuple[int, int] | None = None
        if managed_host_install:
            service_identity = ensure_service_account(args.service_user, args.service_group, state_root)
        ensure_dir(config_root, 0o750, transaction)
        result.setdefault("migrated", [])
        for relative in CONFIG_DIRS:
            result["migrated"].extend(migrate_customer_changes(
                source_root / "config" / relative,
                install_root / "config" / relative,
                config_root / relative,
                transaction,
            ))
        ensure_dir(install_root, 0o755, transaction)
        publish_tree(source_root / "scripts", install_root / "scripts", result, transaction,
                     mode=0o755, directory_mode=0o755, refresh=True)
        publish_tree(source_root / "skills", install_root / "skills", result, transaction,
                     mode=0o644, directory_mode=0o755, refresh=True)
        publish_tree(source_root / "runbooks", install_root / "runbooks", result, transaction,
                     mode=0o644, directory_mode=0o755, refresh=True)
        for relative in ("components.env", "config/compensation-registry.json",
                         "config/jiuwenswarm.maas.env.example", "config/loki.env.example",
                         "config/maas.env.example", "config/model.env.example", "config/noli.env.example",
                         "config/opensearch.env.example",
                         "config/prometheus.env.example", "config/rundeck-e2e.env.example",
                         "config/rundeck.env.example", "config/autoops-agent-bootstrap.md",
                         "config/css.env.example", "config/rundeck-jobs.json"):
            status = copy_managed(source_root / relative, install_root / relative,
                                  mode=0o640, parent_mode=0o755, transaction=transaction)
            result[status].append(str(install_root / relative))
        publish_tree(source_root / "config" / "systemd", install_root / "config" / "systemd",
                     result, transaction, mode=0o644, directory_mode=0o755, refresh=True)
        publish_tree(source_root / "config" / "authorization", install_root / "config" / "authorization",
                     result, transaction, mode=0o640, directory_mode=0o750, refresh=True)
        publish_tree(source_root / "config" / "release", install_root / "config" / "release",
                     result, transaction, mode=0o640, directory_mode=0o750, refresh=True)
        publish_tree(source_root / "config" / "acceptance", install_root / "config" / "acceptance",
                     result, transaction, mode=0o640, directory_mode=0o750, refresh=True)
        for relative in RUNTIME_DOC_FILES:
            status = copy_managed(source_root / relative, install_root / relative,
                                  mode=0o640, parent_mode=0o755, transaction=transaction)
            result[status].append(str(install_root / relative))
        for relative in CONFIG_FILES:
            status = copy_managed(source_root / "config" / relative,
                                  install_root / "config" / relative,
                                  mode=0o644, parent_mode=0o755,
                                  transaction=transaction)
            result[status].append(str(install_root / "config" / relative))
        for relative in CONFIG_DIRS:
            publish_tree(source_root / "config" / relative,
                         install_root / "config" / relative, result, transaction,
                         mode=0o644, directory_mode=0o755, refresh=True)
        for relative in SWARMFLOW_FILES:
            status = copy_managed(source_root / "swarmflow" / relative,
                                  install_root / "swarmflow" / relative,
                                  transaction=transaction)
            result[status].append(str(install_root / "swarmflow" / relative))

        # Keep the customer-owned configuration outside the project checkout and
        # publish only examples. Real MaaS, NOLI, Loki, OpenSearch and Rundeck values
        # remain environment-provided and are never generated by this installer.
        for relative in CONFIG_DIRS:
            publish_tree(source_root / "config" / relative,
                         config_root / relative, result, transaction,
                         mode=0o640, directory_mode=0o750, refresh=False)
        for relative in ("authorization/preauthorization.example.json",
                         "noli.env.example", "loki.env.example",
                         "opensearch.env.example", "prometheus.env.example"):
            status = copy_if_absent(source_root / "config" / relative,
                                    config_root / relative, transaction=transaction)
            result[status].append(str(config_root / relative))
        result["css_env"] = configure_css_runtime_env(config_root, transaction, result)
        if args.auto_configure_local_observability:
            result["datasources"] = configure_local_observability(source_root, config_root, transaction)

        ensure_dir(state_root, 0o750, transaction)
        ensure_dir(state_root / "watch", 0o750, transaction)
        events = state_root / "events.jsonl"
        if events.is_symlink():
            raise ValueError(f"refusing symlink path: {events}")
        if not events.exists():
            transaction.snapshot_file(events)
            events.touch(mode=0o640)
            result["installed"].append(str(events))
        else:
            regular(events)
            result["preserved"].append(str(events))

        runtime_path = config_root / "runtime.json"
        existing_runtime: dict[str, object] = {}
        if runtime_path.exists():
            existing_runtime = read_json_asset(runtime_path, require_schema=False)
            if existing_runtime.get("schema_version") not in {1, 2}:
                raise ValueError(f"unsupported AutoOps runtime configuration schema: {runtime_path}")
        runtime_payload = {
            "schema_version": 2,
            "instance_id": str(existing_runtime.get("instance_id") or
                                hashlib.sha256(str(config_root).encode("utf-8")).hexdigest()[:16]),
            "install_root": str(install_root),
            "config_root": str(config_root),
            "state_root": str(state_root),
            "state_db": str(state_root / "autoops-state.db"),
            "watch_state_dir": str(state_root / "watch"),
            "events_file": str(events),
            "outbox_file": str(state_root / "notifications.jsonl"),
            "deployment_mode": str(existing_runtime.get("deployment_mode", "installed")),
        }
        atomic_write(runtime_path, json.dumps(runtime_payload, ensure_ascii=False,
                                               indent=2, sort_keys=True) + "\n", 0o640, transaction)
        result["installed" if not existing_runtime else "updated"].append(str(runtime_path))

        ensure_dir(systemd_root, 0o755, transaction)
        for relative in SYSTEMD_FILES:
            source = source_root / "config" / "systemd" / relative
            destination = systemd_root / relative
            rendered = render_unit(source, install_root=install_root, config_root=config_root,
                                   state_root=state_root,
                                   service_user=args.service_user, service_group=args.service_group,
                                   python_executable=python_executable)
            if destination.is_symlink():
                raise ValueError(f"refusing symlink systemd unit: {destination}")
            if destination.exists():
                regular(destination)
                current = destination.read_text(encoding="utf-8")
                if not current.startswith(MANAGED_MARKER + "\n"):
                    result["preserved"].append(str(destination))
                    continue
                if current == rendered:
                    result["preserved"].append(str(destination))
                    continue
                atomic_write(destination, rendered, 0o644, transaction)
                result["installed"].append(str(destination))
            else:
                atomic_write(destination, rendered, 0o644, transaction)
                result["installed"].append(str(destination))

        # Ownership is part of the install contract, so apply it before the
        # manifest is calculated. The manifest contains hashes and metadata,
        # never customer configuration contents or credentials.
        if service_identity is not None:
            set_state_owner(state_root, *service_identity)
            set_config_access(config_root, service_identity[1])

        manifest = install_root / "autoops-install-manifest.json"
        previous_manifest: dict[str, object] | None = None
        if manifest.exists():
            previous_manifest = read_json_asset(manifest, require_schema=False)
            previous_schema = previous_manifest.get("schema_version")
            if previous_schema not in {1, 2}:
                raise ValueError(f"unsupported install manifest schema: {manifest}")
        file_records = manifest_file_records(
            (("install_root", install_root), ("config_root", config_root),
             ("systemd_root", systemd_root)), manifest)
        manifest_payload = {
            "schema_version": 2,
            "source_root": str(source_root),
            "install_root": str(install_root),
            "config_root": str(config_root),
            "state_root": str(state_root),
            "systemd_root": str(systemd_root),
            "service_user": args.service_user,
            "service_group": args.service_group,
            "python_executable": str(python_executable),
            "managed_marker": MANAGED_MARKER,
            "files": sorted(result["installed"] + result["updated"] + result["preserved"]),
            "artifact": {"kind": "runtime-install", "source_root": str(source_root)},
            "artifact_sha256": None,
            "instance": {
                "instance_id": runtime_payload["instance_id"],
                "runtime_file": str(runtime_path),
                "deployment_mode": runtime_payload["deployment_mode"],
            },
            "roots": {
                "install": str(install_root), "config": str(config_root),
                "state": str(state_root), "systemd": str(systemd_root),
            },
            "file_records": file_records,
            "ownership": {
                "service_user": args.service_user,
                "service_group": args.service_group,
                "state_and_config_applied": service_identity is not None,
            },
        }
        if previous_manifest and previous_manifest.get("schema_version") == 1:
            manifest_payload["migrated_from"] = {
                "schema_version": 1,
                "manifest_sha256": previous_manifest.get("manifest_sha256"),
            }
        manifest_payload["manifest_sha256"] = hashlib.sha256(
            json.dumps(manifest_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        atomic_write(manifest, json.dumps(manifest_payload, ensure_ascii=False, indent=2) + "\n", 0o640, transaction)
        result["manifest"] = [str(manifest)]
        result["service_account"] = [
            f"{args.service_user}:{args.service_group}" if service_identity is not None else "not-managed"
        ]
        result["status"] = ["READY"]
        return result
    except Exception:
        transaction.rollback()
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install the JiuwenSwarm AutoOps glue runtime.")
    parser.add_argument("--source-root", type=Path, default=ROOT)
    parser.add_argument("--install-root", type=Path, default=Path("/opt/Jiuwenswarm_AutoOps"))
    parser.add_argument("--config-root", type=Path,
                        default=Path(os.environ.get("AUTOOPS_CONFIG_ROOT", "/etc/jiuwenswarm-autoops")))
    parser.add_argument("--state-root", type=Path,
                        default=Path(os.environ.get("AUTOOPS_STATE_ROOT", "/var/lib/jiuwenswarm-autoops")))
    parser.add_argument("--systemd-root", type=Path,
                        default=Path(os.environ.get("AUTOOPS_SYSTEMD_ROOT", "/etc/systemd/system")))
    parser.add_argument("--service-user", default="jiuwenswarm-autoops")
    parser.add_argument("--service-group", default="jiuwenswarm-autoops")
    parser.add_argument("--python-executable", type=Path,
                        help="service Python interpreter; must be accessible to the systemd account and Python 3.9+")
    parser.add_argument("--no-create-service-account", dest="create_service_account", action="store_false",
                        help="do not create the default systemd service account on a root host install")
    parser.add_argument("--no-auto-configure-local-observability", dest="auto_configure_local_observability",
                        action="store_false", help="do not discover healthy local Loki, Prometheus, or OpenSearch endpoints")
    parser.set_defaults(create_service_account=True, auto_configure_local_observability=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(install(args), ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "INPUT_ERROR", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
