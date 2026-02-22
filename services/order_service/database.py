# ═══════════════════════════════════════════════════════════════════════════════
# database.py — Servicio de Pedidos
# Base de datos EXCLUSIVA de este servicio. No compartida con nadie.
# ═══════════════════════════════════════════════════════════════════════════════

import sqlite3

DB_PATH = "orders.db"


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                restaurant_id INTEGER NOT NULL,
                customer_name TEXT    NOT NULL,
                status        TEXT    NOT NULL DEFAULT 'pending',
                total         REAL    NOT NULL DEFAULT 0,
                created_at    TEXT    DEFAULT (datetime('now')),
                updated_at    TEXT    DEFAULT (datetime('now'))
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id     INTEGER NOT NULL,
                menu_item_id INTEGER NOT NULL,
                item_name    TEXT    NOT NULL,
                unit_price   REAL    NOT NULL,
                quantity     INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (order_id) REFERENCES orders(id)
            )
        """)

        conn.commit()