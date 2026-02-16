"""
audit.py
────────
Detailed audit trail for every action in the system.
Logs to the DB audit table and exports to CSV on demand.
"""

import csv
import os
from datetime import datetime
from database import connect_db


ACTIONS = {
    "USER_REGISTERED":  "User registered",
    "USER_DELETED":     "User deleted",
    "MODEL_TRAINED":    "Model trained",
    "LOGIN_SUCCESS":    "Login successful",
    "LOGIN_FAIL":       "Login failed",
    "INTRUDER":         "Intruder detected",
    "LIVENESS_FAIL":    "Liveness check failed",
    "WRONG_PIN":        "Wrong PIN entered",
    "LOCKOUT":          "Account locked out",
    "LOCKOUT_RESET":    "Lockout manually reset",
    "PIN_RESET":        "PIN reset by admin",
    "SESSION_CREATED":  "Session token created",
    "SESSION_REVOKED":  "Session token revoked",
    "ADMIN_LOGIN":      "Admin panel accessed",
}


def log_action(action: str, performed_by: str = "SYSTEM",
               target_user: str = "", details: str = ""):
    """
    Write an audit entry to the database.

    Args:
        action       : One of the keys in ACTIONS dict above
        performed_by : Who triggered the action (username or SYSTEM)
        target_user  : User affected by the action (if different)
        details      : Any extra context
    """
    timestamp   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    description = ACTIONS.get(action, action)

    try:
        conn   = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO audit (timestamp, action, performed_by, target_user, details)
            VALUES (?, ?, ?, ?, ?)
        """, (timestamp, action, performed_by, target_user, details))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Audit] DB error: {e}")


def get_audit_log(limit: int = 200) -> list:
    """Return recent audit entries as list of dicts."""
    conn   = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT timestamp, action, performed_by, target_user, details
        FROM audit ORDER BY id DESC LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "timestamp":    r[0],
            "action":       r[1],
            "performed_by": r[2],
            "target_user":  r[3],
            "details":      r[4],
        }
        for r in rows
    ]


def export_to_csv(filepath: str = None) -> str:
    """
    Export the full audit log to a CSV file.
    Returns the path of the created file.
    """
    os.makedirs("logs", exist_ok=True)

    if filepath is None:
        ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = f"logs/audit_export_{ts}.csv"

    entries = get_audit_log(limit=10000)

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "timestamp", "action", "performed_by", "target_user", "details"
        ])
        writer.writeheader()
        writer.writerows(entries)

    print(f"[Audit] Exported {len(entries)} entries → {filepath}")
    return filepath