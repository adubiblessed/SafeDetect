import os
import sys
import time
import subprocess
from pathlib import Path
from urllib.parse import urlparse

try:
    import torch
except Exception:
    torch = None


BASE_DIR = Path(__file__).resolve().parent


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


def prompt_snapshot_interval(default_value=6):
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


def detect_best_device():
    if torch is not None and torch.cuda.is_available():
        return "cuda:0"
    return "cpu"


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


def prompt_model_file(base_dir):
    default_model = "safe_detect 1.1.pt"
    while True:
        model_input = prompt_with_default("Model file", default_model)
        model_path = Path(model_input)
        if not model_path.is_absolute():
            model_path = base_dir / model_path

        if model_path.exists() and model_path.is_file():
            return str(model_path)

        print(f"Model file not found: {model_path}")
        print("Please enter the exact path or filename of your trained model.")


def main():
    os.chdir(BASE_DIR)

    print("\n=== SafeDetect One-Command Starter ===")
    print("This starts Django and phone detection together with low-latency settings.")

    default_user_id = os.getenv("SAFEDETECT_USER_ID", "").strip()
    user_id = prompt_user_id(default_user_id)
    raw_stream_url = prompt_required("Enter phone camera stream URL", "http://<phone-ip>:<port>/video")
    try:
        stream_url = normalize_stream_url(raw_stream_url)
    except ValueError as e:
        print(e)
        return

    server_host = prompt_with_default("Django host", "127.0.0.1")
    server_port = prompt_with_default("Django port", "8000")
    django_base_url = f"http://{server_host}:{server_port}"

    snapshot_interval = prompt_snapshot_interval(default_value=6)
    serial_port = input("Arduino serial port (example COM3, leave blank to skip): ").strip()
    baud_rate = prompt_baud_rate(default_value=9600)

    model_path = prompt_model_file(BASE_DIR)
    imgsz = prompt_with_default("Inference image size", "320")

    device = detect_best_device()
    print(f"Detected compute device: {device}")

    env = os.environ.copy()
    env["SAFEDETECT_DEVICE"] = device
    env["SAFEDETECT_PREVIEW"] = "1"
    env["SAFEDETECT_IMGSZ"] = str(imgsz)
    env["SAFEDETECT_MODEL_PATH"] = model_path
    env["SAFEDETECT_USER_ID"] = user_id

    print("\nStarting Django runserver...")
    django_cmd = [sys.executable, "manage.py", "runserver", f"{server_host}:{server_port}"]
    django_proc = subprocess.Popen(django_cmd, cwd=BASE_DIR, env=env)
    detect_proc = None

    try:
        # Give Django a short head start.
        time.sleep(2)

        print("Starting phone detection...")
        detect_cmd = [sys.executable, str(BASE_DIR / "sep_detection" / "detection_phone_camera.py")]
        detect_proc = subprocess.Popen(
            detect_cmd,
            cwd=BASE_DIR,
            env=env,
            stdin=subprocess.PIPE,
            text=True,
        )

        answers = [
            user_id,
            stream_url,
            django_base_url,
            str(snapshot_interval),
            serial_port,
            str(baud_rate),
        ]
        detect_proc.stdin.write("\n".join(answers) + "\n")
        detect_proc.stdin.flush()
        detect_proc.stdin.close()

        detect_exit = detect_proc.wait()
        print(f"Detection process exited with code {detect_exit}")

    except KeyboardInterrupt:
        print("\nStopping services...")
    finally:
        if detect_proc is not None and detect_proc.poll() is None:
            detect_proc.terminate()
            try:
                detect_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                detect_proc.kill()

        if django_proc.poll() is None:
            django_proc.terminate()
            try:
                django_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                django_proc.kill()


if __name__ == "__main__":
    main()
