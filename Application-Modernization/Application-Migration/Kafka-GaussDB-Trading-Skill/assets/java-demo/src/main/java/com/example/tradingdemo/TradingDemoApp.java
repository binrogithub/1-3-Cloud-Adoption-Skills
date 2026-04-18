package com.example.tradingdemo;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.clients.consumer.ConsumerRecords;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.apache.kafka.common.serialization.StringSerializer;

import java.io.FileInputStream;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.Statement;
import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.Properties;
import java.util.UUID;

public final class TradingDemoApp {
    private static final ObjectMapper MAPPER = new ObjectMapper();

    public static void main(String[] args) throws Exception {
        if (args.length < 2) {
            System.err.println("Usage: TradingDemoApp <bootstrap-db|produce-demo|consume> <app.properties> [count]");
            System.exit(1);
        }

        String mode = args[0];
        Properties app = loadProps(args[1]);

        switch (mode) {
            case "bootstrap-db" -> bootstrapDb(app);
            case "produce-demo" -> produceDemo(app, args.length >= 3 ? Integer.parseInt(args[2]) : 1000);
            case "consume" -> consume(app);
            default -> throw new IllegalArgumentException("Unknown mode: " + mode);
        }
    }

    private static Properties loadProps(String path) throws Exception {
        Properties props = new Properties();
        try (FileInputStream in = new FileInputStream(path)) {
            props.load(in);
        }
        return props;
    }

    private static Connection openDb(Properties app) throws Exception {
        Class.forName(app.getProperty("db.driver"));
        return DriverManager.getConnection(
                app.getProperty("db.url"),
                app.getProperty("db.user"),
                app.getProperty("db.password"));
    }

