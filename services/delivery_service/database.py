
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
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL UNIQUE,
                address  TEXT    NOT NULL,
                status   TEXT    NOT NULL DEFAULT 'assigned'
            )
        """)
        conn.commit()

