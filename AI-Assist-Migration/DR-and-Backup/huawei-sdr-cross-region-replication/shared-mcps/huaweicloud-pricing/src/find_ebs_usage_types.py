#!/usr/bin/env python3
import json
import time

from pricing_catalog_helper import load_env_file, call_get

SERVICE_TYPE_CODE = "hws.service.type.ebs"
RESOURCE_TYPE_CODE = "hws.resource.type.volume"

def main():
    load_env_file()

    limit = 100
    offset = 0
    total_count = None
    matches = []

    while True:
        result = call_get("/v2/products/usage-types", {
            "limit": limit,
            "offset": offset,
        })

        status = result.get("http_status")
        data = result.get("data", {})

        if status != 200:
            print(json.dumps({
                "status": "ERROR",
                "offset": offset,
                "http_status": status,
                "response": data,
            }, indent=2, ensure_ascii=False))
            return

        if total_count is None:
            total_count = data.get("total_count", 0)

        usage_types = data.get("usage_types", [])

        for item in usage_types:
            if (
                item.get("service_type_code") == SERVICE_TYPE_CODE
                or item.get("resource_type_code") == RESOURCE_TYPE_CODE
            ):
                matches.append(item)

        offset += limit

        if offset >= total_count:
            break

        time.sleep(0.15)

    print(json.dumps({
        "status": "OK",
        "searched_total_count": total_count,
        "service_type_code_filter": SERVICE_TYPE_CODE,
        "resource_type_code_filter": RESOURCE_TYPE_CODE,
        "matches_count": len(matches),
        "matches": matches,
    }, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
