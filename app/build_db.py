# ============================================================
# Import into app.pywith:
#   from build_db import (
#       get_db_connection, init_db, init_db_full,
#       get_user_id, cache_dataframe, get_cached_rows,
#       log_ml_prediction,
#   )
# ============================================================

import sqlite3
import datetime

DATABASE = "users.db"


# ---------------------------------------------------------------
# CONNECTION
# ---------------------------------------------------------------

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------
# TABLE CREATION
# ---------------------------------------------------------------

def init_db():
    """Original users table — kept separate so existing code still works."""
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def init_db_full():
    """Creates all tables. Call this on app startup instead of (or after) init_db()."""
    conn = get_db_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            ticker  TEXT    NOT NULL,
            UNIQUE(user_id, ticker),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS stock_cache (
            id     INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            date   DATE NOT NULL,
            open   REAL,
            high   REAL,
            low    REAL,
            close  REAL,
            volume INTEGER,
            UNIQUE(ticker, date)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS portfolio (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER  NOT NULL,
            ticker     TEXT     NOT NULL,
            shares     REAL     NOT NULL DEFAULT 0,
            avg_price  REAL     NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, ticker),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS ai_queries (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            ticker     TEXT,
            question   TEXT,
            answer     TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS ml_predictions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker          TEXT NOT NULL,
            prediction_date DATE NOT NULL,
            target_date     DATE NOT NULL,
            predicted_price REAL NOT NULL
        )
    """)

    conn.commit()
    conn.close()


# USER HELPERS


def get_user_id(username: str):
    """Return the integer user id for a given username, or None."""
    conn = get_db_connection()
    row  = conn.execute(
        "SELECT id FROM users WHERE username = ?", (username,)
    ).fetchone()
    conn.close()
    return row["id"] if row else None


def get_user_by_username(username: str):
    """Return the full users row for a given username, or None."""
    conn = get_db_connection()
    row  = conn.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()
    conn.close()
    return row


def create_user(username: str, hashed_password: str):
    """
    Insert a new user. Returns True on success, False if username already exists.
    Raises sqlite3.IntegrityError on duplicate — caller can catch it.
    """
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO users (username, password) VALUES (?, ?)",
        (username, hashed_password),
    )
    conn.commit()
    conn.close()


# STOCK CACHE HELPERS


def cache_dataframe(ticker: str, df):
    """Write a yFinance history DataFrame into stock_cache."""
    conn = get_db_connection()
    for idx, row in df.iterrows():
        date_str = idx.strftime("%Y-%m-%d")
        conn.execute(
            """
            INSERT OR IGNORE INTO stock_cache
                (ticker, date, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticker,
                date_str,
                float(row.get("Open",   0)),
                float(row.get("High",   0)),
                float(row.get("Low",    0)),
                float(row.get("Close",  0)),
                int(row.get("Volume",   0)),
            ),
        )
    conn.commit()
    conn.close()


def get_cached_rows(ticker: str, since_date: str):
    """
    Return cached stock_cache rows for ticker on or after since_date ('YYYY-MM-DD').
    Rows are ordered ascending by date.
    """
    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT * FROM stock_cache
        WHERE ticker = ? AND date >= ?
        ORDER BY date ASC
        """,
        (ticker, since_date),
    ).fetchall()
    conn.close()
    return rows


# WATCHLIST HELPERS


def get_watchlist(user_id: int):
    """Return all tickers on a user's watchlist."""
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT ticker FROM watchlist WHERE user_id = ? ORDER BY ticker ASC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [r["ticker"] for r in rows]


def add_to_watchlist(user_id: int, ticker: str):
    """Add ticker to watchlist. Silently ignores duplicates (INSERT OR IGNORE)."""
    conn = get_db_connection()
    conn.execute(
        "INSERT OR IGNORE INTO watchlist (user_id, ticker) VALUES (?, ?)",
        (user_id, ticker),
    )
    conn.commit()
    conn.close()


def remove_from_watchlist(user_id: int, ticker: str):
    """Remove ticker from watchlist."""
    conn = get_db_connection()
    conn.execute(
        "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?",
        (user_id, ticker),
    )
    conn.commit()
    conn.close()


# PORTFOLIO HELPERS


def get_portfolio(user_id: int):
    """Return all holdings for a user."""
    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT ticker, shares, avg_price, created_at
        FROM portfolio
        WHERE user_id = ?
        ORDER BY ticker ASC
        """,
        (user_id,),
    ).fetchall()
    conn.close()
    return rows


def upsert_portfolio(user_id: int, ticker: str, shares: float, avg_price: float):
    """
    Add shares to a holding. If the ticker already exists, blends the
    average price (weighted average). If it doesn't, inserts a new row.
    """
    conn = get_db_connection()
    existing = conn.execute(
        "SELECT shares, avg_price FROM portfolio WHERE user_id = ? AND ticker = ?",
        (user_id, ticker),
    ).fetchone()

    if existing:
        old_shares = existing["shares"]
        old_avg    = existing["avg_price"]
        new_shares = old_shares + shares
        new_avg    = (old_shares * old_avg + shares * avg_price) / new_shares
        conn.execute(
            "UPDATE portfolio SET shares = ?, avg_price = ? WHERE user_id = ? AND ticker = ?",
            (new_shares, new_avg, user_id, ticker),
        )
    else:
        conn.execute(
            "INSERT INTO portfolio (user_id, ticker, shares, avg_price) VALUES (?, ?, ?, ?)",
            (user_id, ticker, shares, avg_price),
        )

    conn.commit()
    conn.close()


def remove_from_portfolio(user_id: int, ticker: str):
    """Remove a holding entirely from the portfolio."""
    conn = get_db_connection()
    conn.execute(
        "DELETE FROM portfolio WHERE user_id = ? AND ticker = ?",
        (user_id, ticker),
    )
    conn.commit()
    conn.close()

