"""
email_alert.py
─────────────
Sends security alert emails via Gmail SMTP.

SETUP (one-time):
  1. Enable 2-Factor Authentication on your Gmail account
  2. Go to: myaccount.google.com → Security → App Passwords
  3. Create an App Password for "Mail"
  4. Paste the 16-character password into SENDER_APP_PASSWORD below
  5. Fill in SENDER_EMAIL and RECIPIENT_EMAIL

Never use your real Gmail password here — always use an App Password.
"""

import smtplib
import ssl
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText
from email.mime.image     import MIMEImage
from datetime             import datetime

# ── Configuration — edit these ────────────────────────────────────────────────
SENDER_EMAIL      = "your_gmail@gmail.com"       # Gmail you send FROM
SENDER_APP_PASSWORD = "xxxx xxxx xxxx xxxx"      # 16-char Gmail App Password
RECIPIENT_EMAIL   = "alert_recipient@gmail.com"  # Where alerts are sent TO

ALERTS_ENABLED    = True    # Set False to disable all alerts without removing code

# Gmail SMTP settings (do not change)
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465   # SSL port
# ─────────────────────────────────────────────────────────────────────────────

# Alert trigger flags — set any to False to silence that specific event
ALERT_ON = {
    "INTRUDER":      True,
    "LIVENESS_FAIL": True,
    "WRONG_PIN":     True,
    "LOCKOUT":       True,
}

# Human-readable labels for each event type
EVENT_LABELS = {
    "INTRUDER":      "🚨 Intruder Detected",
    "LIVENESS_FAIL": "⚠️  Liveness Check Failed",
    "WRONG_PIN":     "🔒 Wrong PIN Entered",
    "LOCKOUT":       "🔴 Account Locked Out",
}

# Severity colours for email body
EVENT_COLORS = {
    "INTRUDER":      "#dc2626",
    "LIVENESS_FAIL": "#d97706",
    "WRONG_PIN":     "#7c3aed",
    "LOCKOUT":       "#b91c1c",
}


def _build_html(event_type, username, confidence, timestamp, extra_info=""):
    label  = EVENT_LABELS.get(event_type, event_type)
    color  = EVENT_COLORS.get(event_type, "#475569")

    return f"""
    <html><body style="font-family: Arial, sans-serif; background:#0f172a; color:#e2e8f0; padding:30px;">
      <div style="max-width:520px; margin:auto; background:#1e293b; border-radius:10px;
                  border-left: 6px solid {color}; padding:24px;">

        <h2 style="color:{color}; margin-top:0;">
          {label}
        </h2>

        <table style="width:100%; border-collapse:collapse;">
          <tr>
            <td style="padding:8px 0; color:#94a3b8; width:140px;">Event</td>
            <td style="padding:8px 0; font-weight:bold;">{label}</td>
          </tr>
          <tr>
            <td style="padding:8px 0; color:#94a3b8;">Username</td>
            <td style="padding:8px 0;">{username}</td>
          </tr>
          <tr>
            <td style="padding:8px 0; color:#94a3b8;">Timestamp</td>
            <td style="padding:8px 0;">{timestamp}</td>
          </tr>
          <tr>
            <td style="padding:8px 0; color:#94a3b8;">Confidence</td>
            <td style="padding:8px 0;">{confidence:.1f}%</td>
          </tr>
          {"" if not extra_info else f'''
          <tr>
            <td style="padding:8px 0; color:#94a3b8;">Details</td>
            <td style="padding:8px 0;">{extra_info}</td>
          </tr>'''}
        </table>

        {"<p style='margin-top:16px; color:#f87171; font-size:13px;'>⚠ An intruder snapshot has been attached.</p>" if event_type == "INTRUDER" else ""}

        <hr style="border:none; border-top:1px solid #334155; margin:20px 0;">
        <p style="color:#475569; font-size:12px; margin:0;">
          Biometric Authentication System &nbsp;|&nbsp; Automated Security Alert
        </p>
      </div>
    </body></html>
    """


def send_alert(event_type, username="UNKNOWN", confidence=0.0,
               snapshot_path=None, extra_info=""):
    """
    Send a security alert email.

    Args:
        event_type    : One of INTRUDER, LIVENESS_FAIL, WRONG_PIN, LOCKOUT
        username      : Username involved (or UNKNOWN)
        confidence    : Face match confidence score
        snapshot_path : Optional path to intruder image to attach
        extra_info    : Optional extra detail string shown in email
    """
    if not ALERTS_ENABLED:
        return

    if not ALERT_ON.get(event_type, False):
        return

    if SENDER_EMAIL.startswith("your_") or SENDER_APP_PASSWORD.startswith("xxxx"):
        print("[Email Alert] ⚠ Not configured — edit SENDER_EMAIL and SENDER_APP_PASSWORD in email_alert.py")
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    label     = EVENT_LABELS.get(event_type, event_type)
    subject   = f"[Security Alert] {label} — {timestamp}"

    try:
        msg = MIMEMultipart("related")
        msg["From"]    = SENDER_EMAIL
        msg["To"]      = RECIPIENT_EMAIL
        msg["Subject"] = subject

        # HTML body
        html_body = _build_html(event_type, username, confidence, timestamp, extra_info)
        msg.attach(MIMEText(html_body, "html"))

        # Attach intruder snapshot if provided
        if snapshot_path and os.path.exists(snapshot_path):
            with open(snapshot_path, "rb") as img_file:
                img = MIMEImage(img_file.read(), name=os.path.basename(snapshot_path))
                img.add_header("Content-Disposition", "attachment",
                               filename=os.path.basename(snapshot_path))
                msg.attach(img)

        # Send via Gmail SSL
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
            server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())

        print(f"[Email Alert] Sent: {label} → {RECIPIENT_EMAIL}")

    except smtplib.SMTPAuthenticationError:
        print("[Email Alert] ❌ Authentication failed — check your App Password in email_alert.py")
    except smtplib.SMTPException as e:
        print(f"[Email Alert] ❌ SMTP error: {e}")
    except Exception as e:
        print(f"[Email Alert] ❌ Unexpected error: {e}")


def test_alert():
    """Call this once to verify your email setup is working."""
    print("[Email Alert] Sending test email...")
    send_alert(
        event_type   = "INTRUDER",
        username     = "TEST_USER",
        confidence   = 45.2,
        extra_info   = "This is a test alert from your Biometric Auth System."
    )