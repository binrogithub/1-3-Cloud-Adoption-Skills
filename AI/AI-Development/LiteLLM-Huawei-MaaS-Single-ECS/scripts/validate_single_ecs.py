#!/usr/bin/env python3
import argparse
import json
import sys
import urllib.error
import urllib.request


def post_json(url: str, payload: dict, bearer_token: str | None = None) -> dict:
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    request = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate direct Huawei MaaS access and proxied LiteLLM access on a single ECS host."
    )
    parser.add_argument("--maas-base-url", required=True)
    parser.add_argument("--maas-api-key", required=True)
    parser.add_argument("--maas-model", default="glm-5.1")
    parser.add_argument("--proxy-base-url", required=True)
    parser.add_argument("--proxy-api-key", required=True)
    parser.add_argument("--proxy-model", default="huawei/glm-5.1")
    parser.add_argument("--prompt", default="hello")
    args = parser.parse_args()

    direct_payload = {
        "model": args.maas_model,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": args.prompt},
        ],
    }
    proxy_payload = {
        "model": args.proxy_model,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": args.prompt},
        ],
    }

    try:
        direct_response = post_json(
            f"{args.maas_base_url.rstrip('/')}/chat/completions",
            payload=direct_payload,
            bearer_token=args.maas_api_key,
        )
        proxy_response = post_json(
            f"{args.proxy_base_url.rstrip('/')}/chat/completions",
            payload=proxy_payload,
            bearer_token=args.proxy_api_key,
        )
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code}: {error_body}", file=sys.stderr)
        return 1

    output = {
        "direct_model": direct_response.get("model"),
        "direct_content": direct_response["choices"][0]["message"]["content"],
        "proxy_model": proxy_response.get("model"),
        "proxy_content": proxy_response["choices"][0]["message"]["content"],
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
