#!/usr/bin/env python3
"""Estimate Kafka partitions and starting consumer/database settings.

Example:
  python3 topic_plan.py --target-tps 12000 --avg-handler-ms 3 --payload-kb 4
"""

from __future__ import annotations

import argparse
import json
import math


def main() -> int:
    parser = argparse.ArgumentParser(description="Estimate topic sizing and first-pass tuning values.")
    parser.add_argument("--target-tps", type=float, required=True)
    parser.add_argument("--avg-handler-ms", type=float, required=True)
    parser.add_argument("--payload-kb", type=float, default=4.0)
    parser.add_argument("--utilization-target", type=float, default=0.7)
    parser.add_argument("--replication-factor", type=int, default=3)
    args = parser.parse_args()

    partitions = math.ceil(
        args.target_tps * args.avg_handler_ms / 1000.0 / args.utilization_target
    )

    if partitions <= 6:
        db_batch_size = 500
        max_poll_records = 500
    elif partitions <= 24:
        db_batch_size = 1000
        max_poll_records = 1000
    else:
        db_batch_size = 2000
        max_poll_records = 2000

    if args.payload_kb >= 32:
        compression = "zstd"
        linger_ms = 20
    else:
        compression = "lz4"
        linger_ms = 10

    plan = {
        "inputs": {
            "target_tps": args.target_tps,
            "avg_handler_ms": args.avg_handler_ms,
            "payload_kb": args.payload_kb,
            "utilization_target": args.utilization_target,
            "replication_factor": args.replication_factor,
        },
        "recommendation": {
            "request_topic_partitions": partitions,
            "consumer_threads": partitions,
            "minimum_brokers_for_rf": args.replication_factor,
            "producer": {
                "acks": "all",
                "enable.idempotence": True,
                "compression.type": compression,
                "linger.ms": linger_ms,
            },
            "consumer": {
                "enable.auto.commit": False,
                "max.poll.records": max_poll_records,
            },
            "database": {
                "starting_batch_size": db_batch_size,
                "connection_pool_min": min(max(4, partitions // 4), 16),
                "connection_pool_max": min(max(8, partitions), 64),
            },
        },
        "notes": [
            "This is a first-pass estimate, not a capacity guarantee.",
            "Keep the partition key aligned with the business conflict key.",
            "Validate with Kafka-only, DB-only, and end-to-end benchmarks.",
        ],
    }

    print(json.dumps(plan, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
