#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path

from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkcore.client import Client, ClientBuilder
from huaweicloudsdkcore.exceptions.exceptions import HostUnreachableException
from huaweicloudsdkcore.http.http_config import HttpConfig
from huaweicloudsdkcore.region.region import Region
from huaweicloudsdkcore.sdk_request import SdkRequest
from huaweicloudsdkcore.sdk_response import FutureSdkResponse


ENV_FILE = "/root/.config/maas-pricing/pricing-env"


def load_env_file(path: str = ENV_FILE):
    env_path = Path(path)

    if not env_path.exists():
        raise RuntimeError(f"Env file not found: {path}")

    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("export "):
            line = line[len("export "):]

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


class CustomClient(Client):
    def build_future_request(
        self,
        method,
        resource_path,
        path_params,
        query_params,
        header_params,
        request_body,
        post_params,
        cname,
        response_type,
        collection_formats,
        progress_callback,
    ):
        url_parse_result = self._url_parse(cname)
        schema = url_parse_result.scheme
        host = url_parse_result.netloc

        header_params = self._parse_header_params(collection_formats, header_params)
        resource_path = self._parse_path_params(
            collection_formats,
            path_params,
            resource_path,
            self._credentials.get_update_path_params(),
        )
        query_params = self._parse_query_params(collection_formats, query_params)
        post_params = self._parse_post_params(collection_formats, post_params)

        if (
            self._config.ignore_content_type_for_get_request
            and method == "GET"
            and not request_body
        ):
            header_params.pop(self._CONTENT_TYPE, None)
        else:
            header_params.setdefault(self._CONTENT_TYPE, self._APPLICATION_JSON)

        body = self._parse_body(request_body, post_params)

        sdk_request = SdkRequest(
            method=method,
            schema=schema,
            host=host,
            resource_path=resource_path,
            query_params=query_params,
            header_params=header_params,
            body=body,
            stream=False,
            signing_algorithm=self._config.signing_algorithm,
        )

        return self._credentials.process_auth_request(sdk_request, self._http_client)

    def do_http_request(
        self,
        method,
        resource_path,
        path_params=None,
        query_params=None,
        header_params=None,
        body=None,
        post_params=None,
        cname=None,
        response_type=None,
        response_headers=None,
        collection_formats=None,
        request_type=None,
        async_request=False,
        progress_callback=None,
    ):
        if async_request:
            future_request = self.build_future_request(
                method,
                resource_path,
                path_params,
                query_params,
                header_params,
                body,
                post_params,
                cname,
                response_type,
                collection_formats,
                progress_callback,
            )
            future_response = self._http_client.executor.submit(
                self._do_http_request_async,
                future_request,
                response_type,
                response_headers,
                progress_callback,
            )
            return FutureSdkResponse(future_response, self._logger)

        while True:
            try:
                request = self.build_future_request(
                    method,
                    resource_path,
                    path_params or {},
                    query_params or {},
                    header_params or {},
                    body,
                    post_params or {},
                    cname,
                    response_type,
                    collection_formats or {},
                    progress_callback,
                ).result()

                response = self._do_http_request_sync(request)
                break

            except HostUnreachableException as exc:
                with self._mutex:
                    if self._endpoint_index < len(self._endpoints) - 1:
                        self._endpoint_index += 1
                    else:
                        self._endpoint_index = 0
                        raise exc

        return response


def create_client(endpoint_host=None):
    ak = os.environ.get("HUAWEI_ACCESS_KEY")
    sk = os.environ.get("HUAWEI_SECRET_KEY")
    region = os.environ.get("HUAWEI_DEFAULT_REGION", "la-north-2")

    if endpoint_host is None:
        endpoint_host = os.environ.get("HUAWEI_PRICING_ENDPOINT", "bss-intl.myhuaweicloud.com")

    endpoint = f"https://{endpoint_host}"

    if not ak or not sk:
        raise RuntimeError("HUAWEI_ACCESS_KEY/HUAWEI_SECRET_KEY are required")

    credentials = BasicCredentials(ak, sk)

    http_config = HttpConfig()
    http_config.ignore_ssl_verification = False
    http_config.ignore_content_type_for_get_request = True

    return (
        ClientBuilder(CustomClient)
        .with_http_config(http_config)
        .with_credentials(credentials)
        .with_region(Region(id=region, endpoint=endpoint))
        .build()
    )


