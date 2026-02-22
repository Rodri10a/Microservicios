# ═══════════════════════════════════════════════════════════════════════════════
# database.py — Servicio de Delivery
# Base de datos EXCLUSIVA de este servicio.
# ═══════════════════════════════════════════════════════════════════════════════

import sqlite3

DB_PATH = "delivery.db"


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS deliveries (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id      INTEGER NOT NULL UNIQUE,
                customer_name TEXT    NOT NULL,
                driver_name   TEXT,
                status        TEXT    NOT NULL DEFAULT 'assigned',
                address       TEXT    NOT NULL,
                created_at    TEXT    DEFAULT (datetime('now')),
                updated_at    TEXT    DEFAULT (datetime('now'))
            )
        """)
        conn.commit()