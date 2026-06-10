import cv2
import time
import uuid
import json
import requests
import os
from pathlib import Path
from queue import Queue, Full
from threading import Thread, Lock
from datetime import datetime
from dotenv import load_dotenv
from ultralytics import YOLO
from urllib.parse import urlparse

try:
    import torch
except Exception:
    torch = None

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

INFERENCE_QUEUE = Queue(maxsize=2)
UPLOAD_QUEUE = Queue()
LOG_LOCK = Lock()
PREVIEW_LOCK = Lock()
LATEST_PREVIEW_FRAME = None
SERIAL_CONNECTION = None
SERIAL_PORT = None
SERIAL_BAUD = 9600
SERIAL_LAST_RECONNECT_ATTEMPT = 0
SERIAL_RECONNECT_INTERVAL = 10  # seconds between reconnect attempts


def _env_bool(name, default=False):
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def pick_compute_device(preferred="auto"):
    preferred = (preferred or "auto").strip().lower()
    if preferred.startswith("cuda"):
        if torch is not None and torch.cuda.is_available():
            return "cuda:0", True
        return "cpu", False

    if preferred == "cpu":
        return "cpu", False

    # auto mode
    if torch is not None and torch.cuda.is_available():
        return "cuda:0", True
    return "cpu", False


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


def normalize_stream_url(raw_url):
    url = raw_url.strip()
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("Stream URL must include scheme and host, e.g. http://192.168.1.50:8080/video")

    if parsed.scheme in {"http", "https"}:
        path = parsed.path or ""
        if path in {"", "/"}:
            url = url.rstrip("/") + "/video"
    return url


def close_serial_connection():
    global SERIAL_CONNECTION
    if SERIAL_CONNECTION is not None:
        try:
            SERIAL_CONNECTION.close()
        except Exception:
            pass
        SERIAL_CONNECTION = None


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


def inference_worker(
    model,
    user_id,
    face_detector,
    inference_queue,
    upload_queue,
    device,
    imgsz,
    use_half,
    snapshot_interval,
):
    global LATEST_PREVIEW_FRAME
    last_alert_time = 0.0

    while True:
        item = inference_queue.get()
        if item is None:
            inference_queue.task_done()
            break

        frame, capture_time = item

        # Run YOLO inference in this dedicated thread
        try:
            t_inf_start = time.time()
            results = model.predict(
                frame,
                classes=[0, 1, 2, 3, 4, 5],
                conf=0.4,
                imgsz=imgsz,
                device=device,
                half=use_half,
                verbose=False,
            )
            t_inf_end = time.time()
            inference_time = t_inf_end - t_inf_start
        except Exception as e:
            print(f"Inference error: {e}")
            inference_queue.task_done()
            continue

        person_detected = False
        annotated_frame = frame.copy()
        for r in results:
            if len(r.boxes) > 0:
                person_detected = True
                for box in r.boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
                break

        # Publish latest annotated frame for preview window.
        with PREVIEW_LOCK:
            LATEST_PREVIEW_FRAME = annotated_frame

        if person_detected and (time.time() - last_alert_time >= snapshot_interval):
            # Face detection and snapshot creation
            h, w = frame.shape[:2]
            t_fd_start = time.time()
            face_detector.setInputSize((w, h))
            _, faces = face_detector.detect(frame)
            t_fd_end = time.time()
            face_detect_time = t_fd_end - t_fd_start

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

            t_save_start = time.time()
            cv2.imwrite(snap_path, annotated_frame)
            if face_crops:
                cv2.imwrite(face_path, face_crops[0])
            else:
                face_path = snap_path
            t_save_end = time.time()
            save_time = t_save_end - t_save_start

            upload_queue.put(
                {
                    "uid": uid,
                    "snap_path": snap_path,
                    "face_path": face_path,
                    "user_id": user_id,
                    "capture_time": capture_time,
                    "timings": {
                        "inference": inference_time,
                        "face_detect": face_detect_time,
                        "save": save_time,
                    },
                }
            )
            last_alert_time = time.time()

        inference_queue.task_done()


