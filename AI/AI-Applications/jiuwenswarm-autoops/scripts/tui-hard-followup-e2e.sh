#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_PATH="$(readlink -f -- "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd -- "$(dirname -- "$SCRIPT_PATH")" && pwd)"
SESSION="${1:?session name required}"
FIRST_REQUEST="${2:?first request required}"
SECOND_REQUEST="${3:?follow-up request required}"
SWARM_HOME="${JIUWENSWARM_HOME:-/root/.jiuwenswarm}"
HISTORY="${JIUWENSWARM_SESSION_DIR:-$SWARM_HOME/agent/sessions}/${SESSION}/history.jsonl"

[[ "$SESSION" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$ ]] || { echo 'invalid session name' >&2; exit 2; }
python3 "$SCRIPT_DIR/install-jiuwenswarm-autoops-skills.py" >/dev/null

export AUTOOPS_FOLLOWUP_HISTORY="$HISTORY"
export AUTOOPS_FOLLOWUP_FIRST="$FIRST_REQUEST"
export AUTOOPS_FOLLOWUP_SECOND="$SECOND_REQUEST"
export SESSION
expect <<'EOF'
  log_user 0
  set timeout 5
  spawn -noecho jiuwenswarm-tui --persist-session --session $env(SESSION)
  set deadline [expr {[clock seconds] + 360}]
  set first_at [expr {[clock seconds] + 12}]
  set first_sent 0
  set second_sent 0
  set second_pos -1
  while {[clock seconds] < $deadline} {
    expect -timeout 0 {
      -re {.+} {}
      timeout {}
    }
    if {$first_sent == 0 && [clock seconds] >= $first_at} {
      send -- "#autoops-project-manager $env(AUTOOPS_FOLLOWUP_FIRST)\r"
      set first_sent 1
    }
    if {[file exists $env(AUTOOPS_FOLLOWUP_HISTORY)]} {
      set stream [open $env(AUTOOPS_FOLLOWUP_HISTORY) r]
      set history [read $stream]
      close $stream
      set last_result [string last "\"event_type\": \"chat.tool_result\"" $history]
      set last_final [string last "\"event_type\": \"chat.final\"" $history]
      if {$first_sent == 1 && $second_sent == 0 && $last_result >= 0 && $last_final > $last_result} {
        send -- "#autoops-project-manager $env(AUTOOPS_FOLLOWUP_SECOND)\r"
        set second_sent 1
        set second_pos [string length $history]
      }
      if {$second_sent == 1 && [string length $history] > $second_pos} {
        set new_history [string range $history $second_pos end]
        set new_result [string last "\"event_type\": \"chat.tool_result\"" $new_history]
        set new_final [string last "\"event_type\": \"chat.final\"" $new_history]
        set new_call [string last "\"event_type\": \"chat.tool_call\"" $new_history]
        # A continuity question may be answerable from the durable history and
        # therefore legitimately has no second operational tool call.
        if {$new_final >= 0 && (($new_result >= 0 && $new_final > $new_result) || ($new_result < 0 && $new_call < $new_final))} {
          puts "TUI_FOLLOWUP_RESULT=PASS"
          puts "SESSION=$env(SESSION)"
          puts "HISTORY=$env(AUTOOPS_FOLLOWUP_HISTORY)"
          catch {close}
          catch {wait}
          exit 0
        }
      }
    }
    after 1000
  }
  puts stderr "follow-up TUI turn did not complete: $env(SESSION)"
  catch {close}
  catch {wait}
  exit 1
EOF
