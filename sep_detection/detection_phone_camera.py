import cv2
import time
import uuid
import json
import requests
import os
from pathlib import Path
from queue import Queue
from threading import Thread, Lock
from datetime import datetime
from dotenv import load_dotenv
from ultralytics import YOLO

try:
    import serial
except ImportError:
    serial = None


BASE_DIR = Path(__file__).resolve().parents[1]
MODEL_PATH = BASE_DIR / "safe_detect 1.1.pt"
YUNET_PATH = BASE_DIR / "yunet.onnx"
TMP_DIR = BASE_DIR / "temp"
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "detection_phone_logs.json"

os.makedirs(TMP_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

SNAPSHOT_QUEUE = Queue()
LOG_LOCK = Lock()
SERIAL_CONNECTION = None
SERIAL_PORT = None
SERIAL_BAUD = 9600
SERIAL_LAST_RECONNECT_ATTEMPT = 0
SERIAL_RECONNECT_INTERVAL = 10  # seconds between reconnect attempts


def _validate_required_files():
    missing = [str(p) for p in (MODEL_PATH, YUNET_PATH) if not p.exists()]
    if missing:
        missing_text = "\n".join(f"- {p}" for p in missing)
        raise FileNotFoundError(
            "Required model file(s) are missing:\n"
            f"{missing_text}\n"
            "Ensure these files exist locally in the project root before running detection_phone_camera.py."
        )


def prompt_with_default(label, default_value):
    value = input(f"{label} [{default_value}]: ").strip()
    return value if value else default_value


def prompt_required(label, hint=""):
    while True:
        suffix = f" ({hint})" if hint else ""
        value = input(f"{label}{suffix}: ").strip()
        if value:
            return value
        print("Please enter a value.")


def prompt_user_id(default_user_id=""):
    while True:
        if default_user_id:
            entered = input(f"Enter user ID [{default_user_id}]: ").strip()
            entered = entered if entered else default_user_id
        else:
            entered = input("Enter user ID: ").strip()

        if entered.isdigit():
            return entered
        print("Please enter a valid numeric user ID.")


def prompt_snapshot_interval(default_value=10):
    while True:
        raw = input(f"Snapshot interval in seconds [{default_value}]: ").strip()
        if not raw:
            return default_value
        try:
            value = int(raw)
            if value > 0:
                return value
            print("Please enter a positive number.")
        except ValueError:
            print("Please enter a valid integer.")


def prompt_baud_rate(default_value=9600):
    while True:
        raw = input(f"Arduino baud rate [{default_value}]: ").strip()
        if not raw:
            return default_value
        try:
            value = int(raw)
            if value > 0:
                return value
            print("Please enter a positive number.")
        except ValueError:
            print("Please enter a valid integer.")


def prompt_serial_port():
    return input("Arduino serial port (example COM3 or /dev/ttyACM0, leave blank to skip): ").strip()


def open_serial_connection(port, baud_rate):
    if not port:
        return None

    if serial is None:
        print("PySerial is not installed. Arduino buzzer support is disabled.")
        return None

    try:
        connection = serial.Serial(port, baud_rate, timeout=1)
        time.sleep(2)
        print(f"Arduino connected on {port} at {baud_rate} baud")
        return connection
    except Exception as e:
        print(f"Could not open Arduino serial port: {e}")
        return None


def send_arduino_signal(signal_text):
    global SERIAL_CONNECTION, SERIAL_LAST_RECONNECT_ATTEMPT
    # Try to open connection lazily if we have port info
    now = time.time()
    if SERIAL_CONNECTION is None and SERIAL_PORT:
        # throttle reconnect attempts
        if now - SERIAL_LAST_RECONNECT_ATTEMPT > SERIAL_RECONNECT_INTERVAL:
            SERIAL_LAST_RECONNECT_ATTEMPT = now
            SERIAL_CONNECTION = open_serial_connection(SERIAL_PORT, SERIAL_BAUD)

    if SERIAL_CONNECTION is None:
        # connection not available
        return False

    try:
        SERIAL_CONNECTION.write((signal_text.strip() + "\n").encode("utf-8"))
        SERIAL_CONNECTION.flush()
        return True
    except PermissionError as e:
        print(f"Arduino serial write failed: {e}")
        try:
            SERIAL_CONNECTION.close()
        except Exception:
            pass
        SERIAL_CONNECTION = None
        return False
    except Exception as e:
        print(f"Arduino serial write failed: {e}")
        try:
            SERIAL_CONNECTION.close()
        except Exception:
            pass
        SERIAL_CONNECTION = None
        return False


def log_event(user_id, event_type, message, **data):
    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "event_type": event_type,
        "message": message,
        "user_id": user_id,
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
            print(f"Failed to write log: {e}")


def send_telegram_photo_with_message(token, chat_id, user_id, image_path, is_user=False, confidence=0.0):
    if not token or not chat_id:
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if is_user:
        caption = f"*Authorized User Detected*\nTime: `{now}`\nConfidence: `{confidence:.2%}`"
    else:
        caption = f"*INTRUDER ALERT! Unknown Person Detected!*\nTime: `{now}`\nConfidence: `{confidence:.2%}`"

    url = f"https://api.telegram.org/bot{token}/sendPhoto"

    with open(image_path, "rb") as photo:
        files = {"photo": photo}
        data = {
            "chat_id": chat_id,
            "caption": caption,
            "parse_mode": "Markdown",
        }
        try:
            res = requests.post(url, data=data, files=files, timeout=10)
            print(f"Telegram sent: {res.status_code}")
            log_event(user_id, "telegram_sent", "Telegram notification sent", status_code=res.status_code)
        except Exception as e:
            print(f"Telegram error: {e}")
            log_event(user_id, "telegram_error", "Telegram notification failed", error=str(e))


def verify_detected_face(user_id, verify_face_url, face_image_path):
    try:
        with open(face_image_path, "rb") as f:
            files = {"face_image": f}
            data = {"user_id": user_id}
            response = requests.post(verify_face_url, files=files, data=data, timeout=8)

            try:
                result = response.json()
            except ValueError:
                return True, False, 0.0, f"Non-JSON response ({response.status_code})"

            if response.status_code != 200:
                return True, False, float(result.get("confidence", 0.0)), f"HTTP {response.status_code}: {result}"

            should_alert = result.get("should_alert", True)
            is_user = result.get("is_user", False)
            confidence = float(result.get("confidence", 0.0))
            return should_alert, is_user, confidence, "ok"

    except Exception as e:
        return True, False, 0.0, str(e)


def face_worker(
    user_id,
    face_detector,
    api_url,
    verify_face_url,
    telegram_token,
    telegram_chat_id,
):
    while True:
        item = SNAPSHOT_QUEUE.get()
        if item is None:
            break

        frame, capture_time = item
        h, w = frame.shape[:2]
        face_detector.setInputSize((w, h))
        _, faces = face_detector.detect(frame)

        annotated_frame = frame.copy()
        face_crops = []
        if faces is not None:
            for face in faces:
                x, y, fw, fh = face[:4].astype(int)
                cv2.rectangle(annotated_frame, (x, y), (x + fw, y + fh), (0, 255, 0), 2)
                face_crop = frame[y:y + fh, x:x + fw]
                if face_crop.size > 0:
                    face_crops.append(face_crop)

        uid = str(uuid.uuid4())
        snap_path = os.path.join(TMP_DIR, f"{uid}_snapshot.jpg")
        face_path = os.path.join(TMP_DIR, f"{uid}_face.jpg")

        cv2.imwrite(snap_path, annotated_frame)
        if face_crops:
            cv2.imwrite(face_path, face_crops[0])
        else:
            face_path = snap_path

        try:
            with open(snap_path, "rb") as f1, open(face_path, "rb") as f2:
                files = {
                    "snapshot": f1,
                    "face_image": f2,
                }
                data = {
                    "uuid": uid,
                    "user_id": user_id,
                }
                res = requests.post(api_url, files=files, data=data, timeout=10)
                print(f"Sent to Django: {res.status_code}")
                log_event(
                    user_id,
                    "django_sent",
                    "Detection sent to Django",
                    status_code=res.status_code,
                    uuid=uid,
                    snapshot_path=snap_path,
                    face_path=face_path,
                )
        except Exception as e:
            print(f"Error sending to API: {e}")
            log_event(user_id, "django_error", "Failed to send detection to Django", error=str(e), uuid=uid)

        should_alert, is_user, confidence, verify_msg = verify_detected_face(user_id, verify_face_url, face_path)
        log_event(
            user_id,
            "verification_result",
            "Face verification completed",
            should_alert=should_alert,
            is_user=is_user,
            confidence=confidence,
            verify_message=verify_msg,
            uuid=uid,
        )

        if should_alert:
            send_telegram_photo_with_message(
                telegram_token,
                telegram_chat_id,
                user_id,
                snap_path,
                is_user=False,
                confidence=confidence,
            )
            send_arduino_signal("INTRUDER")
            print("INTRUDER ALERT SENT")
            log_event(user_id, "intruder_alert", "Intruder alert sent", uuid=uid, confidence=confidence, arduino_signal="INTRUDER")
        else:
            print(f"User {user_id} recognized. No intruder alert sent.")
            send_arduino_signal("USER")
            log_event(user_id, "authorized_user", "Authorized user recognized", uuid=uid, confidence=confidence, arduino_signal="USER")

        SNAPSHOT_QUEUE.task_done()


def main():
    _validate_required_files()

    load_dotenv()
    telegram_token = os.getenv("TELEGRAM_TOKEN", "").strip()
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    print("\n=== SafeDetect Phone Camera Mode ===")
    print("Example stream URLs:")
    print("- IP Webcam app: http://192.168.1.50:8080/video")
    print("- DroidCam app: http://192.168.1.50:4747/video")
    print("- RTSP stream: rtsp://username:password@192.168.1.50:554/stream")

    default_user_id = os.getenv("SAFEDETECT_USER_ID", "").strip()
    user_id = prompt_user_id(default_user_id)
    stream_url = prompt_required("Enter phone camera stream URL", "http://<phone-ip>:<port>/video")
    django_base_url = prompt_with_default("Enter Django base URL", "http://127.0.0.1:8000")
    snapshot_interval = prompt_snapshot_interval(default_value=10)
    serial_port = prompt_serial_port()
    baud_rate = prompt_baud_rate(default_value=9600)

    api_url = f"{django_base_url.rstrip('/')}/api/detections/"
    verify_face_url = f"{django_base_url.rstrip('/')}/api/verify-face/"

    model = YOLO(str(MODEL_PATH))
    face_detector = cv2.FaceDetectorYN.create(
        model=str(YUNET_PATH),
        config="",
        input_size=(320, 320),
        score_threshold=0.9,
        nms_threshold=0.3,
        top_k=5000,
    )

    log_event(
        user_id,
        "startup",
        "Phone camera detection session started",
        stream_url=stream_url,
        django_base_url=django_base_url,
        snapshot_interval=snapshot_interval,
        serial_port=serial_port,
        baud_rate=baud_rate,
    )

    global SERIAL_CONNECTION, SERIAL_PORT, SERIAL_BAUD
    SERIAL_PORT = serial_port
    SERIAL_BAUD = baud_rate
    SERIAL_CONNECTION = open_serial_connection(SERIAL_PORT, SERIAL_BAUD)

    print(f"\nConnecting to stream: {stream_url}")
    cap = cv2.VideoCapture(stream_url)
    if not cap.isOpened():
        print("Failed to open stream. Check your phone app URL and same Wi-Fi network.")
        log_event(user_id, "stream_error", "Failed to open stream", stream_url=stream_url)
        return

    worker = Thread(
        target=face_worker,
        args=(
            user_id,
            face_detector,
            api_url,
            verify_face_url,
            telegram_token,
            telegram_chat_id,
        ),
        daemon=True,
    )
    worker.start()

    print("Stream connected. Running in headless mode with no preview window.")
    log_event(user_id, "stream_connected", "Phone camera stream connected", stream_url=stream_url)
    last_snapshot_time = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            print("Stream frame read failed. Reconnecting...")
            log_event(user_id, "stream_warning", "Frame read failed; reconnecting")
            cap.release()
            time.sleep(2)
            cap = cv2.VideoCapture(stream_url)
            continue

        results = model.predict(frame, classes=[0, 1, 2, 3, 4, 5], conf=0.4)
        person_detected = False

        for r in results:
            if len(r.boxes) > 0:
                person_detected = True
                for box in r.boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
                break

        current_time = time.time()
        if person_detected and (current_time - last_snapshot_time > snapshot_interval):
            SNAPSHOT_QUEUE.put((frame.copy(), current_time))
            last_snapshot_time = current_time

        # No preview window is shown to avoid lag on low-resource systems.
        # The script runs headless and only prints connection/state messages.

    cap.release()
    if SERIAL_CONNECTION is not None:
        try:
            SERIAL_CONNECTION.close()
        except Exception:
            pass
    SNAPSHOT_QUEUE.put(None)
    log_event(user_id, "shutdown", "Phone camera detection session ended")


if __name__ == "__main__":
    main()
