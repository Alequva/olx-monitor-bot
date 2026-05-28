import sqlite3
import threading
from typing import Optional

from config import DB_PATH

_local = threading.local()


def get_conn() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(DB_PATH)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
    return _local.conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id      INTEGER PRIMARY KEY,
            chat_id      INTEGER NOT NULL,
            category     TEXT    DEFAULT 'arenda-dolgosrochnaya',
            price_min    INTEGER DEFAULT 0,
            price_max    INTEGER DEFAULT 0,
            location     TEXT    DEFAULT '',
            rooms        TEXT    DEFAULT '',
            interval_m   INTEGER DEFAULT 30,
            backlog_days INTEGER DEFAULT 7,
            is_active    INTEGER DEFAULT 1,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS sent_posts (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            post_url   TEXT    NOT NULL,
            post_title TEXT,
            sent_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, post_url)
        );
    """)

    for col in [
        ("backlog_days", "INTEGER DEFAULT 7"),
        ("gender_pref", "TEXT DEFAULT 'any'"),
        ("session_dedup", "INTEGER DEFAULT 0"),
    ]:
        try:
            conn.execute(f"ALTER TABLE users ADD COLUMN {col[0]} {col[1]}")
            conn.commit()
        except sqlite3.OperationalError:
            pass
    conn.commit()


def register_user(user_id: int, chat_id: int):
    conn = get_conn()
    conn.execute(
        """INSERT OR IGNORE INTO users (user_id, chat_id) VALUES (?, ?)""",
        (user_id, chat_id),
    )
    conn.commit()


def get_user(user_id: int) -> Optional[sqlite3.Row]:
    conn = get_conn()
    return conn.execute(
        "SELECT * FROM users WHERE user_id = ?", (user_id,)
    ).fetchone()


def update_user(user_id: int, **kwargs):
    if not kwargs:
        return
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [user_id]
    conn = get_conn()
    conn.execute(f"UPDATE users SET {sets} WHERE user_id = ?", vals)
    conn.commit()


def is_post_sent(user_id: int, post_url: str) -> bool:
    conn = get_conn()
    row = conn.execute(
        "SELECT 1 FROM sent_posts WHERE user_id = ? AND post_url = ?",
        (user_id, post_url),
    ).fetchone()
    return row is not None


def mark_post_sent(user_id: int, post_url: str, post_title: str = ""):
    conn = get_conn()
    conn.execute(
        """INSERT OR IGNORE INTO sent_posts (user_id, post_url, post_title)
           VALUES (?, ?, ?)""",
        (user_id, post_url, post_title),
    )
    conn.commit()


def get_all_active_users():
    conn = get_conn()
    return conn.execute(
        "SELECT * FROM users WHERE is_active = 1"
    ).fetchall()
