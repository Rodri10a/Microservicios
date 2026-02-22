# ═══════════════════════════════════════════════════════════════════════════════
# database.py — Servicio de Restaurantes
# Responsabilidad exclusiva: conexión e inicialización de la DB de este servicio.
# Ningún otro servicio toca este archivo ni esta base de datos.
# ═══════════════════════════════════════════════════════════════════════════════

import sqlite3

DB_PATH = "restaurant.db"


def get_db() -> sqlite3.Connection:
    """Retorna una conexión con row_factory para acceder columnas por nombre."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Crea las tablas si no existen. Se llama al arrancar el servicio."""
    with get_db() as conn:

        # Tabla de restaurantes
        conn.execute("""
            CREATE TABLE IF NOT EXISTS restaurants (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT    NOT NULL,
                address    TEXT    NOT NULL,
                phone      TEXT,
                is_open    INTEGER NOT NULL DEFAULT 1,
                created_at TEXT    DEFAULT (datetime('now'))
            )
        """)

        # Tabla de items del menú — pertenece al restaurante, no al pedido
        conn.execute("""
            CREATE TABLE IF NOT EXISTS menu_items (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                restaurant_id INTEGER NOT NULL,
                name          TEXT    NOT NULL,
                description   TEXT,
                price         REAL    NOT NULL,
                available     INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (restaurant_id) REFERENCES restaurants(id)
            )
        """)

        conn.commit()