    private static Properties producerProps(Properties app) {
        Properties p = new Properties();
        p.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, app.getProperty("kafka.bootstrap.servers"));
        p.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        p.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        p.put(ProducerConfig.ACKS_CONFIG, "all");
        p.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, "true");
        p.put(ProducerConfig.COMPRESSION_TYPE_CONFIG, "lz4");
        p.put(ProducerConfig.LINGER_MS_CONFIG, "20");
        copyOptionalKafkaSecurity(app, p);
        return p;
    }

    private static Properties consumerProps(Properties app) {
        Properties p = new Properties();
        p.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, app.getProperty("kafka.bootstrap.servers"));
        p.put(ConsumerConfig.GROUP_ID_CONFIG, app.getProperty("app.consumer.group"));
        p.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
        p.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
        p.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG, "false");
        p.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest");
        p.put(ConsumerConfig.MAX_POLL_RECORDS_CONFIG, "500");
        copyOptionalKafkaSecurity(app, p);
        return p;
    }

    private static void copyOptionalKafkaSecurity(Properties app, Properties target) {
        for (String key : new String[]{
                "kafka.security.protocol",
                "kafka.sasl.mechanism",
                "kafka.sasl.jaas.config",
                "kafka.ssl.truststore.location",
                "kafka.ssl.truststore.password",
                "kafka.ssl.endpoint.identification.algorithm"
        }) {
            String value = app.getProperty(key);
            if (value != null && !value.isBlank()) {
                target.put(key.substring("kafka.".length()), value);
            }
        }
    }

    private static void bootstrapDb(Properties app) throws Exception {
        try (Connection conn = openDb(app); Statement st = conn.createStatement()) {
            st.executeUpdate("""
                    CREATE TABLE IF NOT EXISTS trade_inbox (
                        event_id VARCHAR(64) PRIMARY KEY,
                        trace_id VARCHAR(64) NOT NULL,
                        aggregate_id VARCHAR(64) NOT NULL,
                        event_type VARCHAR(64) NOT NULL,
                        payload_json TEXT NOT NULL,
                        status VARCHAR(32) NOT NULL,
                        error_code VARCHAR(64),
                        error_message TEXT,
                        received_at TIMESTAMP NOT NULL,
                        processed_at TIMESTAMP
                    )
                    """);
            st.executeUpdate("""
                    CREATE TABLE IF NOT EXISTS trade_state (
                        aggregate_id VARCHAR(64) PRIMARY KEY,
                        account_id VARCHAR(64) NOT NULL,
                        state VARCHAR(32) NOT NULL,
                        amount DECIMAL(18,2) NOT NULL,
                        currency VARCHAR(8) NOT NULL,
                        version INTEGER NOT NULL,
                        updated_at TIMESTAMP NOT NULL
                    )
                    """);
            st.executeUpdate("""
                    CREATE TABLE IF NOT EXISTS trade_outbox (
                        id BIGSERIAL PRIMARY KEY,
                        event_id VARCHAR(64) UNIQUE NOT NULL,
                        aggregate_id VARCHAR(64) NOT NULL,
                        topic_name VARCHAR(128) NOT NULL,
                        payload_json TEXT NOT NULL,
                        publish_status VARCHAR(32) NOT NULL,
                        created_at TIMESTAMP NOT NULL,
                        published_at TIMESTAMP
                    )
                    """);
            st.executeUpdate("""
                    CREATE TABLE IF NOT EXISTS trade_audit (
                        id BIGSERIAL PRIMARY KEY,
                        event_id VARCHAR(64) NOT NULL,
                        trace_id VARCHAR(64) NOT NULL,
                        aggregate_id VARCHAR(64) NOT NULL,
                        action VARCHAR(64) NOT NULL,
                        detail_json TEXT NOT NULL,
                        created_at TIMESTAMP NOT NULL
                    )
                    """);
        }
        System.out.println("database bootstrap complete");
    }

    private static void produceDemo(Properties app, int count) throws Exception {
        try (KafkaProducer<String, String> producer = new KafkaProducer<>(producerProps(app))) {
            for (int i = 0; i < count; i++) {
                String accountId = "acct-" + (i % 64);
                String aggregateId = "trade-" + i;
                String eventId = UUID.randomUUID().toString().replace("-", "");
                String traceId = UUID.randomUUID().toString().replace("-", "");
                Map<String, Object> payload = Map.of(
                        "event_id", eventId,
                        "trace_id", traceId,
                        "aggregate_id", aggregateId,
                        "account_id", accountId,
                        "event_type", "trade.requested",
                        "amount", BigDecimal.valueOf((i % 5000) + 1),
                        "currency", "CNY",
                        "event_time", Instant.now().toString(),
                        "schema_version", 1
                );
                String json = MAPPER.writeValueAsString(payload);
                producer.send(new ProducerRecord<>(app.getProperty("app.topic.request"), accountId, json)).get();
            }
        }
        System.out.println("produced demo events: " + count);
    }

    private static void consume(Properties app) throws Exception {
        try (KafkaConsumer<String, String> consumer = new KafkaConsumer<>(consumerProps(app));
             Connection conn = openDb(app)) {
            conn.setAutoCommit(false);
            consumer.subscribe(java.util.List.of(app.getProperty("app.topic.request")));

            while (true) {
                ConsumerRecords<String, String> records = consumer.poll(Duration.ofSeconds(1));
                for (ConsumerRecord<String, String> record : records) {
                    processOne(app, conn, record);
                }
                if (!records.isEmpty()) {
                    consumer.commitSync();
                }
            }
        }
    }

    private static void processOne(Properties app, Connection conn, ConsumerRecord<String, String> record) throws Exception {
        Map<?, ?> payload = MAPPER.readValue(record.value().getBytes(StandardCharsets.UTF_8), Map.class);
        String eventId = payload.get("event_id").toString();
        String traceId = payload.get("trace_id").toString();
        String aggregateId = payload.get("aggregate_id").toString();
        String accountId = payload.get("account_id").toString();
        String amountText = payload.get("amount").toString();
        String payloadJson = record.value();
        Instant now = Instant.now();

        try {
            if (existsInbox(conn, eventId)) {
                conn.rollback();
                return;
            }

            try (PreparedStatement ps = conn.prepareStatement("""
                    INSERT INTO trade_inbox(event_id, trace_id, aggregate_id, event_type, payload_json, status, received_at)
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """)) {
                ps.setString(1, eventId);
                ps.setString(2, traceId);
                ps.setString(3, aggregateId);
                ps.setString(4, "trade.requested");
                ps.setString(5, payloadJson);
                ps.setString(6, "RECEIVED");
                ps.executeUpdate();
            }

            try (PreparedStatement ps = conn.prepareStatement("""
                    MERGE INTO trade_state t
                    USING (SELECT ? AS aggregate_id, ? AS account_id, ? AS state, ? AS amount, ? AS currency, ? AS version) s
                    ON (t.aggregate_id = s.aggregate_id)
                    WHEN MATCHED THEN
                      UPDATE SET account_id = s.account_id, state = s.state, amount = s.amount, currency = s.currency,
                                 version = t.version + 1, updated_at = CURRENT_TIMESTAMP
                    WHEN NOT MATCHED THEN
                      INSERT (aggregate_id, account_id, state, amount, currency, version, updated_at)
                      VALUES (s.aggregate_id, s.account_id, s.state, s.amount, s.currency, s.version, CURRENT_TIMESTAMP)
                    """)) {
                ps.setString(1, aggregateId);
                ps.setString(2, accountId);
                ps.setString(3, "BOOKED");
                ps.setBigDecimal(4, new BigDecimal(amountText));
                ps.setString(5, payload.get("currency").toString());
                ps.setInt(6, 1);
                ps.executeUpdate();
            }

            String outboxJson = MAPPER.writeValueAsString(Map.of(
                    "event_id", eventId,
                    "trace_id", traceId,
                    "aggregate_id", aggregateId,
                    "event_type", "trade.processed",
                    "processed_at", now.toString()
            ));

            try (PreparedStatement ps = conn.prepareStatement("""
                    INSERT INTO trade_outbox(event_id, aggregate_id, topic_name, payload_json, publish_status, created_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """)) {
                ps.setString(1, eventId);
                ps.setString(2, aggregateId);
                ps.setString(3, app.getProperty("app.topic.processed"));
                ps.setString(4, outboxJson);
                ps.setString(5, "NEW");
                ps.executeUpdate();
            }

            try (PreparedStatement ps = conn.prepareStatement("""
                    INSERT INTO trade_audit(event_id, trace_id, aggregate_id, action, detail_json, created_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """)) {
                ps.setString(1, eventId);
                ps.setString(2, traceId);
                ps.setString(3, aggregateId);
                ps.setString(4, "CONSUMED");
                ps.setString(5, payloadJson);
                ps.executeUpdate();
            }

            try (PreparedStatement ps = conn.prepareStatement("""
                    UPDATE trade_inbox SET status = ?, processed_at = CURRENT_TIMESTAMP
                    WHERE event_id = ?
                    """)) {
                ps.setString(1, "PROCESSED");
                ps.setString(2, eventId);
                ps.executeUpdate();
            }

            conn.commit();
        } catch (Exception ex) {
            conn.rollback();
            try (PreparedStatement ps = conn.prepareStatement("""
                    UPDATE trade_inbox SET status = ?, error_code = ?, error_message = ?, processed_at = CURRENT_TIMESTAMP
                    WHERE event_id = ?
                    """)) {
                ps.setString(1, "FAILED");
                ps.setString(2, ex.getClass().getSimpleName());
                ps.setString(3, ex.getMessage());
                ps.setString(4, eventId);
                ps.executeUpdate();
                conn.commit();
            } catch (Exception ignored) {
                conn.rollback();
            }
            throw ex;
        }
    }

    private static boolean existsInbox(Connection conn, String eventId) throws Exception {
        try (PreparedStatement ps = conn.prepareStatement("SELECT 1 FROM trade_inbox WHERE event_id = ?")) {
            ps.setString(1, eventId);
            try (ResultSet rs = ps.executeQuery()) {
                return rs.next();
            }
        }
    }
}
