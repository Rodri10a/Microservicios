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
    """Crea la tabla si no existe. Se llama al arrancar el servicio."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS menu_items (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                restaurant_name TEXT    NOT NULL,
                name            TEXT    NOT NULL,
                price           REAL    NOT NULL
            )
        """)
        conn.commit()