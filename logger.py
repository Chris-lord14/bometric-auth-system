import os
from datetime import datetime
from database import connect_db

LOG_FILE = "logs/access.log"

STATUS_LABELS = {
    "SUCCESS":       "✅ SUCCESS",
    "FAILED":        "❌ FAILED",
    "INTRUDER":      "🚨 INTRUDER",
    "LIVENESS_FAIL": "⚠️  LIVENESS FAIL",
    "WRONG_PIN":     "🔒 WRONG PIN",
    "NO_PIN":        "🔒 NO PIN SET",
}

def log_attempt(username, status, confidence=0.0):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    os.makedirs("logs", exist_ok=True)

    # Save to database
    try:
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO logs (username, status, confidence, timestamp)
            VALUES (?, ?, ?, ?)
        """, (username, status, confidence, timestamp))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Logger DB Error]: {e}")

    # Save to text file
    try:
        label = STATUS_LABELS.get(status, status)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] User: {username:<20} | {label:<22} | Confidence: {confidence:.1f}%\n")
    except Exception as e:
        print(f"[Logger File Error]: {e}")