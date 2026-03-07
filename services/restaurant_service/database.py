
import sqlite3

DB_PATH = "restaurant.db"
def get_db() -> sqlite3.Connection: 
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
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