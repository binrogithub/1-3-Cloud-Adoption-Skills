#!/usr/bin/env python3
"""Render app.properties for the bundled Java demo.

Examples:
  python3 render_app_properties.py --kafka-bootstrap-servers broker1:9092,broker2:9092 --db-url jdbc:opengauss://db:8000/postgres --db-user app --db-password secret
  python3 render_app_properties.py --security-protocol SASL_SSL --sasl-mechanism SCRAM-SHA-512 --kafka-username user --kafka-password pass --truststore-location /path/client.truststore.jks --db-url jdbc:opengauss://db:8000/postgres --db-user app --db-password secret
"""

from __future__ import annotations

import argparse
import sys


def build_properties(args: argparse.Namespace) -> str:
    lines = [
        f"app.topic.request={args.topic_request}",
        f"app.topic.processed={args.topic_processed}",
        f"app.consumer.group={args.consumer_group}",
        "",
        f"kafka.bootstrap.servers={args.kafka_bootstrap_servers}",
    ]

    if args.security_protocol:
        lines.append(f"kafka.security.protocol={args.security_protocol}")
    if args.sasl_mechanism:
        lines.append(f"kafka.sasl.mechanism={args.sasl_mechanism}")
    if args.kafka_username or args.kafka_password:
        if not (args.kafka_username and args.kafka_password and args.sasl_mechanism):
            raise ValueError("Kafka username/password rendering requires sasl mechanism and both credentials.")
        if args.sasl_mechanism == "PLAIN":
            login_module = "org.apache.kafka.common.security.plain.PlainLoginModule"
        else:
            login_module = "org.apache.kafka.common.security.scram.ScramLoginModule"
        lines.append(
            "kafka.sasl.jaas.config="
            f"{login_module} required username=\"{args.kafka_username}\" password=\"{args.kafka_password}\";"
        )
    if args.truststore_location:
        lines.append(f"kafka.ssl.truststore.location={args.truststore_location}")
    if args.truststore_password:
        lines.append(f"kafka.ssl.truststore.password={args.truststore_password}")
    if args.ssl_endpoint_identification_algorithm is not None:
        lines.append(
            f"kafka.ssl.endpoint.identification.algorithm={args.ssl_endpoint_identification_algorithm}"
        )

    lines.extend(
        [
            "",
            f"db.driver={args.db_driver}",
            f"db.url={args.db_url}",
            f"db.user={args.db_user}",
            f"db.password={args.db_password}",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render app.properties for Kafka + GaussDB Java demo.")
    parser.add_argument("--topic-request", default="trade.request")
    parser.add_argument("--topic-processed", default="trade.processed")
    parser.add_argument("--consumer-group", default="trading-demo-consumer")
    parser.add_argument("--kafka-bootstrap-servers", required=True)
    parser.add_argument("--security-protocol", default="")
    parser.add_argument("--sasl-mechanism", default="")
    parser.add_argument("--kafka-username", default="")
    parser.add_argument("--kafka-password", default="")
    parser.add_argument("--truststore-location", default="")
    parser.add_argument("--truststore-password", default="")
    parser.add_argument("--ssl-endpoint-identification-algorithm", default="")
    parser.add_argument("--db-driver", default="com.huawei.opengauss.jdbc.Driver")
    parser.add_argument("--db-url", required=True)
    parser.add_argument("--db-user", required=True)
    parser.add_argument("--db-password", required=True)
    args = parser.parse_args()

    try:
        sys.stdout.write(build_properties(args))
        return 0
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
