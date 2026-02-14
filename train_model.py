import os
import cv2
import pickle
import numpy as np

MODEL_PATH     = "models/face_model.yml"
LABEL_MAP_PATH = "models/label_map.pkl"

CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
face_cascade = cv2.CascadeClassifier(CASCADE_PATH)


def train_model():
    faces  = []
    labels = []
    label_map     = {}
    label_counter = 0

    dataset_dir = "datasets"

    if not os.path.exists(dataset_dir):
        return False, "Dataset folder not found! Please register users first."

    user_folders = [f for f in os.listdir(dataset_dir)
                    if os.path.isdir(os.path.join(dataset_dir, f))]

    if not user_folders:
        return False, "No users found. Please register at least one user."

    for user_folder in user_folders:
        user_path = os.path.join(dataset_dir, user_folder)
        label_map[label_counter] = user_folder
        images_loaded = 0

        for img_name in os.listdir(user_path):
            img = cv2.imread(os.path.join(user_path, img_name))
            if img is None:
                continue

            gray   = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            detected = face_cascade.detectMultiScale(gray, 1.3, 5)

            for (x, y, w, h) in detected:
                face_roi = cv2.resize(gray[y:y + h, x:x + w], (100, 100))
                faces.append(face_roi)
                labels.append(label_counter)
                images_loaded += 1

        print(f"[Train] {user_folder}: {images_loaded} face(s) loaded.")
        label_counter += 1

    if not faces:
        return False, "No face data found. Try re-registering users."

    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.train(faces, np.array(labels))

    os.makedirs("models", exist_ok=True)
    recognizer.save(MODEL_PATH)

    with open(LABEL_MAP_PATH, "wb") as f:
        pickle.dump(label_map, f)

    return True, (f"Model trained successfully!\n"
                  f"{len(label_map)} user(s), {len(faces)} face image(s) used.")