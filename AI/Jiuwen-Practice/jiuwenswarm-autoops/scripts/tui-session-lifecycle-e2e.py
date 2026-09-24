#!/usr/bin/env python3
"""Run two TUI clients against one persistent session without expect."""
from __future__ import annotations

import argparse
import os
import pty
import select
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def terminate(process: subprocess.Popen, master: int) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
    try:
        os.close(master)
    except OSError:
        pass


def drive_turn(session: str, history: Path, prompt: str, checker: Path, timeout: int) -> bool:
    master, slave = pty.openpty()
    process = subprocess.Popen(["jiuwenswarm-tui", "--persist-session", "--session", session],
                               stdin=slave, stdout=slave, stderr=slave, close_fds=True)
    os.close(slave)
    sent = False
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            readable, _, _ = select.select([master], [], [], 0.5)
            if readable:
                try:
                    os.read(master, 8192)
                except OSError:
                    pass
            if not sent and time.monotonic() + 0.1 >= deadline - timeout + 12:
                os.write(master, (prompt + "\r").encode("utf-8"))
                sent = True
            if sent and history.is_file():
                check = subprocess.run([sys.executable, str(checker), str(history)],
                                       text=True, capture_output=True, check=False, timeout=5)
                # The first turn uses the strict operational completion checker;
                # the second turn uses lifecycle continuity after reconnect.
                if check.returncode == 0:
                    return True
        return False
    finally:
        terminate(process, master)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify TUI persistent-session reconnect continuity.")
    parser.add_argument("session")
    parser.add_argument("first_request")
    parser.add_argument("second_request")
    parser.add_argument("--timeout", type=int, default=int(os.environ.get("AUTOOPS_TUI_LIFECYCLE_TIMEOUT", "240")))
    args = parser.parse_args(argv)
    if not 30 <= args.timeout <= 900:
        print("timeout must be 30..900", file=sys.stderr)
        return 2
    if not args.session or len(args.session) > 128 or not all(char.isalnum() or char in "._-" for char in args.session):
        print("invalid session name", file=sys.stderr)
        return 2
    subprocess.run([sys.executable, str(ROOT / "scripts" / "install-jiuwenswarm-autoops-skills.py")], check=True)
    # A TUI session is meaningful only after both halves of the local backend
    # are reachable.  The launcher owns the detached supervisor; this check
    # makes a restart race visible before the PTY driver starts.
    import socket
    for port in (18092, 19001):
        with socket.create_connection(("127.0.0.1", port), timeout=5):
            pass
    swarm_home = Path(os.environ.get("JIUWENSWARM_HOME", "/root/.jiuwenswarm"))
    history = Path(os.environ.get("JIUWENSWARM_SESSION_DIR", str(swarm_home / "agent/sessions"))) / args.session / "history.jsonl"
    strict_checker = ROOT / "scripts" / "tui-history-completion-check.py"
    lifecycle_checker = ROOT / "scripts" / "tui-session-lifecycle-check.py"
    first = drive_turn(args.session, history, "#autoops-project-manager " + args.first_request,
                       strict_checker, args.timeout)
    if not first:
        print("TUI_LIFECYCLE_RESULT=FAIL stage=first-turn", file=sys.stderr)
        return 1
    second = drive_turn(args.session, history, "#autoops-project-manager " + args.second_request,
                        lifecycle_checker, args.timeout)
    if not second:
        print("TUI_LIFECYCLE_RESULT=FAIL stage=reconnect", file=sys.stderr)
        return 1
    check = subprocess.run([sys.executable, str(lifecycle_checker), str(history)],
                           text=True, capture_output=True, check=False)
    print("TUI_LIFECYCLE_RESULT=PASS")
    print(f"SESSION={args.session}")
    print(f"HISTORY={history}")
    print(check.stdout.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
