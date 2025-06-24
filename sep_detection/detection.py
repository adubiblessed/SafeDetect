import cv2
import time
import uuid
import requests
import os
from queue import Queue
from threading import Thread
from datetime import datetime
from dotenv import load_dotenv
from ultralytics import YOLO  


model = YOLO("safe_detect 1.1.pt")  


face_detector = cv2.FaceDetectorYN.create(
    model="yunet.onnx",
    config="",
    input_size=(320, 320),
    score_threshold=0.9,
    nms_threshold=0.3,
    top_k=5000
)


SNAPSHOT_INTERVAL = 10  
API_URL = "http://127.0.0.1:8000/api/detections/"
TMP_DIR = "temp"
os.makedirs(TMP_DIR, exist_ok=True)


load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


# === Telegram Sender ===
def send_telegram_photo_with_message(image_path):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    caption = f"*🚨 Person Detected!*\nTime: `{now}`"
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto'

    with open(image_path, 'rb') as photo:
        files = {'photo': photo}
        data = {
            'chat_id': TELEGRAM_CHAT_ID,
            'caption': caption,
            'parse_mode': 'Markdown'
        }
        try:
            res = requests.post(url, data=data, files=files)
            print("📤 Telegram sent:", res.status_code)
        except Exception as e:
            print("❌ Telegram error:", e)


# === Snapshot Queue ===
snapshot_queue = Queue()


# === Background Worker ===
def face_worker():
    while True:
        item = snapshot_queue.get()
        if item is None:
            break

        frame, timestamp = item
        h, w = frame.shape[:2]
        face_detector.setInputSize((w, h))
        _, faces = face_detector.detect(frame)

        # Annotate faces
        annotated_frame = frame.copy()
        face_crops = []
        if faces is not None:
            for face in faces:
                x, y, fw, fh = face[:4].astype(int)
                cv2.rectangle(annotated_frame, (x, y), (x+fw, y+fh), (0, 255, 0), 2)
                face_crop = frame[y:y+fh, x:x+fw]
                face_crops.append(face_crop)

        # Save images
        uid = str(uuid.uuid4())
        snap_path = os.path.join(TMP_DIR, f"{uid}_snapshot.jpg")
        face_path = os.path.join(TMP_DIR, f"{uid}_face.jpg")
        cv2.imwrite(snap_path, annotated_frame)
        if face_crops:
            cv2.imwrite(face_path, face_crops[0])
        else:
            face_path = snap_path  # fallback if no face

        # === Send to Django ===
        try:
            with open(snap_path, 'rb') as f1, open(face_path, 'rb') as f2:
                files = {
                    'snapshot': f1,
                    'face_image': f2,
                }
                data = {'uuid': uid}
                res = requests.post(API_URL, files=files, data=data)
                print("📡 Sent to Django:", res.status_code)
        except Exception as e:
            print("❌ Error sending to API:", e)

        # === Send to Telegram ===
        send_telegram_photo_with_message(snap_path)

        snapshot_queue.task_done()


# === Start Worker Thread ===
Thread(target=face_worker, daemon=True).start()

# === Open Webcam ===
cap = cv2.VideoCapture(0)
last_snapshot_time = 0

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    
    results = model.predict(frame, classes=[0,1,2,3,4,5], conf=0.4)
    face_detected = False

    for r in results:
        if len(r.boxes) > 0:
            face_detected = True
            for box in r.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
            break

   
    current_time = time.time()
    if face_detected and (current_time - last_snapshot_time > SNAPSHOT_INTERVAL):
        snapshot_queue.put((frame.copy(), current_time))
        last_snapshot_time = current_time

    # Display webcam
    cv2.imshow("SafeDetect Camera", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break


cap.release()
cv2.destroyAllWindows()
snapshot_queue.put(None)
