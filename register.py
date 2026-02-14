import cv2
import os
from datetime import datetime
from database import connect_db
from pin_auth import prompt_set_pin

CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
face_cascade = cv2.CascadeClassifier(CASCADE_PATH)


def register_user(fullname, username):
    if not fullname or not username:
        return False, "Full name and username cannot be empty!"

    username_clean = username.strip().replace(" ", "_")
    dataset_path = f"datasets/{username_clean}"

    if os.path.exists(dataset_path):
        return False, f"User '{username_clean}' already exists!"

    os.makedirs(dataset_path, exist_ok=True)

    # Insert into DB first
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO users (fullname, username, date_registered)
            VALUES (?, ?, ?)
        """, (fullname, username_clean, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
    except Exception as e:
        conn.close()
        os.rmdir(dataset_path)
        return False, f"Database Error: {str(e)}"
    finally:
        conn.close()

    # ── Face capture ──────────────────────────────────────────────────────────
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return False, "Cannot access webcam."

    count = 0
    target = 30

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)
        gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)

        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

        face_ok = len(faces) > 0
        color   = (0, 255, 0) if face_ok else (0, 0, 255)
        label   = "Face Detected ✓" if face_ok else "No Face Detected"

        cv2.putText(frame, f"Captured: {count}/{target}", (10, 32),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.85, color, 2)
        cv2.putText(frame, label, (10, 62),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        cv2.putText(frame, "SPACE: Capture  |  ESC: Cancel", (10, frame.shape[0] - 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 180, 180), 1)

        cv2.imshow(f"Register: {username_clean}", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == 32 and face_ok:
            count += 1
            cv2.imwrite(os.path.join(dataset_path, f"{count}.jpg"), frame)
        elif key == 27:
            break

        if count >= target:
            break

    cap.release()
    cv2.destroyAllWindows()

    if count == 0:
        os.rmdir(dataset_path)
        return False, "No images captured. Registration cancelled."

    # ── PIN setup (Tkinter dialog) ────────────────────────────────────────────
    pin_hash = prompt_set_pin(username_clean)

    if pin_hash is None:
        # User cancelled PIN — still registered but without PIN
        return True, (f"User '{username_clean}' registered with {count} images.\n"
                      "Warning: No PIN set. You will not be able to log in until a PIN is assigned.")

    # Save PIN hash to DB
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET pin_hash = ? WHERE username = ?",
                   (pin_hash, username_clean))
    conn.commit()
    conn.close()

    return True, f"User '{username_clean}' registered with {count} images and PIN set!"