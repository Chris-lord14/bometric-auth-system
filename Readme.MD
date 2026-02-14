# Smart Biometric Authentication System

A face recognition login system built with Python and OpenCV — **no dlib required**.

---

## Quick Setup

### 1. Install dependencies (one command)
```powershell
pip install opencv-contrib-python numpy scikit-learn
```

> ⚠️ **Important:** Install `opencv-contrib-python`, NOT `opencv-python`.
> The `contrib` version includes the LBPH Face Recognizer used by this project.
> If you have `opencv-python` installed already, uninstall it first:
> ```
> pip uninstall opencv-python
> pip install opencv-contrib-python
> ```

---

### 2. Run the app
```powershell
python main.py
```

---

## How to Use

### Step 1 — Register a User
1. Enter **Full Name** and **Username** in the fields
2. Click **Register User** — your webcam will open
3. Look at the camera and press **SPACE** to capture images (30 needed)
4. A green box means a face was detected — only those frames are saved
5. Press **ESC** to cancel

### Step 2 — Train the Model
1. Click **Train Model**
2. Wait a moment — it processes all registered users' images
3. A success message will confirm how many users/images were used

### Step 3 — Login
1. Click **Login** — webcam opens
2. Look at the camera — it will recognize your face automatically
3. Match above 80% confidence = login granted
4. Press **ESC** to cancel

### Step 4 — View Logs
- Click **View Logs** to see recent login attempts, timestamps, and confidence scores

---

## Project Structure
```
project/
├── main.py            # Main GUI window
├── register.py        # User registration + webcam capture
├── train_model.py     # LBPH model training
├── login.py           # Face recognition login
├── logger.py          # Access log (DB + text file)
├── database.py        # SQLite setup
├── requirements.txt
│
├── datasets/          # Auto-created: one folder per user
│   └── username/
│       ├── 1.jpg
│       └── ...
├── models/            # Auto-created on training
│   ├── face_model.yml
│   └── label_map.pkl
├── logs/              # Auto-created on first login attempt
│   └── access.log
└── auth.db            # SQLite database
```

---

## Why OpenCV instead of dlib/face_recognition?

| Library | Pros | Cons |
|---|---|---|
| `dlib` / `face_recognition` | Very accurate | Requires C++ compiler, CMake; fails on Python 3.14 |
| **OpenCV LBPH** (this project) | Works out-of-the-box, fast | Slightly less accurate in varied lighting |

For a final year project, OpenCV LBPH is reliable and well-documented.

---

## Troubleshooting

**"No module named cv2.face"** → You have `opencv-python` not `opencv-contrib-python`. Reinstall.

**"Cannot access webcam"** → Check that no other app is using your camera. Try `cv2.VideoCapture(1)` in login.py/register.py if you have multiple cameras.

**Low accuracy at login** → Register more images in varied lighting. Retrain after adding new users.