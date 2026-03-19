import os
import sqlite3
import logging
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")
DB_FILE  = os.path.join(DATA_DIR, "mediaman.db")
LOG_FILE = os.path.join(DATA_DIR, "activity.log")

os.makedirs(DATA_DIR, exist_ok=True)

activity_logger = logging.getLogger("activity")
activity_logger.setLevel(logging.INFO)
if not activity_logger.handlers:
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    activity_logger.addHandler(fh)


def log(message: str):
    activity_logger.info(message)


def _get_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      TEXT NOT NULL,
                username     TEXT,
                media_id     TEXT NOT NULL,
                title        TEXT NOT NULL,
                year         TEXT,
                media_type   TEXT,
                requested_at TEXT NOT NULL,
                UNIQUE(user_id, media_id)
            )
        """)
        # Downloads log table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS downloads (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                title        TEXT NOT NULL,
                year         TEXT,
                quality      TEXT,
                downloaded_at TEXT NOT NULL
            )
        """)
        conn.commit()


init_db()


def add_request(user_id, movie: dict, username: str = None):
    with _get_conn() as conn:
        try:
            conn.execute(
                "INSERT INTO requests (user_id, username, media_id, title, year, media_type, requested_at) VALUES (?,?,?,?,?,?,?)",
                (str(user_id), username, str(movie["id"]), movie["title"], movie.get("year", ""), movie.get("type", "movie"), datetime.now().isoformat()),
            )
            conn.commit()
            log(f"REQUEST | user={username or user_id} | {movie['title']} ({movie.get('year', '')})")
        except sqlite3.IntegrityError:
            pass


def get_user_requests(user_id) -> list:
    with _get_conn() as conn:
        rows = conn.execute("SELECT * FROM requests WHERE user_id=? ORDER BY requested_at", (str(user_id),)).fetchall()
    return [dict(r) for r in rows]


def get_all_requests() -> dict:
    with _get_conn() as conn:
        rows = conn.execute("SELECT * FROM requests ORDER BY user_id, requested_at").fetchall()
    result = {}
    for r in rows:
        r = dict(r)
        uid = r["user_id"]
        if uid not in result:
            result[uid] = []
        result[uid].append({
            "id": r["media_id"],
            "media_id": r["media_id"],
            "title": r["title"],
            "year": r["year"],
            "type": r["media_type"],
            "username": r["username"],
            "user_id": r["user_id"],
        })
    return result


def get_requesters_by_title(title: str) -> list:
    """Return list of (user_id, username) who requested a specific title."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT user_id, username FROM requests WHERE title=?",
            (title,)
        ).fetchall()
    return [dict(r) for r in rows]


def delete_user_request(user_id, media_id) -> bool:
    with _get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM requests WHERE user_id=? AND media_id=?",
            (str(user_id), str(media_id))
        )
        conn.commit()
    return cur.rowcount > 0


def delete_requests_by_title(title: str):
    """Remove ALL requests for a given title (after successful download)."""
    with _get_conn() as conn:
        conn.execute("DELETE FROM requests WHERE title=?", (title,))
        conn.commit()


def clear_all_requests():
    with _get_conn() as conn:
        conn.execute("DELETE FROM requests")
        conn.commit()
    log("ADMIN | Cleared all requests")


def log_download(title: str, year: str, quality: str):
    """Record a completed download."""
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO downloads (title, year, quality, downloaded_at) VALUES (?,?,?,?)",
            (title, year, quality, datetime.now().isoformat())
        )
        conn.commit()
    log(f"DOWNLOAD | {title} ({year}) | {quality}")


def get_stats() -> dict:
    """Return stats: total requests, top requesters, total downloads."""
    with _get_conn() as conn:
        total_requests = conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
        total_downloads = conn.execute("SELECT COUNT(*) FROM downloads").fetchone()[0]
        top_users = conn.execute("""
            SELECT username, user_id, COUNT(*) as count
            FROM requests
            GROUP BY user_id
            ORDER BY count DESC
            LIMIT 5
        """).fetchall()
        recent_downloads = conn.execute("""
            SELECT title, year, quality, downloaded_at
            FROM downloads
            ORDER BY downloaded_at DESC
            LIMIT 5
        """).fetchall()

    return {
        "total_requests": total_requests,
        "total_downloads": total_downloads,
        "top_users": [dict(r) for r in top_users],
        "recent_downloads": [dict(r) for r in recent_downloads],
    }


def get_activity(limit: int = 30) -> list:
    """Return recent activity log entries from file."""
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    results = []
    for line in reversed(lines[-limit:]):
        line = line.strip()
        if not line:
            continue
        parts = line.split(" | ", 1)
        results.append({
            "timestamp": parts[0] if len(parts) > 1 else "",
            "message": parts[1] if len(parts) > 1 else line,
        })
    return results