def upload_worker(
    upload_queue,
    api_url,
    verify_face_url,
    telegram_token,
    telegram_chat_id,
):
    while True:
        item = upload_queue.get()
        if item is None:
            break

        uid = item.get("uid")
        snap_path = item.get("snap_path")
        face_path = item.get("face_path")
        user_id = item.get("user_id")
        timings = item.get("timings", {})

        try:
            t_api_start = time.time()
            with open(snap_path, "rb") as f1, open(face_path, "rb") as f2:
                files = {"snapshot": f1, "face_image": f2}
                data = {"uuid": uid, "user_id": user_id}
                res = requests.post(api_url, files=files, data=data, timeout=10)
            t_api_end = time.time()
            api_time = t_api_end - t_api_start
            print(f"Sent to Django: {res.status_code} (api_time={api_time:.2f}s)")
            log_event(
                user_id,
                "django_sent",
                "Detection sent to Django",
                status_code=res.status_code,
                uuid=uid,
                snapshot_path=snap_path,
                face_path=face_path,
                api_time=api_time,
                inference_time=timings.get("inference"),
                face_detect_time=timings.get("face_detect"),
                save_time=timings.get("save"),
            )
        except Exception as e:
            print(f"Error sending to API: {e}")
            log_event(user_id, "django_error", "Failed to send detection to Django", error=str(e), uuid=uid)
            api_time = None

        t_verify_start = time.time()
        should_alert, is_user, confidence, verify_msg = verify_detected_face(user_id, verify_face_url, face_path)
        t_verify_end = time.time()
        verify_time = t_verify_end - t_verify_start
        log_event(
            user_id,
            "verification_result",
            "Face verification completed",
            should_alert=should_alert,
            is_user=is_user,
            confidence=confidence,
            verify_message=verify_msg,
            verify_time=verify_time,
            uuid=uid,
        )

        if should_alert:
            t_tel_start = time.time()
            send_telegram_photo_with_message(
                telegram_token,
                telegram_chat_id,
                user_id,
                snap_path,
                is_user=False,
                confidence=confidence,
            )
            t_tel_end = time.time()
            telegram_time = t_tel_end - t_tel_start

            t_ard_start = time.time()
            send_arduino_signal("INTRUDER")
            t_ard_end = time.time()
            arduino_time = t_ard_end - t_ard_start

            print("INTRUDER ALERT SENT")
            log_event(user_id, "intruder_alert", "Intruder alert sent", uuid=uid, confidence=confidence, arduino_signal="INTRUDER", telegram_time=telegram_time, arduino_time=arduino_time)
        else:
            print(f"User {user_id} recognized. No intruder alert sent.")
            t_ard_start = time.time()
            send_arduino_signal("USER")
            t_ard_end = time.time()
            arduino_time = t_ard_end - t_ard_start
            log_event(user_id, "authorized_user", "Authorized user recognized", uuid=uid, confidence=confidence, arduino_signal="USER", arduino_time=arduino_time)

        upload_queue.task_done()


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
    try:
        stream_url = normalize_stream_url(stream_url)
    except ValueError as e:
        print(e)
        return
    django_base_url = prompt_with_default("Enter Django base URL", "http://127.0.0.1:8000")
    snapshot_interval = prompt_snapshot_interval(default_value=10)
    serial_port = prompt_serial_port()
    baud_rate = prompt_baud_rate(default_value=9600)

    api_url = f"{django_base_url.rstrip('/')}/api/detections/"
    verify_face_url = f"{django_base_url.rstrip('/')}/api/verify-face/"

    preferred_device = os.getenv("SAFEDETECT_DEVICE", "auto")
    preview_enabled = _env_bool("SAFEDETECT_PREVIEW", default=True)
    try:
        imgsz = int(os.getenv("SAFEDETECT_IMGSZ", "320"))
    except ValueError:
        imgsz = 320

    configured_model_path = os.getenv("SAFEDETECT_MODEL_PATH", "").strip()
    resolved_model_path = Path(configured_model_path) if configured_model_path else MODEL_PATH
    if not resolved_model_path.is_absolute():
        resolved_model_path = BASE_DIR / resolved_model_path

    if not resolved_model_path.exists():
        raise FileNotFoundError(
            f"Configured model file not found: {resolved_model_path}\n"
            "Set SAFEDETECT_MODEL_PATH to your trained model path."
        )

    device, use_cuda = pick_compute_device(preferred_device)
    use_half = bool(use_cuda)

    model = YOLO(str(resolved_model_path))
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
        model_path=str(resolved_model_path),
        device=device,
        imgsz=imgsz,
        preview_enabled=preview_enabled,
    )

    global SERIAL_CONNECTION, SERIAL_PORT, SERIAL_BAUD
    SERIAL_PORT = serial_port
    SERIAL_BAUD = baud_rate
    SERIAL_CONNECTION = open_serial_connection(SERIAL_PORT, SERIAL_BAUD)

    print(f"\nConnecting to stream: {stream_url}")
    cap = cv2.VideoCapture(stream_url)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    if not cap.isOpened():
        print("Failed to open stream. Check your phone app URL and same Wi-Fi network.")
        log_event(user_id, "stream_error", "Failed to open stream", stream_url=stream_url)
        close_serial_connection()
        return

    # Start inference and upload workers to decouple capture, inference and network IO
    inference_thread = Thread(
        target=inference_worker,
        args=(model, user_id, face_detector, INFERENCE_QUEUE, UPLOAD_QUEUE, device, imgsz, use_half, snapshot_interval),
        daemon=True,
    )
    inference_thread.start()

    upload_thread = Thread(
        target=upload_worker,
        args=(UPLOAD_QUEUE, api_url, verify_face_url, telegram_token, telegram_chat_id),
        daemon=True,
    )
    upload_thread.start()

    if preview_enabled:
        print("Stream connected. Preview window enabled. Press 'q' to quit.")
    else:
        print("Stream connected. Running in headless mode with no preview window.")

    print(f"Inference device: {device} | half precision: {use_half} | imgsz: {imgsz} | model: {resolved_model_path.name}")
    log_event(user_id, "stream_connected", "Phone camera stream connected", stream_url=stream_url)

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            print("Stream frame read failed. Reconnecting...")
            log_event(user_id, "stream_warning", "Frame read failed; reconnecting")
            cap.release()
            time.sleep(2)
            cap = cv2.VideoCapture(stream_url)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            continue

        current_time = time.time()
        try:
            INFERENCE_QUEUE.put_nowait((frame.copy(), current_time))
        except Full:
            try:
                INFERENCE_QUEUE.get_nowait()
                INFERENCE_QUEUE.task_done()
            except Exception:
                pass
            try:
                INFERENCE_QUEUE.put_nowait((frame.copy(), current_time))
            except Exception:
                pass

        if preview_enabled:
            frame_to_show = frame
            with PREVIEW_LOCK:
                if LATEST_PREVIEW_FRAME is not None:
                    frame_to_show = LATEST_PREVIEW_FRAME
            cv2.imshow("SafeDetect Phone Camera Preview", frame_to_show)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                print("Quit signal received from preview window.")
                break

    cap.release()
    if preview_enabled:
        cv2.destroyAllWindows()
    close_serial_connection()
    # Signal workers to shut down
    try:
        INFERENCE_QUEUE.put(None)
    except Exception:
        pass
    try:
        UPLOAD_QUEUE.put(None)
    except Exception:
        pass
    log_event(user_id, "shutdown", "Phone camera detection session ended")


if __name__ == "__main__":
    main()
