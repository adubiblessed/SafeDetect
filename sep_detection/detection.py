import cv2
import time
import uuid
import requests
import json
import os
from pathlib import Path
from queue import Queue
from threading import Thread, Lock
from datetime import datetime
from dotenv import load_dotenv
from ultralytics import YOLO  


BASE_DIR = Path(__file__).resolve().parents[1]
MODEL_PATH = BASE_DIR / "safe_detect 1.1.pt"
YUNET_PATH = BASE_DIR / "yunet.onnx"


def _validate_required_files():
    missing = [str(p) for p in (MODEL_PATH, YUNET_PATH) if not p.exists()]
    if missing:
        missing_text = "\n".join(f"- {p}" for p in missing)
        raise FileNotFoundError(
            "Required model file(s) are missing:\n"
            f"{missing_text}\n"
            "Ensure these files exist locally in the project root before running detection.py."
        )


_validate_required_files()

model = YOLO(str(MODEL_PATH))  


face_detector = cv2.FaceDetectorYN.create(
    model=str(YUNET_PATH),
    config="",
    input_size=(320, 320),
    score_threshold=0.9,
    nms_threshold=0.3,
    top_k=5000
)


SNAPSHOT_INTERVAL = 10  
API_URL = "http://127.0.0.1:8000/api/detections/"
VERIFY_FACE_URL = "http://127.0.0.1:8000/api/verify-face/"
TMP_DIR = BASE_DIR / "temp"
os.makedirs(TMP_DIR, exist_ok=True)
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "detection_logs.json"
os.makedirs(LOG_DIR, exist_ok=True)

LOG_LOCK = Lock()


load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def prompt_for_user_id():
    default_user_id = os.getenv('SAFEDETECT_USER_ID', '').strip()

    while True:
        prompt_text = "Enter the user ID for this detection session"
        if default_user_id:
            prompt_text += f" [{default_user_id}]"
        prompt_text += ": "

        entered_user_id = input(prompt_text).strip()
        if not entered_user_id and default_user_id:
            entered_user_id = default_user_id

        if entered_user_id.isdigit():
            return entered_user_id

        print("⚠️  Please enter a valid numeric user ID.")


# Ask for the user ID at startup so detections are always tied to one account
USER_ID = prompt_for_user_id()


def log_event(event_type, message, **data):
    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "event_type": event_type,
        "message": message,
        "user_id": USER_ID,
        **data,
    }

    with LOG_LOCK:
        try:
            if LOG_FILE.exists():
                try:
                    existing = json.loads(LOG_FILE.read_text(encoding="utf-8"))
                    if not isinstance(existing, list):
                        existing = []
                except json.JSONDecodeError:
                    existing = []
            else:
                existing = []

            existing.append(entry)
            LOG_FILE.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"❌ Failed to write log entry: {e}")


# === Telegram Sender ===
def send_telegram_photo_with_message(image_path, is_user=False, confidence=0.0):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if is_user:
        caption = f"*✅ Authorized User Detected*\nTime: `{now}`\nConfidence: `{confidence:.2%}`"
    else:
        caption = f"*🚨 INTRUDER ALERT! Unknown Person Detected!*\nTime: `{now}`\nConfidence: `{confidence:.2%}`"
    
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
            print(f"📤 Telegram sent: {res.status_code}")
            log_event(
                "telegram_sent",
                "Telegram notification sent",
                image_path=str(image_path),
                is_user=is_user,
                confidence=confidence,
                status_code=res.status_code,
            )
        except Exception as e:
            print(f"❌ Telegram error: {e}")
            log_event("telegram_error", "Telegram notification failed", image_path=str(image_path), error=str(e))


