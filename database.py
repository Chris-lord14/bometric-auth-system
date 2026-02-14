import sqlite3
import os

DB_NAME = "auth.db"

def connect_db():
    return sqlite3.connect(DB_NAME)

def create_tables():
    # Ensure required directories exist
    os.makedirs("models", exist_ok=True)
    os.makedirs("datasets", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    os.makedirs("intruders", exist_ok=True)

    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fullname TEXT NOT NULL,
        username TEXT UNIQUE NOT NULL,
        pin_hash TEXT,
        date_registered TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        status TEXT,
        confidence REAL,
        timestamp TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS lockouts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        identifier TEXT UNIQUE NOT NULL,
        fail_count INTEGER DEFAULT 0,
        locked_until TEXT
    )
    """)

    # Add pin_hash column if upgrading from older DB (safe migration)
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN pin_hash TEXT")
    except Exception:
        pass  # Column already exists

    conn.commit()
    conn.close()


def get_lockout(identifier):
    """Returns (fail_count, locked_until_str) or (0, None) if not found."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT fail_count, locked_until FROM lockouts WHERE identifier = ?", (identifier,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row[0], row[1]
    return 0, None


def record_failure(identifier):
    """Increment fail count. Lock for 30s after 5 failures. Returns (fail_count, locked_until_str)."""
    from datetime import datetime, timedelta

    fail_count, _ = get_lockout(identifier)
    fail_count += 1
    locked_until = None

    if fail_count >= 5:
        locked_until = (datetime.now() + timedelta(seconds=30)).strftime("%Y-%m-%d %H:%M:%S")

    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO lockouts (identifier, fail_count, locked_until)
        VALUES (?, ?, ?)
        ON CONFLICT(identifier) DO UPDATE SET fail_count = ?, locked_until = ?
    """, (identifier, fail_count, locked_until, fail_count, locked_until))
    conn.commit()
    conn.close()
    return fail_count, locked_until


def reset_failures(identifier):
    """Reset fail count after successful login."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM lockouts WHERE identifier = ?", (identifier,))
    conn.commit()
    conn.close()


def is_locked_out(identifier):
    """Returns (True, seconds_remaining) if locked, (False, 0) otherwise."""
    from datetime import datetime
    _, locked_until = get_lockout(identifier)
    if locked_until:
        locked_dt = datetime.strptime(locked_until, "%Y-%m-%d %H:%M:%S")
        now = datetime.now()
        if now < locked_dt:
            remaining = int((locked_dt - now).total_seconds())
            return True, remaining
        else:
            reset_failures(identifier)
    return False, 0


def save_pin_hash(username, pin_hash):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET pin_hash = ? WHERE username = ?", (pin_hash, username))
    conn.commit()
    conn.close()


def get_pin_hash(username):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT pin_hash FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None