import sqlite3
import threading
from typing import Dict, List

DB_PATH = "bot_data.db"


class Database:
    def __init__(self):
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._lock:
            conn = self._connect()
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS watches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    username TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(chat_id, username)
                );
                CREATE TABLE IF NOT EXISTS seen_videos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    video_id TEXT NOT NULL,
                    seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(username, video_id)
                );
                CREATE TABLE IF NOT EXISTS stats (
                    chat_id INTEGER PRIMARY KEY,
                    downloaded INTEGER DEFAULT 0
                );
            """)
            conn.commit()
            conn.close()

    def add_watch(self, chat_id: int, username: str) -> bool:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("INSERT OR IGNORE INTO watches (chat_id, username) VALUES (?, ?)", (chat_id, username.lower()))
                conn.execute("INSERT OR IGNORE INTO stats (chat_id, downloaded) VALUES (?, 0)", (chat_id,))
                conn.commit()
                return conn.execute("SELECT changes() as c").fetchone()["c"] > 0
            finally:
                conn.close()

    def remove_watch(self, chat_id: int, username: str) -> bool:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("DELETE FROM watches WHERE chat_id=? AND username=?", (chat_id, username.lower()))
                conn.commit()
                return conn.execute("SELECT changes() as c").fetchone()["c"] > 0
            finally:
                conn.close()

    def get_watches(self, chat_id: int) -> List[str]:
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute("SELECT username FROM watches WHERE chat_id=? ORDER BY username", (chat_id,)).fetchall()
                return [r["username"] for r in rows]
            finally:
                conn.close()

    def get_all_watches(self) -> Dict[str, List[int]]:
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute("SELECT username, chat_id FROM watches").fetchall()
                result: Dict[str, List[int]] = {}
                for row in rows:
                    result.setdefault(row["username"], []).append(row["chat_id"])
                return result
            finally:
                conn.close()

    def is_seen(self, username: str, video_id: str) -> bool:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute("SELECT 1 FROM seen_videos WHERE username=? AND video_id=?", (username.lower(), video_id)).fetchone()
                return row is not None
            finally:
                conn.close()

    def mark_seen(self, username: str, video_id: str):
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("INSERT OR IGNORE INTO seen_videos (username, video_id) VALUES (?, ?)", (username.lower(), video_id))
                conn.commit()
            finally:
                conn.close()

    def increment_downloaded(self, chat_id: int):
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("INSERT INTO stats (chat_id, downloaded) VALUES (?, 1) ON CONFLICT(chat_id) DO UPDATE SET downloaded = downloaded + 1", (chat_id,))
                conn.commit()
            finally:
                conn.close()

    def get_total_watches(self) -> int:
        with self._lock:
            conn = self._connect()
            try:
                return conn.execute("SELECT COUNT(*) as c FROM watches").fetchone()["c"]
            finally:
                conn.close()

    def get_total_chats(self) -> int:
        with self._lock:
            conn = self._connect()
            try:
                return conn.execute("SELECT COUNT(DISTINCT chat_id) as c FROM watches").fetchone()["c"]
            finally:
                conn.close()

    def get_total_downloaded(self) -> int:
        with self._lock:
            conn
