# Java Demo

The bundled Java demo lives in `assets/java-demo/`.

## What it does

- `bootstrap-db`: creates a generic schema for inbox, state, outbox, and audit tables
- `produce-demo`: creates synthetic trade events and writes them to Kafka
- `consume`: reads Kafka, applies idempotent DB writes, and commits offsets only after DB commit

## Why the demo is conservative

- It uses plain Java instead of a full framework.
- It uses `java.sql.*` APIs so the code compiles without bundling a database jar in source control.
- At runtime, add the Huawei GaussDB JDBC jar to the classpath.

## Files

- `pom.xml`
- `app.properties.example`
- `src/main/java/com/example/tradingdemo/TradingDemoApp.java`

## Build

1. Copy `assets/java-demo/` into your project workspace.
2. Put the GaussDB JDBC jar in `lib/` if you use the official driver path.
3. Copy `app.properties.example` to `app.properties`.
4. Fill in Kafka bootstrap servers and database values.
5. Build with Maven.

Example:

```bash
mvn -q -DskipTests package
```

## Run

```bash
java -cp "target/trading-demo-1.0.0.jar:lib/*" com.example.tradingdemo.TradingDemoApp bootstrap-db app.properties
java -cp "target/trading-demo-1.0.0.jar:lib/*" com.example.tradingdemo.TradingDemoApp produce-demo app.properties 1000
java -cp "target/trading-demo-1.0.0.jar:lib/*" com.example.tradingdemo.TradingDemoApp consume app.properties
```

## Config guidance

For Kafka:
- set `kafka.bootstrap.servers`
- if auth is enabled, set `kafka.security.protocol`, `kafka.sasl.mechanism`, and `kafka.sasl.jaas.config`
- if SSL truststore is required, set `kafka.ssl.truststore.location` and `kafka.ssl.truststore.password`

For GaussDB:
- set `db.url` to `jdbc:opengauss://host:port/database`
- set `db.user`
- set `db.password`
- set `db.driver` to `com.huawei.opengauss.jdbc.Driver`

The DMS for Kafka official guide includes example SASL and truststore properties, and the GaussDB official guide includes the JDBC driver class and URL format.
