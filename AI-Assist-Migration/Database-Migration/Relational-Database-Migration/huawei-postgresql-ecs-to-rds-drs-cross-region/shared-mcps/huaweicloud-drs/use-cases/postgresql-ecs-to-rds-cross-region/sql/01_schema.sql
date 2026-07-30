-- ============================================================
-- 01_schema.sql - Demo database schema for PostgreSQL migration
-- ============================================================
-- Run on: Source ECS PostgreSQL (then replicated to target RDS via DRS)
-- ============================================================

CREATE TABLE IF NOT EXISTS demo_customers (
    customer_id   SERIAL PRIMARY KEY,
    customer_code VARCHAR(10) NOT NULL UNIQUE,
    full_name     VARCHAR(100) NOT NULL,
    email         VARCHAR(150) NOT NULL UNIQUE,
    country       VARCHAR(50) NOT NULL,
    created_at    TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS demo_products (
    product_id    SERIAL PRIMARY KEY,
    product_code  VARCHAR(10) NOT NULL UNIQUE,
    product_name  VARCHAR(100) NOT NULL,
    category      VARCHAR(50) NOT NULL,
    unit_price    NUMERIC(10,2) NOT NULL CHECK (unit_price > 0),
    created_at    TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS demo_orders (
    order_id      SERIAL PRIMARY KEY,
    order_code    VARCHAR(10) NOT NULL UNIQUE,
    customer_id   INTEGER NOT NULL REFERENCES demo_customers(customer_id),
    order_date    DATE NOT NULL,
    status        VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    created_at    TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS demo_order_items (
    order_item_id SERIAL PRIMARY KEY,
    order_id      INTEGER NOT NULL REFERENCES demo_orders(order_id),
    product_id    INTEGER NOT NULL REFERENCES demo_products(product_id),
    quantity      INTEGER NOT NULL CHECK (quantity > 0),
    unit_price    NUMERIC(10,2) NOT NULL,
    line_total    NUMERIC(12,2) GENERATED ALWAYS AS (quantity * unit_price) STORED,
    created_at    TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS demo_migration_audit (
    audit_id      SERIAL PRIMARY KEY,
    phase         VARCHAR(50) NOT NULL,
    status        VARCHAR(50) NOT NULL,
    note          TEXT,
    recorded_at   TIMESTAMP NOT NULL DEFAULT now()
);
