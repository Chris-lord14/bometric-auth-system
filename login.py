import cv2
import pickle
import numpy as np
import os
from datetime import datetime
from logger import log_attempt
from database import (is_locked_out, record_failure, reset_failures,
                      get_pin_hash)
from liveness import check_liveness
from pin_auth import prompt_verify_pin

MODEL_PATH     = "models/face_model.yml"
LABEL_MAP_PATH = "models/label_map.pkl"
INTRUDER_DIR   = "intruders"

CASCADE_PATH   = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
face_cascade   = cv2.CascadeClassifier(CASCADE_PATH)

# LBPH: lower confidence value = better match
CONFIDENCE_THRESHOLD = 80.0
LOCKOUT_IDENTIFIER   = "login"   # single global lockout key


def _save_intruder_snapshot(frame):
    """Save a timestamped snapshot of an unrecognised face."""
    os.makedirs(INTRUDER_DIR, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(INTRUDER_DIR, f"intruder_{ts}.jpg")
    cv2.imwrite(path, frame)
    print(f"[Security] Intruder snapshot saved: {path}")
    return path


def login_user():
    # ── 1. Lockout check ──────────────────────────────────────────────────────
    locked, secs = is_locked_out(LOCKOUT_IDENTIFIER)
    if locked:
        return False, (f"Too many failed attempts.\n"
                       f"Account locked. Try again in {secs} second(s).")

    # ── 2. Load model ─────────────────────────────────────────────────────────
    if not os.path.exists(MODEL_PATH) or not os.path.exists(LABEL_MAP_PATH):
        return False, "Model not found! Please train the model first."

    try:
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.read(MODEL_PATH)
        with open(LABEL_MAP_PATH, "rb") as f:
            label_map = pickle.load(f)
    except Exception as e:
        return False, f"Error loading model: {e}"

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return False, "Cannot access webcam."

    # ── 3. Liveness check (blink detection) ───────────────────────────────────
    cv2.namedWindow("Liveness Check - Blink to continue")
    liveness_ok = check_liveness(cap, face_cascade)
    cv2.destroyAllWindows()

    if not liveness_ok:
        cap.release()
        fail_count, locked_until = record_failure(LOCKOUT_IDENTIFIER)
        log_attempt("UNKNOWN", "LIVENESS_FAIL", 0.0)

        # Capture intruder snapshot from last webcam frame
        ret, snap = cap.read() if cap.isOpened() else (False, None)
        if ret and snap is not None:
            _save_intruder_snapshot(snap)
        cap.release()

        msg = "Liveness check failed. Please blink naturally."
        if fail_count >= 5:
            return False, f"{msg}\nAccount locked for 30 seconds."
        return False, f"{msg} ({5 - fail_count} attempt(s) left before lockout)"

    # ── 4. Face recognition ───────────────────────────────────────────────────
    recognized_user  = None
    best_confidence  = None
    intruder_frame   = None
    frames_checked   = 0
    MAX_RECOG_FRAMES = 150   # ~5 seconds

    while frames_checked < MAX_RECOG_FRAMES:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)
        gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)
        frames_checked += 1

        for (x, y, w, h) in faces:
            face_roi = cv2.resize(gray[y:y + h, x:x + w], (100, 100))
            label_id, confidence = recognizer.predict(face_roi)
            match_quality = max(0.0, 100.0 - confidence)
            predicted_user = label_map.get(label_id, "Unknown")

            color = (0, 255, 0) if confidence < CONFIDENCE_THRESHOLD else (0, 0, 255)
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            cv2.putText(frame, f"{predicted_user} ({match_quality:.1f}%)",
                        (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.75, color, 2)

            if confidence < CONFIDENCE_THRESHOLD:
                recognized_user = predicted_user
                best_confidence = match_quality
                intruder_frame  = None   # clear — this is a valid face
                break
            else:
                intruder_frame = frame.copy()

        if recognized_user:
            break

        cv2.putText(frame, f"Scanning... ({MAX_RECOG_FRAMES - frames_checked} frames left)",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (200, 200, 200), 1)
        cv2.putText(frame, "ESC: Cancel", (10, frame.shape[0] - 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (150, 150, 150), 1)
        cv2.imshow("Login - Face Recognition", frame)

        if cv2.waitKey(1) & 0xFF == 27:
            break

    cap.release()
    cv2.destroyAllWindows()

    # ── 5. Handle unrecognised face ───────────────────────────────────────────
    if not recognized_user:
        if intruder_frame is not None:
            snap_path = _save_intruder_snapshot(intruder_frame)
            log_attempt("UNKNOWN", "INTRUDER", 0.0)
        else:
            log_attempt("UNKNOWN", "FAILED", 0.0)

        fail_count, locked_until = record_failure(LOCKOUT_IDENTIFIER)
        msg = "Face not recognised."
        if fail_count >= 5:
            return False, f"{msg}\nAccount locked for 30 seconds."
        return False, f"{msg} ({5 - fail_count} attempt(s) left before lockout)"

    # ── 6. MFA — PIN verification ─────────────────────────────────────────────
    stored_pin = get_pin_hash(recognized_user)

    if stored_pin is None:
        log_attempt(recognized_user, "NO_PIN", best_confidence)
        fail_count, _ = record_failure(LOCKOUT_IDENTIFIER)
        return False, f"No PIN set for '{recognized_user}'. Please re-register."

    pin_ok = prompt_verify_pin(recognized_user, stored_pin)

    if not pin_ok:
        log_attempt(recognized_user, "WRONG_PIN", best_confidence)
        fail_count, locked_until = record_failure(LOCKOUT_IDENTIFIER)
        msg = f"Wrong PIN for '{recognized_user}'."
        if fail_count >= 5:
            return False, f"{msg}\nAccount locked for 30 seconds."
        return False, f"{msg} ({5 - fail_count} attempt(s) left before lockout)"

    # ── 7. All checks passed ──────────────────────────────────────────────────
    reset_failures(LOCKOUT_IDENTIFIER)
    log_attempt(recognized_user, "SUCCESS", best_confidence)
    return True, f"Login Successful! Welcome, {recognized_user} ({best_confidence:.1f}% confidence)"