def call_get(path: str, query: dict):
    client = create_client()

    response = client.do_http_request(
        method="GET",
        resource_path=path,
        path_params={},
        query_params=query,
        header_params={"X-Language": "en_US"},
        body=None,
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
        "query": query,
        "data": data,
    }


ALLOWED_SERVICE_CODES = {"rds", "elb", "ecs", "evs"}


def call_get_service(api_path: str, query: dict, region: str = None, service_code: str = None):
    if service_code and service_code not in ALLOWED_SERVICE_CODES:
        raise ValueError(f"service_code '{service_code}' not allowed. Allowed: {ALLOWED_SERVICE_CODES}")

    if region is None:
        region = os.environ.get("HUAWEI_DEFAULT_REGION", "la-north-2")

    if service_code:
        endpoint_host = f"{service_code}.{region}.myhuaweicloud.com"
    else:
        endpoint_host = os.environ.get("HUAWEI_PRICING_ENDPOINT", "bss-intl.myhuaweicloud.com")

    client = create_client(endpoint_host=endpoint_host)

    response = client.do_http_request(
        method="GET",
        resource_path=api_path,
        path_params={},
        query_params=query,
        header_params={
            "X-Language": "en_US",
            "Content-Type": "application/json",
        },
        body=None,
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
        "path": api_path,
        "query": query,
        "region": region,
        "endpoint": endpoint_host,
        "data": data,
    }


def call_get_rds(api_path: str, query: dict, region: str = None):
    return call_get_service(api_path, query, region, service_code="rds")


def call_get_elb(api_path: str, query: dict, region: str = None):
    return call_get_service(api_path, query, region, service_code="elb")


def call_get_ecs(api_path: str, query: dict, region: str = None):
    return call_get_service(api_path, query, region, service_code="ecs")


def call_get_evs(api_path: str, query: dict, region: str = None):
    return call_get_service(api_path, query, region, service_code="evs")


