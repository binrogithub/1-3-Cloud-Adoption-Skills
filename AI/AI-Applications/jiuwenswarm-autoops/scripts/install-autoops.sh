#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_PATH="$(readlink -f -- "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd -- "$(dirname -- "$SCRIPT_PATH")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
source_root="${AUTOOPS_SOURCE_ROOT:-${PROJECT_ROOT}}"
install_root="${AUTOOPS_INSTALL_ROOT:-/opt/Jiuwenswarm_AutoOps}"
config_root="${AUTOOPS_CONFIG_ROOT:-/etc/jiuwenswarm-autoops}"
state_root="${AUTOOPS_STATE_ROOT:-/var/lib/jiuwenswarm-autoops}"
systemd_root="${AUTOOPS_SYSTEMD_ROOT:-/etc/systemd/system}"
skills_dir="${JIUWENSWARM_AGENT_SKILLS_DIR:-${HOME}/.jiuwenswarm/agent/workspace/skills}"
install_components=0
skip_skills=0
no_service_account=0
no_local_observability=0
configure_model=0
bin_dir=""
deployment_mode="${AUTOOPS_DEPLOYMENT_MODE:-preserve-existing}"

usage() {
  cat <<'EOF'
Usage: install-autoops.sh [options]

Installs the project-owned AutoOps glue runtime. External observability and
execution engines are not downloaded or started unless --install-components is
explicitly supplied.

  --source-root PATH       Source checkout or a self-contained release tree
  --install-root PATH      Published AutoOps runtime root
  --config-root PATH       External customer configuration root
  --state-root PATH        Durable task/event state root
  --systemd-root PATH      Systemd unit destination
  --skills-dir PATH        JiuwenSwarm user Skill library
  --bin-dir PATH           Publish Jiuwen_autoops_tui aliases into PATH
  --deployment-mode MODE   preserve-existing (default) or full-access-test
  --install-components     Run the pinned component download step first
  --configure-model        Interactively configure MaaS model and API key
  --skip-skills            Do not register project Skills
  --no-create-service-account
  --no-auto-configure-local-observability
  -h, --help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source-root) source_root="$2"; shift 2 ;;
    --install-root) install_root="$2"; shift 2 ;;
    --config-root) config_root="$2"; shift 2 ;;
    --state-root) state_root="$2"; shift 2 ;;
    --systemd-root) systemd_root="$2"; shift 2 ;;
    --skills-dir) skills_dir="$2"; shift 2 ;;
    --bin-dir) bin_dir="$2"; shift 2 ;;
    --deployment-mode) deployment_mode="$2"; shift 2 ;;
    --install-components) install_components=1; shift ;;
    --configure-model) configure_model=1; shift ;;
    --skip-skills) skip_skills=1; shift ;;
    --no-create-service-account) no_service_account=1; shift ;;
    --no-auto-configure-local-observability) no_local_observability=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) printf 'unknown option: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done

case "$deployment_mode" in
  preserve-existing|full-access-test) ;;
  *) printf 'unsupported deployment mode: %s\n' "$deployment_mode" >&2; exit 2 ;;
esac

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    printf 'missing required command for AutoOps installation: %s\n' "$1" >&2
    exit 2
  }
}

require_command python3
require_command readlink

if (( install_components == 1 )); then
  require_command bash
  printf '[1/3] Downloading pinned external components\n' >&2
  JIUWENSWARM_ROOT="${JIUWENSWARM_ROOT:-/opt/JiuwenSwarm}" \
    bash "${source_root}/scripts/bootstrap-components.sh"
else
  printf '[1/3] External component download skipped (use --install-components to enable)\n' >&2
fi

runtime_args=(--source-root "$source_root" --install-root "$install_root"
  --config-root "$config_root" --state-root "$state_root" --systemd-root "$systemd_root")
(( no_service_account == 1 )) && runtime_args+=(--no-create-service-account)
(( no_local_observability == 1 )) && runtime_args+=(--no-auto-configure-local-observability)
printf '[2/3] Publishing AutoOps runtime\n' >&2
python3 "${source_root}/scripts/install-autoops-runtime.py" "${runtime_args[@]}"

if (( configure_model == 1 )); then
  printf '[model] Configuring the shared JiuwenSwarm model entry\n' >&2
  python3 "${install_root}/scripts/configure-model.py" --config-root "$config_root"
fi

if (( skip_skills == 0 )); then
  printf '[3/3] Registering AutoOps Skills\n' >&2
  python3 "${source_root}/scripts/install-jiuwenswarm-autoops-skills.py" \
    --skills-dir "$skills_dir" --deployment-mode "$deployment_mode"
else
  printf '[3/3] Skill registration skipped\n' >&2
fi

if [[ -n "$bin_dir" ]]; then
  mkdir -p "$bin_dir"
  for command_name in Jiuwen_autoops_tui jiuwen_autoops_tui; do
    link="$bin_dir/$command_name"
    target="$install_root/scripts/Jiuwen_autoops_tui"
    if [[ -e "$link" || -L "$link" ]]; then
      current="$(readlink -f -- "$link" 2>/dev/null || true)"
      [[ "$current" == "$(readlink -f -- "$target")" ]] || {
        printf 'refusing to replace existing command alias: %s\n' "$link" >&2
        exit 2
      }
    else
      ln -s -- "$target" "$link"
    fi
  done
  printf 'Published TUI aliases in %s\n' "$bin_dir" >&2
fi

printf 'AutoOps installation completed. Runtime=%s Config=%s State=%s\n' \
  "$install_root" "$config_root" "$state_root" >&2
