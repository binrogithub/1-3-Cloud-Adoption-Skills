#!/usr/bin/env python3
"""Connectivity + one functional delegate smoke test."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ENV_PATH, HYBRID_DIR, SKILL_ROOT, chat_completion, load_env  # noqa: E402


def main() -> int:
    env = load_env()
    print(f"hybrid_dir={HYBRID_DIR}")
    print(f"env_file={ENV_PATH} exists={ENV_PATH.exists()}")
    print(f"base={env.get('DELEGATE_API_BASE')}")
    print(f"model={env.get('DELEGATE_MODEL')}")
    if not env.get("DELEGATE_API_KEY"):
        print("VERIFY FAIL: DELEGATE_API_KEY missing")
        return 2

    try:
        resp = chat_completion(
            messages=[{"role": "user", "content": "Reply with exactly: pong"}],
            max_tokens=32,
        )
        content = resp["choices"][0]["message"]["content"]
        print(f"ping_content={content!r}")
    except Exception as e:  # noqa: BLE001
        err = str(e)
        print(f"VERIFY FAIL: connectivity: {err}")
        if "81003" in err or "Invalid authorization" in err:
            alt = (
                "https://api.modelarts-maas.com/openai/v1"
                if "ap-southeast-1" in (env.get("DELEGATE_API_BASE") or "")
                else "https://api-ap-southeast-1.modelarts-maas.com/openai/v1"
            )
            print(
                "HINT: MaaS keys are region-bound. Re-install with the other base, e.g.\n"
                f'  python .../install.py --base-url "{alt}" --api-key "<key>"'
            )
        return 1

    brief = {
        "goal": "Return a JSON success for smoke test without editing files",
        "files": [],
        "acceptance": "status success and acceptance_met true",
        "constraints": ["Do not modify any files", "Keep summary short"],
        "max_attempts": 1,
    }
    proc = subprocess.run(
        [
            sys.executable,
            str(SKILL_ROOT / "scripts" / "delegate.py"),
            "--brief",
            json.dumps(brief),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    print(proc.stdout)
    if proc.stderr:
        print(proc.stderr, file=sys.stderr)

    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError:
        print("VERIFY FAIL: delegate smoke non-JSON")
        return 1

    if result.get("status") not in ("success", "needs_escalation", "failed"):
        print("VERIFY FAIL: unexpected delegate status")
        return 1

    if result.get("status") == "success":
        print("VERIFY PASS (connectivity + delegate smoke)")
        return 0

    print("VERIFY FAIL: delegate smoke non-success")
    print(f"delegate_status={result.get('status')}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
