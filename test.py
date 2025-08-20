import cv2
import os
import numpy as np
from datetime import datetime
import time
# Folder for saving faces
DATASET_DIR = "faces_dataset"
os.makedirs(DATASET_DIR, exist_ok=True)

"""Simple face dataset & (optional) LBPH recognition demo.

If OpenCV was installed without the contrib modules (opencv-python), the
cv2.face namespace will be missing and recognition won't work. We degrade
gracefully and still allow dataset collection so that once the user installs
opencv-contrib-python, recognition can start immediately without code changes.
"""

# Try to create recognizer (needs opencv-contrib-python). Fall back gracefully.
try:
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    HAVE_RECOGNIZER = True
except AttributeError:
    recognizer = None
    HAVE_RECOGNIZER = False
    print("[INFO] OpenCV built without 'face' module. Install 'opencv-contrib-python' to enable LBPH recognition.")

# Load existing dataset
def train_recognizer():
    faces, labels = [], []
    label_map = {}
    i = 0
    for filename in os.listdir(DATASET_DIR):
        if filename.endswith(".jpg"):
            path = os.path.join(DATASET_DIR, filename)
            img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
            label = filename.split("_")[0]  
            if label not in label_map:
                label_map[label] = i
                i += 1
            faces.append(img)
            labels.append(label_map[label])
    if faces and HAVE_RECOGNIZER:
        recognizer.train(faces, np.array(labels))
    return {v: k for k, v in label_map.items()}

label_dict = train_recognizer()

# Start camera
cap = cv2.VideoCapture(0)
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

SAMPLE_SIZE = 20  # frames to capture per new identity
FACE_SIZE = (200, 200)  # normalization size
THRESHOLD_CONFIDENCE = 70  # LBPH: lower is better; only show if <= this value
SHOW_UNKNOWN = False  # If False, skip drawing boxes for low-confidence / unknown faces

print("[INFO] Controls: q=quit, a=add person, r=retrain, +/- adjust threshold, u toggle unknown visibility")
print(f"[INFO] Current confidence threshold: {THRESHOLD_CONFIDENCE}")

def capture_new_person(name: str):
    """Capture SAMPLE_SIZE face crops for a new person and save to dataset."""
    count = 0
    print(f"[CAPTURE] Collecting {SAMPLE_SIZE} samples for '{name}' ... Look at the camera.")
    while count < SAMPLE_SIZE:
        time.sleep(1)
        ret2, frm = cap.read()
        if not ret2:
            continue
        gray2 = cv2.cvtColor(frm, cv2.COLOR_BGR2GRAY)
        dets = face_cascade.detectMultiScale(gray2, 1.3, 5)
        if len(dets) == 0:
            cv2.putText(frm, "No face detected", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,255), 2)
        else:
            # Take the largest face
            x, y, w, h = max(dets, key=lambda b: b[2]*b[3])
            roi = gray2[y:y+h, x:x+w]
            roi_resized = cv2.resize(roi, FACE_SIZE)
            filename = f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.jpg"
            cv2.imwrite(os.path.join(DATASET_DIR, filename), roi_resized)
            count += 1
            cv2.rectangle(frm, (x, y), (x+w, y+h), (0,255,0), 2)
            cv2.putText(frm, f"{name} {count}/{SAMPLE_SIZE}", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)
        cv2.imshow("Face Recognition", frm)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            return False  # user aborted
    print(f"[CAPTURE] Done capturing for '{name}'.")
    return True

while True:
    ret, frame = cap.read()
    if not ret:
        continue
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)

    for idx, (x, y, w, h) in enumerate(faces):
        face_img = gray[y:y+h, x:x+w]
        face_norm = cv2.resize(face_img, FACE_SIZE)

        if HAVE_RECOGNIZER and recognizer is not None and len(label_dict) > 0:
            try:
                label, confidence = recognizer.predict(face_norm)
                name = label_dict.get(label, "Unknown")
                is_high_conf = confidence <= THRESHOLD_CONFIDENCE and name != "Unknown"
                if is_high_conf:
                    text = f"{name}:{int(confidence)}"
                else:
                    text = "Unknown"
            except Exception:
                text = "Unknown"
        else:
            text = "Unknown"
        # Skip drawing for unknown / low-confidence if configured
        if text == "Unknown" and not SHOW_UNKNOWN:
            continue

        color = (0, 255, 0) if text != "Unknown" else (0, 165, 255)
        cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)
        cv2.putText(frame, f"{idx}:{text}", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    cv2.putText(frame, f"a:add r:retrain +/-:thresh({THRESHOLD_CONFIDENCE}) u:unk({int(SHOW_UNKNOWN)}) q:quit", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255,255,255), 2)
    cv2.imshow("Face Recognition", frame)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    elif key == ord('r'):
        print('[ACTION] Retraining from current dataset...')
        label_dict = train_recognizer()
        print(f"[ACTION] Retrain complete: {len(label_dict)} identities.")
    elif key == ord('a'):
        if not HAVE_RECOGNIZER:
            print("[WARN] Recognizer unavailable (install opencv-contrib-python). You can still collect data.")
        name = input("Enter new person's name: ").strip()
        if name:
            if capture_new_person(name):
                label_dict = train_recognizer()
                print(f"[INFO] Added '{name}'. Known identities: {len(label_dict)}")
            else:
                print("[INFO] Capture aborted.")
    elif key in (43, ord('=')):  # '+' (some keyboards produce '=' without shift)
        THRESHOLD_CONFIDENCE += 5
        print(f"[TUNE] Threshold increased to {THRESHOLD_CONFIDENCE}")
    elif key == ord('-'):
        THRESHOLD_CONFIDENCE = max(5, THRESHOLD_CONFIDENCE - 5)
        print(f"[TUNE] Threshold decreased to {THRESHOLD_CONFIDENCE}")
    elif key == ord('u'):
        SHOW_UNKNOWN = not SHOW_UNKNOWN
        print(f"[TUNE] SHOW_UNKNOWN set to {SHOW_UNKNOWN}")

cap.release()
cv2.destroyAllWindows()
