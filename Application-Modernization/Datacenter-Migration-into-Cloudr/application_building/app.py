import os
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

import pymysql
from flask import Flask, jsonify, render_template, request
from pymysql.cursors import DictCursor


app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _db_ssl_config() -> dict | None:
    if _env_bool("DB_SSL_DISABLED", False):
        return None

    ssl_ca = (os.getenv("DB_SSL_CA") or "").strip()
    ssl_cert = (os.getenv("DB_SSL_CERT") or "").strip()
    ssl_key = (os.getenv("DB_SSL_KEY") or "").strip()

    if not (ssl_ca or ssl_cert or ssl_key):
        return None

    ssl_options = {}
    if ssl_ca:
        ssl_options["ca"] = ssl_ca
    if ssl_cert:
        ssl_options["cert"] = ssl_cert
    if ssl_key:
        ssl_options["key"] = ssl_key
    ssl_options["check_hostname"] = _env_bool("DB_SSL_VERIFY_IDENTITY", False)

    return ssl_options


def db_config() -> dict:
    config = {
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER", "canteen_user"),
        "password": os.getenv("DB_PASSWORD", "canteen_pass"),
        "database": os.getenv("DB_NAME", "canteen_ordering"),
        "cursorclass": DictCursor,
        "autocommit": False,
        "charset": "utf8mb4",
        "connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "10")),
    }

    ssl_options = _db_ssl_config()
    if ssl_options:
        config["ssl"] = ssl_options

    return config


def get_conn():
    return pymysql.connect(**db_config())


