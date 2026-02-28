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
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                restaurant_name TEXT    NOT NULL,
                customer_name   TEXT    NOT NULL,
                status          TEXT    NOT NULL DEFAULT 'pending',
                total           REAL    NOT NULL DEFAULT 0,
                items           TEXT    NOT NULL
            )
        """)
        conn.commit()