import cv2
import numpy as np

# ── Configuration ─────────────────────────────────────────────────────────────
REQUIRED_BLINKS   = 2     # blinks needed to pass
MAX_FRAMES        = 300   # ~10 seconds at 30fps
CONSEC_CLOSED     = 2     # consecutive frames eye must be "closed" to count
EYE_CLOSED_RATIO  = 0.23  # contour height/ROI height below this = closed

# Eye sub-regions within face bounding box (fractions of face w/h)
LEFT_EYE_X  = (0.15, 0.45)
RIGHT_EYE_X = (0.55, 0.85)
EYE_Y       = (0.20, 0.50)


def _preprocess(gray_roi):
    """CLAHE — boosts local contrast in dark/dull regions."""
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4))
    return clahe.apply(gray_roi)


def _eye_open_ratio(eye_gray):
    """
    Geometry-based open/closed estimate using iris/pupil contour shape.
    Works in dim light because it uses shape, NOT brightness.
    Returns ratio of (largest dark contour height / ROI height).
      Open eye  → tall iris visible  → ratio ~0.4–0.7
      Closed eye → lid covers iris   → ratio <0.23
    """
    if eye_gray.size == 0:
        return 1.0

    h, w = eye_gray.shape
    if h == 0 or w == 0:
        return 1.0

    # Enhance local contrast before thresholding
    enhanced = _preprocess(eye_gray)

    # Adaptive threshold — adapts per-pixel to local lighting conditions
    thresh = cv2.adaptiveThreshold(
        enhanced, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        blockSize=11, C=4
    )

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return 1.0

    largest = max(contours, key=cv2.contourArea)
    if cv2.contourArea(largest) < (h * w * 0.02):
        return 1.0   # noise

    _, _, cw, ch = cv2.boundingRect(largest)
    return ch / h


def _extract_eye_roi(gray, fx, fy, fw, fh, x_range, y_range):
    """Extract eye ROI from face bounding box using relative coordinates."""
    x1 = int(fx + x_range[0] * fw)
    x2 = int(fx + x_range[1] * fw)
    y1 = int(fy + y_range[0] * fh)
    y2 = int(fy + y_range[1] * fh)
    return gray[y1:y2, x1:x2], (x1, y1, x2, y2)


def check_liveness(cap, face_cascade):
    """
    Geometry + adaptive-threshold blink detection.
    Robust in poor / dull lighting — uses contour shape, not pixel brightness.

    Returns:
        True  → liveness confirmed
        False → timeout or ESC pressed
    """
    blink_count   = 0
    frame_count   = 0
    consec_closed = 0
    eye_was_open  = True
    ratio_history = []
    HISTORY_LEN   = 4

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)
        gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frame_count += 1

        faces = face_cascade.detectMultiScale(
            gray, scaleFactor=1.2, minNeighbors=5, minSize=(80, 80)
        )

        if len(faces) > 0:
            fx, fy, fw, fh = max(faces, key=lambda f: f[2] * f[3])
            cv2.rectangle(frame, (fx, fy), (fx + fw, fy + fh), (0, 200, 255), 2)

            l_roi, l_coords = _extract_eye_roi(gray, fx, fy, fw, fh, LEFT_EYE_X,  EYE_Y)
            r_roi, r_coords = _extract_eye_roi(gray, fx, fy, fw, fh, RIGHT_EYE_X, EYE_Y)

            l_ratio = _eye_open_ratio(l_roi)
            r_ratio = _eye_open_ratio(r_roi)
            eye_ratio = (l_ratio + r_ratio) / 2.0

            for (x1, y1, x2, y2) in [l_coords, r_coords]:
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 1)

            # Smooth ratio over last N frames to reduce noise
            ratio_history.append(eye_ratio)
            if len(ratio_history) > HISTORY_LEN:
                ratio_history.pop(0)
            smoothed = float(np.mean(ratio_history))

            # ── Blink state machine ───────────────────────────────────────────
            eye_closed = smoothed < EYE_CLOSED_RATIO

            if eye_closed:
                consec_closed += 1
            else:
                if consec_closed >= CONSEC_CLOSED and not eye_was_open:
                    blink_count += 1
                    ratio_history.clear()
                consec_closed = 0

            eye_was_open = not eye_closed

            # Eye openness bar
            bar_w = min(200, int(smoothed * 200))
            bar_color = (0, 0, 255) if eye_closed else (0, 255, 0)
            cv2.rectangle(frame, (10, frame.shape[0] - 40),
                          (10 + bar_w, frame.shape[0] - 26), bar_color, -1)
            cv2.rectangle(frame, (10, frame.shape[0] - 40),
                          (210, frame.shape[0] - 26), (100, 100, 100), 1)
            cv2.putText(frame, "Eye openness", (215, frame.shape[0] - 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (160, 160, 160), 1)

            status_msg = "Please blink naturally"
        else:
            status_msg = "No face detected — move closer"

        # ── Overlay ───────────────────────────────────────────────────────────
        seconds_left  = max(0, (MAX_FRAMES - frame_count) // 30)
        prog_color    = (0, 255, 0) if blink_count >= REQUIRED_BLINKS else (0, 200, 255)

        cv2.putText(frame, f"Blinks: {blink_count} / {REQUIRED_BLINKS}",
                    (10, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.95, prog_color, 2)
        cv2.putText(frame, f"{status_msg}  ({seconds_left}s)",
                    (10, 66), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (200, 200, 200), 1)
        cv2.putText(frame, "ESC: Cancel",
                    (10, 92), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (120, 120, 120), 1)

        cv2.imshow("Liveness Check - Blink to continue", frame)

        if blink_count >= REQUIRED_BLINKS:
            cv2.waitKey(600)
            return True

        if frame_count >= MAX_FRAMES:
            break

        if cv2.waitKey(1) & 0xFF == 27:
            break

    return False