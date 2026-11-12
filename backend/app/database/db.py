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
        existing = {row["name"] for row in cursor.execute("PRAGMA table_info(incidents)").fetchall()}
        new_columns = {
            "image_path": "TEXT",
            "state_history": "TEXT",
            "distance_threshold": "REAL",
            "time_threshold": "REAL",
        }
        for name, column_type in new_columns.items():
            if name not in existing:
                cursor.execute(f"ALTER TABLE incidents ADD COLUMN {name} {column_type}")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('admin', 'operator')),
                is_active INTEGER NOT NULL DEFAULT 1,
                failed_attempts INTEGER NOT NULL DEFAULT 0,
                locked_until TEXT,
                created_at TEXT NOT NULL,
                last_login_at TEXT,
                must_change_password INTEGER NOT NULL DEFAULT 0
            )
        """)
        user_columns = {row["name"] for row in cursor.execute("PRAGMA table_info(users)").fetchall()}
        if "must_change_password" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                actor TEXT,
                action TEXT NOT NULL,
                detail TEXT
            )
        """)
        conn.commit()
    finally:
        conn.close()
