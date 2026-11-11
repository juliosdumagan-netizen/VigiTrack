import os
import sqlite3

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "vigitrack.db"))


def get_connection():
    """Returns a SQLite connection configured with WAL mode and row factory."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Initializes the database schema if not already created."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                object_class TEXT NOT NULL,
                object_track_id INTEGER,
                person_track_id INTEGER,
                distance REAL,
                camera_name TEXT,
                status TEXT DEFAULT 'unattended',
                detected_at TEXT NOT NULL
            )
        """)
        conn.commit()
    finally:
        conn.close()
