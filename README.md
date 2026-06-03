
# 🔒 SafeDetect

SafeDetect is a real-time object detection system that uses **YOLOv8** and **Yunet** to detect and raise alerts for threats such as **guns**, **knives**, **fire**, and **masks**. Designed for surveillance and security systems, it integrates with **Arduino** to trigger physical alarms on detection.

---

## 📌 Features

- 🔍 Real-time detection of:
  - Gun
  - Knife
  - Fire
  - Mask
- 📸 Upload or stream video sources
- ⚠️ Arduino integration for triggering physical alarms

---

## 🛠️ Tech Stack

- **Python 3.10+**
- **YOLOv8** via Ultralytics
- **Django**
- **Yunet**
- **Arduino (serial communication)**
- **Tailwind Css**  

---

## 🚀 Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/adubiblessed/SafeDetect.git
cd SafeDetect
```

### 2. Create a virtual environment (optional but recommended)

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Setup `.env` file

Create a `.env` file in the root directory with content like:

```env
TELEGRAM_TOKEN = ''
TELEGRAM_CHAT_ID = ''
SAFEDETECT_USER_ID = ''
```

### 5. Run the app

```bash
py manage.py runserver
```

---

## 📱 Phone Camera Mode

If you want to use your phone as the camera instead of your laptop webcam, run:

```bash
py sep_detection/detection_phone_camera.py
```

The script will prompt for:

- The user ID to protect
- Your phone camera stream URL
- The Django base URL
- The snapshot interval
- The Arduino serial port, if you want buzzer support
- The Arduino baud rate

Common stream URLs:

- IP Webcam: `http://<phone-ip>:8080/video`
- DroidCam: `http://<phone-ip>:4747/video`
- RTSP: `rtsp://username:password@<phone-ip>:554/stream`

The phone must be on the same Wi-Fi network as your PC.

---

## 💡 Arduino Integration

Upload this sketch to your board:

```cpp
const int BUZZER_PIN = 8;

void setup() {
  pinMode(BUZZER_PIN, OUTPUT);
  Serial.begin(9600);
}

void loop() {
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    cmd.toUpperCase();

    if (cmd == "INTRUDER") {
      tone(BUZZER_PIN, 1500);
      delay(180);
      noTone(BUZZER_PIN);
      delay(90);
      tone(BUZZER_PIN, 1500);
      delay(180);
      noTone(BUZZER_PIN);
      delay(90);
      tone(BUZZER_PIN, 1500);
      delay(180);
      noTone(BUZZER_PIN);
    } else if (cmd == "USER") {
      noTone(BUZZER_PIN);
    }
  }
}
```

The phone-camera detection script sends `INTRUDER` when the face is unknown and `USER` when the face matches the registered user. Set the Arduino serial port during startup, for example `COM3` on Windows.

If you are not using the buzzer, leave the serial port blank when the script asks for it.

---


## 🧠 Future Improvements

- Add face recognition module
- Email/SMS alert system
- Expand to multi-camera support

---

## 📜 License

This project is open-source under the MIT License.

---

## 🙌 Acknowledgements

- [Ultralytics YOLOv8](https://github.com/ultralytics/ultralytics)
- [Arduino](https://www.arduino.cc/)
