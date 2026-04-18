# Huawei Cloud Deploy

Use this reference when the user asks for a deployable Huawei Cloud plan rather than only logical architecture.

## Recommended topology

- Deploy DMS for Kafka and GaussDB in the same region.
- Deploy the Java application on ECS or CCE in the same VPC whenever possible.
- Prefer private connectivity first.
- Prefer encrypted Kafka access when enabled on the instance.

## DMS for Kafka checklist

Collect these fields from the console:
- bootstrap servers
- network mode in use
- topic names
- authentication mode
- username and password if SASL is enabled
- truststore or certificate material if SASL_SSL is enabled

Official Huawei docs note:
- DMS for Kafka is compatible with open-source Kafka clients.
- Same-region same-VPC clients use private network addresses.
- Cross-VPC private access may require VPC peering or a VPC endpoint.
- Public access uses different addresses and different ports from private access.

Official references:
- DMS for Kafka overview: https://support.huaweicloud.com/eu/devg-kafka/Kafka-summary.html
- Kafka public access: https://support.huaweicloud.com/intl/en-us/usermanual-kafka/kafka-ug-0319001.html

## Kafka security defaults

For generic enterprise deployments:
- prefer private network access
- prefer SASL_SSL if the instance is configured for it
- lock security groups to app node CIDRs only
- avoid public exposure unless there is a concrete requirement

Official Huawei compliance material also signals that public access should be treated cautiously.

## GaussDB checklist

Collect these fields from the console:
- writer endpoint
- port
- database name
- username
- password
- SSL requirement
- engine family and driver guidance

Official Huawei docs note:
- Java should use the GaussDB-compatible JDBC path with `jdbc:opengauss://...`
- driver class is `com.huawei.opengauss.jdbc.Driver` in the official JDBC guide
- properties-based credential passing is safer than embedding secrets in the URL

Official references:
- GaussDB JDBC connection guide: https://support.huaweicloud.com/intl/en-us/distributed-devg-v3-gaussdb/gaussdb-12-0059.html
- GaussDB application overview: https://support.huaweicloud.com/distributed-devg-v3-gaussdb/gaussdb-12-1708.html

## Demo sizing defaults

For a first demo:
- Kafka topics: 3 to 6 partitions
- Consumer instances: 1
- Consumer threads: match partition count only if ordering rules allow it
- Batch size: start small and measure
- GaussDB schema: single schema dedicated to the demo

## Deployment sequence

1. Create Kafka and GaussDB in the same region and VPC.
2. Create a security group that allows only app-to-service traffic.
3. Create a dedicated application user and database/schema.
4. Create Kafka topics.
5. Copy the bundled Java demo.
6. Fill in `app.properties`.
7. Run `bootstrap-db`.
8. Run `produce-demo`.
9. Run `consume`.
10. Validate DB state and Kafka lag.
