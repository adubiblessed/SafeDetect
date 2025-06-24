
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
```

### 5. Run the app

```bash
py manage.py runserver
```

---

## 💡 Arduino Integration

Upload this [Arduino sketch](arduino/alarm.ino) to your board:

```cpp
#define BUZZER 8

void setup() {
  pinMode(BUZZER, OUTPUT);
  Serial.begin(9600);
}

void loop() {
  if (Serial.available()) {
    char cmd = Serial.read();
    digitalWrite(BUZZER, cmd == '1' ? HIGH : LOW);
  }
}
```

Python will send `'1'` to activate the alarm and `'0'` to deactivate it.

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