def verify_detected_face(face_image_path):
    """
    Verify if detected face belongs to the authenticated user.
    
    Returns:
        Tuple: (should_alert: bool, is_user: bool, confidence: float)
    """
    if not USER_ID:
        print("⚠️  No USER_ID set. Skipping face verification. Will send alert.")
        log_event("verification_skipped", "Face verification skipped because no user id was provided", face_image_path=str(face_image_path))
        return True, False, 0.0
    
    try:
        with open(face_image_path, 'rb') as f:
            files = {'face_image': f}
            data = {'user_id': USER_ID}
            
            response = requests.post(VERIFY_FACE_URL, files=files, data=data, timeout=5)

            try:
                result = response.json()
            except ValueError:
                print(f"❌ Face verification returned non-JSON response: {response.status_code}")
                print(f"Response body: {response.text[:500]}")
                log_event(
                    "verification_error",
                    "Face verification returned non-JSON response",
                    face_image_path=str(face_image_path),
                    status_code=response.status_code,
                    response_body=response.text[:500],
                )
                return True, False, 0.0

            if response.status_code != 200:
                print(f"❌ Face verification failed: {response.status_code}")
                print(f"Response body: {result}")
                log_event(
                    "verification_error",
                    "Face verification returned an error status",
                    face_image_path=str(face_image_path),
                    status_code=response.status_code,
                    response_body=result,
                )
                return True, False, float(result.get('confidence', 0.0)) if isinstance(result, dict) else 0.0
            
            should_alert = result.get('should_alert', True)
            is_user = result.get('is_user', False)
            confidence = result.get('confidence', 0.0)
            
            print(f"🔍 Face verification: User={is_user}, Alert={should_alert}, Confidence={confidence:.2%}")
            log_event(
                "verification_result",
                "Face verification completed",
                face_image_path=str(face_image_path),
                should_alert=should_alert,
                is_user=is_user,
                confidence=confidence,
            )
            
            return should_alert, is_user, confidence
            
    except Exception as e:
        print(f"❌ Face verification error: {e}")
        log_event("verification_error", "Face verification failed with exception", face_image_path=str(face_image_path), error=str(e))
        # Safe default: send alert if verification fails
        return True, False, 0.0


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
                if USER_ID:
                    data['user_id'] = USER_ID
                res = requests.post(API_URL, files=files, data=data)
                print(f"📡 Sent to Django: {res.status_code}")
                log_event(
                    "django_sent",
                    "Detection sent to Django",
                    uuid=uid,
                    snapshot_path=snap_path,
                    face_path=face_path,
                    status_code=res.status_code,
                )
        except Exception as e:
            print(f"❌ Error sending to API: {e}")
            log_event("django_error", "Failed to send detection to Django", uuid=uid, snapshot_path=snap_path, face_path=face_path, error=str(e))

        # === Verify Face & Send Alert ===
        should_alert, is_user, confidence = verify_detected_face(face_path)
        
        if should_alert:
            # Only send Telegram alert for unknown faces (intruders)
            send_telegram_photo_with_message(snap_path, is_user=False, confidence=confidence)
            print("🚨 INTRUDER ALERT SENT")
            log_event(
                "intruder_alert",
                "Intruder alert sent",
                uuid=uid,
                snapshot_path=snap_path,
                face_path=face_path,
                confidence=confidence,
            )
        else:
            # Recognized user - send info message (optional)
            print(f"✅ User {USER_ID} recognized. No alert sent.")
            log_event(
                "authorized_user",
                "Authorized user detected; alert suppressed",
                uuid=uid,
                snapshot_path=snap_path,
                face_path=face_path,
                confidence=confidence,
            )
            if TELEGRAM_TOKEN:  # Only send verification telegram if token exists
                try:
                    send_telegram_photo_with_message(snap_path, is_user=True, confidence=confidence)
                except:
                    pass  # Silently fail for verification messages

        snapshot_queue.task_done()


# === Start Worker Thread ===
Thread(target=face_worker, daemon=True).start()

# === Open Webcam ===
print(f"🎥 Starting SafeDetect - User ID: {USER_ID if USER_ID else 'NOT SET (no face verification)'}")
print(f"💡 To enable face verification, set SAFEDETECT_USER_ID environment variable")
log_event("startup", "SafeDetect camera session started")

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
