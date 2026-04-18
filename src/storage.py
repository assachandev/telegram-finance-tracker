import calendar
import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

from src.config import DB_PATH, TIMEZONE

logger = logging.getLogger(__name__)

DEFAULT_CATEGORIES: dict[str, list[str]] = {
    "expense": ["Food", "Transport", "Shopping", "Entertainment", "Medical", "Education", "Bills", "Travel", "Other"],
    "income": ["Salary", "Freelance", "Business", "Gift", "Other"],
}


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                date     TEXT    NOT NULL,
                type     TEXT    NOT NULL CHECK(type IN ('expense', 'income')),
                category TEXT    NOT NULL,
                amount   REAL    NOT NULL,
                method   TEXT    NOT NULL CHECK(method IN ('cash', 'transfer')),
                note     TEXT    NOT NULL DEFAULT ''
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT    NOT NULL,
                name TEXT    NOT NULL,
                UNIQUE(type, name)
            )
        """)
        for tx_type, cats in DEFAULT_CATEGORIES.items():
            for cat in cats:
                conn.execute(
                    "INSERT OR IGNORE INTO categories (type, name) VALUES (?, ?)",
                    (tx_type, cat),
                )
    logger.info("Database ready at %s", DB_PATH)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _today() -> str:
    return datetime.now(TIMEZONE).strftime("%Y-%m-%d")


def _month_range(year: int, month: int) -> tuple[str, str]:
    last_day = calendar.monthrange(year, month)[1]
    return f"{year}-{month:02d}-01", f"{year}-{month:02d}-{last_day:02d}"


def _query(where: str = "", params: tuple = ()) -> list[dict]:
    sql = "SELECT * FROM transactions"
    if where:
        sql += f" WHERE {where}"
    sql += " ORDER BY id"
    with _conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

def get_categories() -> dict[str, list[str]]:
    with _conn() as conn:
        rows = conn.execute("SELECT type, name FROM categories ORDER BY name").fetchall()
    result: dict[str, list[str]] = {"expense": [], "income": []}
    for row in rows:
        result.setdefault(row["type"], []).append(row["name"])
    return result


def add_category(tx_type: str, name: str) -> bool:
    try:
        with _conn() as conn:
            conn.execute("INSERT INTO categories (type, name) VALUES (?, ?)", (tx_type, name))
        return True
    except sqlite3.IntegrityError:
        return False


def remove_category(tx_type: str, name: str) -> bool:
    with _conn() as conn:
        cur = conn.execute("DELETE FROM categories WHERE type = ? AND name = ?", (tx_type, name))
    return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def append_transaction(tx_type: str, category: str, amount: float, method: str, note: str = "") -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO transactions (date, type, category, amount, method, note) VALUES (?, ?, ?, ?, ?, ?)",
            (_today(), tx_type, category, amount, method, note),
        )


def delete_last_transaction() -> dict | None:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM transactions ORDER BY id DESC LIMIT 1").fetchone()
        if row is None:
            return None
        data = dict(row)
        conn.execute("DELETE FROM transactions WHERE id = ?", (data["id"],))
    return data


# ---------------------------------------------------------------------------
# Read — today
# ---------------------------------------------------------------------------

def get_today() -> list[dict]:
    return _query("date = ?", (_today(),))


# ---------------------------------------------------------------------------
# Read — this month / last month
# ---------------------------------------------------------------------------

def get_this_month() -> list[dict]:
    now = datetime.now(TIMEZONE)
    start, end = _month_range(now.year, now.month)
    return _query("date BETWEEN ? AND ?", (start, end))


def get_last_month() -> list[dict]:
    now = datetime.now(TIMEZONE)
    year, month = (now.year - 1, 12) if now.month == 1 else (now.year, now.month - 1)
    start, end = _month_range(year, month)
    return _query("date BETWEEN ? AND ?", (start, end))


# ---------------------------------------------------------------------------
# Read — this year / all time
# ---------------------------------------------------------------------------

def get_this_year() -> list[dict]:
    year = str(datetime.now(TIMEZONE).year)
    return _query("strftime('%Y', date) = ?", (year,))


def get_recent(n: int = 5) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM transactions ORDER BY id DESC LIMIT ?", (n,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_all() -> list[dict]:
    return _query()
