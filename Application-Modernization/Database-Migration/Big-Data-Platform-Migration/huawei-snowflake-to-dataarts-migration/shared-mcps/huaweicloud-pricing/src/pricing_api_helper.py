#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path

from pricing_catalog_helper import load_env_file, create_client


def read_product_infos(path: str):
    data = json.loads(Path(path).read_text())

    if isinstance(data, list):
        return data

    if isinstance(data, dict) and isinstance(data.get("product_infos"), list):
        return data["product_infos"]

    raise RuntimeError("Input file must be a JSON array or an object with product_infos array.")


def call_post(path: str, payload: dict):
    client = create_client()

    response = client.do_http_request(
        method="POST",
        resource_path=path,
        path_params={},
        query_params={},
        header_params={
            "Content-Type": "application/json;charset=UTF-8",
            "X-Language": "en_US"
        },
        body=payload,
        post_params={},
        cname=None,
        response_type=None,
        response_headers=None,
        collection_formats={},
        request_type=None,
        async_request=False,
    )

    status = getattr(response, "status_code", None)
    content = getattr(response, "content", b"")

    try:
        data = response.json() if content else {}
    except Exception:
        data = {"raw": content.decode("utf-8", errors="replace")}

    return {
        "http_status": status,
        "path": path,
        "request_summary": {
            "project_id": payload.get("project_id"),
            "product_infos_count": len(payload.get("product_infos", [])),
            "inquiry_precision": payload.get("inquiry_precision")
        },
        "data": data
    }


def main():
    load_env_file()

    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["on-demand-price", "period-price"])
    parser.add_argument("--product-infos-file", required=True)
    parser.add_argument("--project-id", default=os.environ.get("HUAWEI_PROJECT_ID", ""))
    parser.add_argument("--inquiry-precision", type=int, default=1)

    args = parser.parse_args()

    if not args.project_id:
        raise RuntimeError("project_id is required. Set HUAWEI_PROJECT_ID or pass --project-id.")

    product_infos = read_product_infos(args.product_infos_file)

    payload = {
        "project_id": args.project_id,
        "product_infos": product_infos
    }

    if args.operation == "on-demand-price":
        payload["inquiry_precision"] = args.inquiry_precision
        api_path = "/v2/bills/ratings/on-demand-resources"
    else:
        api_path = "/v2/bills/ratings/period-resources/subscribe-rate"

    result = call_post(api_path, payload)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