SCHEMA_SQL = [
    """
    CREATE TABLE IF NOT EXISTS menu_items (
      id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
      name VARCHAR(128) NOT NULL,
      category VARCHAR(64) NOT NULL,
      price DECIMAL(10,2) NOT NULL,
      is_available TINYINT(1) NOT NULL DEFAULT 1,
      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    """
    CREATE TABLE IF NOT EXISTS orders (
      id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
      customer_name VARCHAR(64) NOT NULL,
      customer_phone VARCHAR(32) NOT NULL,
      pickup_time VARCHAR(32) NULL,
      notes VARCHAR(255) NULL,
      status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
      total_amount DECIMAL(10,2) NOT NULL,
      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    """
    CREATE TABLE IF NOT EXISTS order_items (
      id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
      order_id BIGINT UNSIGNED NOT NULL,
      menu_item_id BIGINT UNSIGNED NOT NULL,
      quantity INT NOT NULL,
      unit_price DECIMAL(10,2) NOT NULL,
      line_total DECIMAL(10,2) NOT NULL,
      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (id),
      KEY idx_order_id (order_id),
      KEY idx_menu_item_id (menu_item_id),
      CONSTRAINT fk_order_items_order FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
      CONSTRAINT fk_order_items_menu_item FOREIGN KEY (menu_item_id) REFERENCES menu_items(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
]

SEED_MENU = [
    ("红烧牛肉面", "主食", Decimal("18.00")),
    ("扬州炒饭", "主食", Decimal("16.00")),
    ("宫保鸡丁套餐", "套餐", Decimal("22.00")),
    ("番茄鸡蛋盖饭", "主食", Decimal("14.00")),
    ("清炒时蔬", "小菜", Decimal("10.00")),
    ("酸辣土豆丝", "小菜", Decimal("8.00")),
    ("紫菜蛋花汤", "汤品", Decimal("6.00")),
    ("可乐", "饮品", Decimal("4.00")),
    ("冰红茶", "饮品", Decimal("4.00")),
]


def decimal_2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def init_db() -> None:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for sql in SCHEMA_SQL:
                cur.execute(sql)

            cur.execute("SELECT COUNT(1) AS c FROM menu_items")
            count = cur.fetchone()["c"]
            if count == 0:
                cur.executemany(
                    "INSERT INTO menu_items (name, category, price) VALUES (%s, %s, %s)",
                    SEED_MENU,
                )
        conn.commit()
    finally:
        conn.close()


@app.get("/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "service": "canteen-ordering",
            "time": datetime.utcnow().isoformat() + "Z",
        }
    )


@app.get("/")
def index():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, category, price
                FROM menu_items
                WHERE is_available = 1
                ORDER BY category, id
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    grouped = {}
    for row in rows:
        grouped.setdefault(row["category"], []).append(row)
    return render_template("index.html", grouped_menu=grouped)


@app.get("/admin/orders")
def admin_orders():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, customer_name, customer_phone, pickup_time, notes, status, total_amount, created_at
                FROM orders
                ORDER BY id DESC
                LIMIT 100
                """
            )
            orders = cur.fetchall()

            items = []
            order_ids = [row["id"] for row in orders]
            if order_ids:
                placeholders = ",".join(["%s"] * len(order_ids))
                cur.execute(
                    f"""
                    SELECT oi.order_id, mi.name AS menu_name, oi.quantity, oi.unit_price, oi.line_total
                    FROM order_items oi
                    JOIN menu_items mi ON oi.menu_item_id = mi.id
                    WHERE oi.order_id IN ({placeholders})
                    ORDER BY oi.order_id DESC, oi.id ASC
                    """,
                    order_ids,
                )
                items = cur.fetchall()
    finally:
        conn.close()

    item_map = {}
    for item in items:
        item_map.setdefault(item["order_id"], []).append(item)

    for order in orders:
        order["items"] = item_map.get(order["id"], [])

    return render_template("admin.html", orders=orders)


@app.get("/api/menu")
def api_menu():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, category, price, is_available FROM menu_items ORDER BY category, id"
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify(rows)


@app.post("/api/orders")
def create_order():
    data = request.get_json(silent=True) or {}
    customer_name = (data.get("customer_name") or "").strip()
    customer_phone = (data.get("customer_phone") or "").strip()
    pickup_time = (data.get("pickup_time") or "").strip()
    notes = (data.get("notes") or "").strip()
    items = data.get("items") or []

    if not customer_name:
        return jsonify({"error": "请填写姓名"}), 400
    if not customer_phone:
        return jsonify({"error": "请填写手机号"}), 400
    if not isinstance(items, list) or len(items) == 0:
        return jsonify({"error": "请至少选择一项菜品"}), 400

    normalized = {}
    for item in items:
        try:
            menu_item_id = int(item.get("menu_item_id"))
            qty = int(item.get("quantity"))
        except (TypeError, ValueError):
            continue
        if menu_item_id > 0 and qty > 0:
            normalized[menu_item_id] = normalized.get(menu_item_id, 0) + qty

    if not normalized:
        return jsonify({"error": "数量必须大于 0"}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(normalized))
            cur.execute(
                f"SELECT id, name, price, is_available FROM menu_items WHERE id IN ({placeholders})",
                list(normalized.keys()),
            )
            menu_rows = cur.fetchall()

            menu_map = {row["id"]: row for row in menu_rows if row["is_available"] == 1}
            if len(menu_map) != len(normalized):
                return jsonify({"error": "部分菜品不可用，请刷新页面后重试"}), 400

            total = Decimal("0.00")
            line_items = []
            for menu_id, qty in normalized.items():
                unit_price = Decimal(str(menu_map[menu_id]["price"]))
                line_total = decimal_2(unit_price * qty)
                total = decimal_2(total + line_total)
                line_items.append((menu_id, qty, unit_price, line_total))

            cur.execute(
                """
                INSERT INTO orders (customer_name, customer_phone, pickup_time, notes, status, total_amount)
                VALUES (%s, %s, %s, %s, 'PENDING', %s)
                """,
                (customer_name, customer_phone, pickup_time or None, notes or None, total),
            )
            order_id = cur.lastrowid

            cur.executemany(
                """
                INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price, line_total)
                VALUES (%s, %s, %s, %s, %s)
                """,
                [(order_id, m_id, qty, unit_price, line_total) for m_id, qty, unit_price, line_total in line_items],
            )

        conn.commit()
        return jsonify(
            {
                "message": "下单成功",
                "order_id": order_id,
                "total_amount": float(total),
            }
        )
    except Exception:
        conn.rollback()
        app.logger.exception("create order failed")
        return jsonify({"error": "下单失败，请稍后重试"}), 500
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8000, debug=False)