def main():
    load_env_file()

    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["service-types", "resource-types", "service-resources", "usage-types", "measurements", "rds-flavors", "rds-storage-types", "elb-flavors", "elb-availability-zones", "ecs-flavors", "evs-volume-types"])
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--service-type-code", default="")
    parser.add_argument("--resource-type-code", default="")
    parser.add_argument("--rds-version", default=None)
    parser.add_argument("--ha-mode", default=None)
    parser.add_argument("--availability-zone", default=None)
    parser.add_argument("--volume-type", default=None)
    args = parser.parse_args()

    if args.operation == "service-types":
        result = call_get("/v2/products/service-types", {
            "limit": args.limit,
            "offset": args.offset,
        })

    elif args.operation == "resource-types":
        result = call_get("/v2/products/resource-types", {
            "limit": args.limit,
            "offset": args.offset,
        })

    elif args.operation == "service-resources":
        if not args.service_type_code:
            raise RuntimeError("--service-type-code is required for service-resources")

        result = call_get("/v2/products/service-resources", {
            "service_type_code": args.service_type_code,
            "limit": args.limit,
            "offset": args.offset,
        })

    elif args.operation == "usage-types":
        query = {
            "limit": args.limit,
            "offset": args.offset,
        }

        if args.service_type_code:
            query["service_type_code"] = args.service_type_code

        if args.resource_type_code:
            query["resource_type_code"] = args.resource_type_code

        result = call_get("/v2/products/usage-types", query)

    elif args.operation == "rds-flavors":
        project_id = os.environ.get("HUAWEI_PROJECT_ID", "")
        if not project_id:
            raise RuntimeError("HUAWEI_PROJECT_ID is required for rds-flavors")

        region = os.environ.get("HUAWEI_DEFAULT_REGION", "la-north-2")
        api_path = f"/v3/{project_id}/flavors/mysql"
        query = {"version_name": args.rds_version or "8.0"}

        result = call_get_rds(api_path, query, region)

    elif args.operation == "rds-storage-types":
        project_id = os.environ.get("HUAWEI_PROJECT_ID", "")
        if not project_id:
            raise RuntimeError("HUAWEI_PROJECT_ID is required for rds-storage-types")

        region = os.environ.get("HUAWEI_DEFAULT_REGION", "la-north-2")
        api_path = f"/v3/{project_id}/storage-type/mysql"
        query = {
            "version_name": args.rds_version or "8.0",
            "ha_mode": args.ha_mode or "single",
        }

        result = call_get_rds(api_path, query, region)

    elif args.operation == "elb-flavors":
        project_id = os.environ.get("HUAWEI_PROJECT_ID", "")
        if not project_id:
            raise RuntimeError("HUAWEI_PROJECT_ID is required for elb-flavors")

        region = os.environ.get("HUAWEI_DEFAULT_REGION", "la-north-2")
        api_path = f"/v3/{project_id}/elb/flavors"
        query = {}

        result = call_get_elb(api_path, query, region)

    elif args.operation == "elb-availability-zones":
        project_id = os.environ.get("HUAWEI_PROJECT_ID", "")
        if not project_id:
            raise RuntimeError("HUAWEI_PROJECT_ID is required for elb-availability-zones")

        region = os.environ.get("HUAWEI_DEFAULT_REGION", "la-north-2")
        api_path = f"/v3/{project_id}/elb/availability-zones"
        query = {}

        result = call_get_elb(api_path, query, region)

    elif args.operation == "ecs-flavors":
        project_id = os.environ.get("HUAWEI_PROJECT_ID", "")
        if not project_id:
            raise RuntimeError("HUAWEI_PROJECT_ID is required for ecs-flavors")

        region = os.environ.get("HUAWEI_DEFAULT_REGION", "la-north-2")
        api_path = f"/v1/{project_id}/cloudservers/flavors"
        query = {}

        if args.availability_zone:
            query["availability_zone"] = args.availability_zone

        result = call_get_ecs(api_path, query, region)

    elif args.operation == "evs-volume-types":
        project_id = os.environ.get("HUAWEI_PROJECT_ID", "")
        if not project_id:
            raise RuntimeError("HUAWEI_PROJECT_ID is required for evs-volume-types")

        region = os.environ.get("HUAWEI_DEFAULT_REGION", "la-north-2")
        api_path = f"/v2/{project_id}/types"
        query = {}

        result = call_get_evs(api_path, query, region)

        if args.availability_zone or args.volume_type:
            volume_types = result.get("data", {}).get("volume_types", [])
            filtered = []
            for vt in volume_types:
                if args.volume_type:
                    vt_name = vt.get("name", "")
                    if vt_name.lower() != args.volume_type.lower():
                        continue
                if args.availability_zone:
                    extra_specs = vt.get("extra_specs", {})
                    az_spec = extra_specs.get("RESKEY:availability_zones", "")
                    az_list = [az.strip() for az in az_spec.split(",") if az.strip()]
                    if args.availability_zone not in az_list:
                        continue
                    sold_out_spec = extra_specs.get("os-vendor-extended:sold_out_availability_zones", "")
                    sold_out_list = [az.strip() for az in sold_out_spec.split(",") if az.strip()]
                    if args.availability_zone in sold_out_list:
                        continue
                filtered.append(vt)
            result["data"]["volume_types"] = filtered
            result["filter_applied"] = {
                "availability_zone": args.availability_zone,
                "volume_type": args.volume_type,
            }

    else:
        result = call_get("/v2/bases/measurements", {
            "limit": args.limit,
            "offset": args.offset,
        })

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
