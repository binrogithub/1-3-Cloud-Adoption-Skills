#!/usr/bin/env python3
"""初始化滚动预算 demo 数据：建 team -> user -> virtual key，key 写入 .demo_key。只需运行一次。
Bootstrap demo data: create team -> user -> virtual key (saved to .demo_key). Run once."""
import json
import os
import re
import sys
import urllib.error
import urllib.request

BASE = os.getenv("LITELLM_URL", "http://localhost:4000")
_ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")


def _master_key() -> str:
    if os.getenv("LITELLM_MASTER_KEY"):
        return os.environ["LITELLM_MASTER_KEY"]
    with open(_ENV_FILE) as f:
        for line in f:
            m = re.match(r"LITELLM_MASTER_KEY\s*=\s*['\"]?([^'\"\n]+)", line)
            if m:
                return m.group(1)
    sys.exit(
        "在环境变量和 ../.env 里都找不到 LITELLM_MASTER_KEY\n"
        "LITELLM_MASTER_KEY not found in environment variables or ../.env"
    )


MASTER_KEY = _master_key()


def post(path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {MASTER_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"ERROR {path}: {e.code} {e.read().decode()}")
        sys.exit(1)


team = post("/team/new", {"team_alias": "opencode-go-demo"})
team_id = team["team_id"]
print(f"team : {team_id} (opencode-go-demo)")

user = post("/user/new", {"user_id": "demo-user", "team_id": team_id})
print("user : demo-user")

key = post(
    "/key/generate",
    {"user_id": "demo-user", "team_id": team_id, "key_alias": "rolling-budget-demo-key"},
)
key_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".demo_key")
with open(key_path, "w") as f:
    f.write(key["key"])
print(f"key  : {key['key']}  (已保存到 saved to demo/.demo_key)")
print("\n初始化完成，运行 ./demo.py 开始演示")
print("Setup complete — run ./demo.py to start the demo")
