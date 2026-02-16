"""
session.py
──────────
Generates and validates signed session tokens after successful login.
Token format: base64(username:timestamp:random) + HMAC signature
Tokens expire after SESSION_DURATION_MINUTES.
"""

import secrets
import hashlib
import hmac
import base64
import json
import os
from datetime import datetime, timedelta
from database import connect_db

SESSION_DURATION_MINUTES = 30
# Secret key stored in a local file — generated once, never changes
KEY_FILE = "models/session.key"


def _get_secret_key():
    """Load or generate the HMAC signing key."""
    os.makedirs("models", exist_ok=True)
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "r") as f:
            return f.read().strip()
    key = secrets.token_hex(32)
    with open(KEY_FILE, "w") as f:
        f.write(key)
    return key


def _sign(payload: str) -> str:
    key = _get_secret_key().encode()
    return hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()


def create_session(username: str) -> str:
    """
    Create a signed session token for a successfully authenticated user.
    Returns the token string. Also persists to DB.
    """
    expires_at = (datetime.now() + timedelta(minutes=SESSION_DURATION_MINUTES)
                  ).strftime("%Y-%m-%d %H:%M:%S")
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    payload = json.dumps({
        "username":   username,
        "created_at": created_at,
        "expires_at": expires_at,
        "nonce":      secrets.token_hex(8)
    })
    encoded  = base64.b64encode(payload.encode()).decode()
    sig      = _sign(encoded)
    token    = f"{encoded}.{sig}"

    # Persist to DB
    conn   = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO sessions (username, token, created_at, expires_at, active)
        VALUES (?, ?, ?, ?, 1)
    """, (username, token, created_at, expires_at))
    conn.commit()
    conn.close()

    return token


def validate_session(token: str) -> dict | None:
    """
    Validate a session token.
    Returns user info dict if valid, None if expired or tampered.
    """
    try:
        encoded, sig = token.rsplit(".", 1)
    except ValueError:
        return None

    # Verify signature
    if not hmac.compare_digest(_sign(encoded), sig):
        return None

    payload = json.loads(base64.b64decode(encoded).decode())
    expires = datetime.strptime(payload["expires_at"], "%Y-%m-%d %H:%M:%S")

    if datetime.now() > expires:
        invalidate_session(token)
        return None

    # Check DB — token must still be active
    conn   = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT active FROM sessions WHERE token = ?", (token,))
    row    = cursor.fetchone()
    conn.close()

    if not row or row[0] != 1:
        return None

    return payload


def invalidate_session(token: str):
    """Revoke a session token (logout)."""
    conn   = connect_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE sessions SET active = 0 WHERE token = ?", (token,))
    conn.commit()
    conn.close()


def get_active_sessions():
    """Return all currently active (non-expired) sessions."""
    conn   = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT username, created_at, expires_at
        FROM sessions WHERE active = 1
        ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows