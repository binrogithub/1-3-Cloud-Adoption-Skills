-- ============================================================
-- 02_seed_data.sql - Deterministic demo data for migration validation
-- ============================================================
-- Run on: Source ECS PostgreSQL after schema creation
-- ============================================================

INSERT INTO demo_customers (customer_code, full_name, email, country, created_at) VALUES
('C001', 'Alice Martinez',    'alice.martinez@example.com',    'Chile',  '2026-01-15 09:00:00'),
('C002', 'Bob Zhang',         'bob.zhang@example.com',         'China',  '2026-01-16 10:30:00'),
('C003', 'Carla Silva',       'carla.silva@example.com',       'Brazil', '2026-01-17 11:15:00'),
('C004', 'David Kim',         'david.kim@example.com',         'Korea',  '2026-02-01 08:45:00'),
('C005', 'Elena Popov',       'elena.popov@example.com',       'Russia', '2026-02-05 14:00:00');

INSERT INTO demo_products (product_code, product_name, category, unit_price, created_at) VALUES
('P001', 'Cloud Server License',   'Software',  299.99, '2026-01-01 00:00:00'),
('P002', 'Storage Expansion Pack', 'Storage',   149.50, '2026-01-01 00:00:00'),
('P003', 'Network Accelerator',    'Network',   499.00, '2026-01-01 00:00:00'),
('P004', 'Security Suite',         'Security',  199.99, '2026-01-01 00:00:00'),
('P005', 'Database Backup Service','Database',   89.99, '2026-01-01 00:00:00');

INSERT INTO demo_orders (order_code, customer_id, order_date, status, created_at) VALUES
('ORD001', 1, '2026-02-10', 'COMPLETED', '2026-02-10 10:00:00'),
('ORD002', 2, '2026-02-12', 'COMPLETED', '2026-02-12 11:30:00'),
('ORD003', 1, '2026-02-15', 'SHIPPED',   '2026-02-15 09:00:00'),
('ORD004', 3, '2026-02-18', 'PENDING',   '2026-02-18 14:00:00'),
('ORD005', 4, '2026-02-20', 'COMPLETED', '2026-02-20 16:00:00');

INSERT INTO demo_order_items (order_id, product_id, quantity, unit_price, created_at) VALUES
(1, 1, 2, 299.99, '2026-02-10 10:00:00'),
(1, 2, 1, 149.50, '2026-02-10 10:00:00'),
(2, 3, 1, 499.00, '2026-02-12 11:30:00'),
(2, 5, 3,  89.99, '2026-02-12 11:30:00'),
(3, 4, 2, 199.99, '2026-02-15 09:00:00'),
(3, 1, 1, 299.99, '2026-02-15 09:00:00'),
(4, 2, 2, 149.50, '2026-02-18 14:00:00'),
(5, 3, 1, 499.00, '2026-02-20 16:00:00'),
(5, 5, 1,  89.99, '2026-02-20 16:00:00');

INSERT INTO demo_migration_audit (phase, status, note, recorded_at) VALUES
('INITIAL_LOAD', 'READY', 'Source data loaded and ready for DRS full + incremental migration', '2026-07-07 12:00:00');
