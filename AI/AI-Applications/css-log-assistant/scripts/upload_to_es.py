import argparse
import json
import math
from datetime import datetime
from pathlib import Path

from elasticsearch import Elasticsearch, helpers


def _parse_timestamp(ts: str) -> datetime:
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts)


def _index_name(index_prefix: str, timestamp: str) -> str:
    dt = _parse_timestamp(timestamp)
    return f"{index_prefix}-{dt:%Y.%m.%d}"


def _put_index_template(client: Elasticsearch, template_name: str, index_pattern: str, shards: int, replicas: int):
    body = {
        "index_patterns": [index_pattern],
        "settings": {
            "number_of_shards": shards,
            "number_of_replicas": replicas,
        },
        "mappings": {
            "dynamic": "true",
            "properties": {
                "timestamp": {"type": "date"},
                "order_id": {"type": "keyword"},
                "country": {"type": "keyword"},
                "country_code": {"type": "keyword"},
                "city": {"type": "keyword"},
                "restaurant_id": {"type": "keyword"},
                "restaurant_name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "customer_id": {"type": "keyword"},
                "driver_id": {"type": "keyword"},
                "order_status": {"type": "keyword"},
                "total_amount": {"type": "double"},
                "currency": {"type": "keyword"},
                "items_count": {"type": "integer"},
                "delivery_time_minutes": {"type": "integer"},
                "distance_km": {"type": "double"},
                "payment_method": {"type": "keyword"},
                "platform": {"type": "keyword"},
                "error_code": {"type": "keyword"},
                "error_message": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            },
        },
    }
    client.indices.put_template(name=template_name, body=body)


def _iter_actions(index_prefix: str, docs):
    for doc in docs:
        index = _index_name(index_prefix, doc["timestamp"])
        doc_id = doc.get("order_id")
        action = {"_index": index, "_source": doc}
        if doc_id:
            action["_id"] = doc_id
        yield action


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--es-url", required=True)
    parser.add_argument("--username", default=None)
    parser.add_argument("--password", default=None)
    parser.add_argument("--insecure", action="store_true")
    parser.add_argument("--ca-cert", default=None)
    parser.add_argument("--input-dir", default="output")
    parser.add_argument("--index-prefix", default="food_delivery_logs")
    parser.add_argument("--template-name", default="food_delivery_logs_template")
    parser.add_argument("--shards", type=int, default=3)
    parser.add_argument("--replicas", type=int, default=1)
    parser.add_argument("--chunk-size", type=int, default=2000)
    parser.add_argument("--request-timeout", type=int, default=120)
    args = parser.parse_args()

    http_auth = None
    if args.username and args.password:
        http_auth = (args.username, args.password)

    verify_certs = not args.insecure
    client = Elasticsearch(
        [args.es_url],
        http_auth=http_auth,
        verify_certs=verify_certs,
        ca_certs=args.ca_cert,
        request_timeout=args.request_timeout,
    )

    index_pattern = f"{args.index_prefix}-*"
    _put_index_template(
        client=client,
        template_name=args.template_name,
        index_pattern=index_pattern,
        shards=args.shards,
        replicas=args.replicas,
    )

    input_path = Path(args.input_dir)
    files = sorted(input_path.glob("logs_batch_*.json"))
    if not files:
        raise SystemExit(f"No logs_batch_*.json found under: {input_path.resolve()}")

    total_files = len(files)
    for i, file_path in enumerate(files, start=1):
        with open(file_path, "r", encoding="utf-8") as f:
            docs = json.load(f)

        total_docs = len(docs)
        batches = max(1, math.ceil(total_docs / args.chunk_size))
        print(f"[{i}/{total_files}] {file_path.name}: {total_docs:,} docs ({batches} chunks)")

        actions = _iter_actions(args.index_prefix, docs)
        helpers.bulk(
            client,
            actions,
            chunk_size=args.chunk_size,
            request_timeout=args.request_timeout,
        )

    print("Done")


if __name__ == "__main__":
    main()

