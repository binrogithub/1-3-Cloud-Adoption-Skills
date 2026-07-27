#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkobs.v1 import ObsClient, PutObjectRequest
from huaweicloudsdkobs.v1.region.obs_region import ObsRegion


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing {name}")
    return value


def obs_client(region: str, ak: str, sk: str) -> ObsClient:
    return ObsClient.new_builder() \
        .with_credentials(BasicCredentials(ak, sk)) \
        .with_region(ObsRegion.value_of(region)) \
        .build()


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload exported migration CSV files to Huawei Cloud OBS.")
    parser.add_argument("--source-dir", type=Path, default=Path("data/export"))
    parser.add_argument("--region", default=os.getenv("OBS_REGION", "la-south-2"))
    parser.add_argument("--bucket", default=os.getenv("OBS_BUCKET", ""))
    parser.add_argument("--prefix", default=os.getenv("OBS_PREFIX", "teradata-dws-demo/export"))
    parser.add_argument("--ak", default=os.getenv("OBS_AK") or os.getenv("CLOUD_SDK_AK") or os.getenv("AK"))
    parser.add_argument("--sk", default=os.getenv("OBS_SK") or os.getenv("CLOUD_SDK_SK") or os.getenv("SK"))
    args = parser.parse_args()

    if not args.bucket or args.bucket.startswith("replace-with-"):
        raise RuntimeError("Missing OBS bucket. Set OBS_BUCKET or --bucket.")
    if not args.ak or not args.sk:
        raise RuntimeError("Missing OBS credentials. Set OBS_AK/OBS_SK, CLOUD_SDK_AK/CLOUD_SDK_SK, or AK/SK.")
    if not args.source_dir.exists():
        raise RuntimeError(f"Source directory not found: {args.source_dir}")

    client = obs_client(args.region, args.ak, args.sk)
    prefix = args.prefix.strip("/")
    files = sorted(args.source_dir.glob("*.csv"))
    if not files:
        raise RuntimeError(f"No CSV files found in {args.source_dir}")

    for path in files:
        key = f"{prefix}/{path.name}" if prefix else path.name
        with path.open("rb") as handle:
            response = client.put_object(
                PutObjectRequest(
                    bucket_name=args.bucket,
                    object_key=key,
                    stream=handle,
                )
            )
        status = getattr(response, "status_code", None) or getattr(response, "status", "")
        print(f"uploaded obs://{args.bucket}/{key} status={status}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except exceptions.ClientRequestException as exc:
        print(f"Huawei Cloud API error: status={exc.status_code} request_id={exc.request_id} code={exc.error_code}", file=sys.stderr)
        print(exc.error_msg, file=sys.stderr)
        raise SystemExit(2)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)

