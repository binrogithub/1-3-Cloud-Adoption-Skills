#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<'EOF'
Usage: tui-autoops-e2e.sh --prompt TEXT [--session NAME] [--expected-role ROLE]
                          [--expected-source SOURCE] [--timeout SECONDS]

Drives jiuwenswarm-tui and uses the session history as the completion signal.
This avoids matching terminal redraw output from the alternate screen.
EOF
}

prompt=""
session="autoops-e2e-$(date -u +%Y%m%dT%H%M%SZ)-$$"
expected_role=""
expected_source=""
timeout_seconds=180
history_checker="${SCRIPT_DIR}/tui-history-completion-check.py"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --prompt) prompt="${2:-}"; shift 2 ;;
    --session) session="${2:-}"; shift 2 ;;
    --expected-role) expected_role="${2:-}"; shift 2 ;;
    --expected-source) expected_source="${2:-}"; shift 2 ;;
    --timeout) timeout_seconds="${2:-}"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) printf 'unknown argument: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ -n "$prompt" ]] || { printf '%s\n' '--prompt is required' >&2; exit 2; }
[[ "$session" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$ ]] || {
  printf 'invalid session name\n' >&2; exit 2;
}
[[ "$timeout_seconds" =~ ^[0-9]+$ ]] && (( timeout_seconds >= 10 && timeout_seconds <= 900 )) || {
  printf 'timeout must be an integer from 10 through 900\n' >&2; exit 2;
}
[[ -f "$history_checker" ]] || { printf 'missing history checker: %s\n' "$history_checker" >&2; exit 1; }
command -v expect >/dev/null 2>&1 || { printf 'missing required command: expect\n' >&2; exit 1; }
command -v jiuwenswarm-tui >/dev/null 2>&1 || { printf 'missing required command: jiuwenswarm-tui\n' >&2; exit 1; }

swarm_home="${JIUWENSWARM_HOME:-/root/.jiuwenswarm}"
session_dir="${JIUWENSWARM_SESSION_DIR:-${swarm_home}/agent/sessions}"
history_file="${session_dir}/${session}/history.jsonl"

AUTOOPS_PROMPT="$prompt" \
AUTOOPS_SESSION="$session" \
AUTOOPS_HISTORY="$history_file" \
AUTOOPS_EXPECTED_ROLE="$expected_role" \
AUTOOPS_EXPECTED_SOURCE="$expected_source" \
AUTOOPS_TIMEOUT="$timeout_seconds" \
AUTOOPS_HISTORY_CHECKER="$history_checker" \
expect <<'EOF'
  log_user 0
  set timeout 5
  spawn -noecho jiuwenswarm-tui --persist-session --session $env(AUTOOPS_SESSION)
  set child_pid [exp_pid]
  set deadline [expr {[clock seconds] + $env(AUTOOPS_TIMEOUT)}]
  set result "TIMEOUT"
  set next_send [expr {[clock seconds] + 12}]
  set bootstrap_sent 0
  while {[clock seconds] < $deadline} {
    # Drain alternate-screen redraw traffic so the child cannot block on a
    # full pseudo-terminal while the history file is being polled.
    expect -timeout 0 {
      -re {.+} {}
      timeout {}
    }
    if {[clock seconds] >= $next_send} {
      if {!$bootstrap_sent} {
        # The explicit CLI session is already new. Set Team/SwarmFlow for this
        # turn, but avoid /new because the current backend rejects its
        # ID-less session.create compatibility request.
        send -- "/mode team\r"
        after 1200
        send -- "/swarmflow on\r"
        after 1200
        set bootstrap_sent 1
      }
      # TUI can start before the WebSocket session is ready. Retry only while
      # metadata confirms that no user message has been accepted yet.
      set message_count 0
      set metadata_file [file join [file dirname $env(AUTOOPS_HISTORY)] metadata.json]
      if {[file exists $metadata_file]} {
        set stream [open $metadata_file r]
        set metadata [read $stream]
        close $stream
        if {[regexp {"message_count": ([0-9]+)} $metadata -> count]} {
          set message_count $count
        }
      }
      if {$message_count == 0} {
        send -- "$env(AUTOOPS_PROMPT)\r"
        set next_send [expr {[clock seconds] + 5}]
      } else {
        set next_send [expr {[clock seconds] + 60}]
      }
    }
    if {[file exists $env(AUTOOPS_HISTORY)]} {
      set stream [open $env(AUTOOPS_HISTORY) r]
      set history [read $stream]
      close $stream
      set role_ok 1
      set source_ok 1
      if {$env(AUTOOPS_EXPECTED_ROLE) ne ""} {
        set role_ok [regexp "selected_role.*$env(AUTOOPS_EXPECTED_ROLE)" $history]
      }
      if {$env(AUTOOPS_EXPECTED_SOURCE) ne ""} {
        set source_ok [regexp "source.*$env(AUTOOPS_EXPECTED_SOURCE)" $history]
      }
      set checker_ok 0
      if {[catch {exec python3 $env(AUTOOPS_HISTORY_CHECKER) $env(AUTOOPS_HISTORY)} checker_output] == 0} {
        if {[regexp {"ready": true} $checker_output]} {
          set checker_ok 1
        }
      }
      # A successful tool result is intermediate state.  Require the durable
      # history checker to observe a non-empty assistant final after the last
      # operational result, otherwise this driver would stop the TUI and
      # create a false PASS before ProjectManager finished its turn.
      if {$role_ok && $source_ok && [regexp {chat\.tool_result} $history] && [regexp {success=True} $history] && $checker_ok} {
        set result "PASS"
        break
      }
    }
    after 1000
  }
  puts "TUI_RESULT=$result"
  puts "SESSION=$env(AUTOOPS_SESSION)"
  puts "HISTORY=$env(AUTOOPS_HISTORY)"
  send -- "/exit\r"
  after 2000
  catch {close}
  catch {wait}
  exit [expr {$result eq "PASS" ? 0 : 1}]
EOF
