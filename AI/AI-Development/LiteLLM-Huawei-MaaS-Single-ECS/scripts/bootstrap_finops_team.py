#!/usr/bin/env python3
import argparse
import json
import sys
import urllib.error
import urllib.request


def post_json(url: str, token: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create one LiteLLM team and one scoped virtual key for FinOps or multi-user proxy onboarding."
    )
    parser.add_argument("--proxy-base-url", required=True)
    parser.add_argument("--master-key", required=True)
    parser.add_argument("--team-alias", required=True)
    parser.add_argument("--model", default="huawei/glm-5.1")
    parser.add_argument("--max-budget", type=float, default=None)
    parser.add_argument("--budget-duration", default=None)
    parser.add_argument("--tpm-limit", type=int, default=None)
    parser.add_argument("--rpm-limit", type=int, default=None)
    parser.add_argument("--key-alias", default=None)
    parser.add_argument("--key-duration", default="30d")
    parser.add_argument("--metadata-json", default=None)
    args = parser.parse_args()

    base_url = args.proxy_base_url.rstrip("/")
    metadata = {}
    if args.metadata_json:
        metadata = json.loads(args.metadata_json)

    team_payload = {
        "team_alias": args.team_alias,
        "models": [args.model],
        "metadata": metadata,
    }
    if args.max_budget is not None:
        team_payload["max_budget"] = args.max_budget
    if args.budget_duration is not None:
        team_payload["budget_duration"] = args.budget_duration
    if args.tpm_limit is not None:
        team_payload["tpm_limit"] = args.tpm_limit
    if args.rpm_limit is not None:
        team_payload["rpm_limit"] = args.rpm_limit

    try:
        team_response = post_json(
            f"{base_url}/team/new",
            token=args.master_key,
            payload=team_payload,
        )
        team_id = team_response["team_id"]

        key_payload = {
            "team_id": team_id,
            "key_alias": args.key_alias or f"{args.team_alias}-key",
            "models": [args.model],
            "duration": args.key_duration,
            "metadata": metadata,
        }
        if args.max_budget is not None:
            key_payload["max_budget"] = args.max_budget
        if args.budget_duration is not None:
            key_payload["budget_duration"] = args.budget_duration
        if args.tpm_limit is not None:
            key_payload["tpm_limit"] = args.tpm_limit
        if args.rpm_limit is not None:
            key_payload["rpm_limit"] = args.rpm_limit

        key_response = post_json(
            f"{base_url}/key/generate",
            token=args.master_key,
            payload=key_payload,
        )
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code}: {error_body}", file=sys.stderr)
        return 1

    output = {
        "team_id": team_id,
        "team_alias": args.team_alias,
        "issued_key_alias": key_response.get("key_alias"),
        "issued_key": key_response.get("key"),
        "allowed_models": key_response.get("models"),
    }
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
