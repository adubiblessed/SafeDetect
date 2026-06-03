// SafeDetect Arduino buzzer sketch
// Listens on Serial for commands from Python:
//   INTRUDER  -> plays an alert pattern
//   USER      -> stops the buzzer

const int BUZZER_PIN = 8;
const int BUZZER_FREQ = 1500;
const int BUZZER_ON_MS = 180;
const int BUZZER_OFF_MS = 90;

String incomingLine;

void buzzPattern() {
  for (int i = 0; i < 3; i++) {
    tone(BUZZER_PIN, BUZZER_FREQ);
    delay(BUZZER_ON_MS);
    noTone(BUZZER_PIN);
    delay(BUZZER_OFF_MS);
  }
}

void stopBuzz() {
  noTone(BUZZER_PIN);
  digitalWrite(BUZZER_PIN, LOW);
}

void setup() {
  pinMode(BUZZER_PIN, OUTPUT);
  stopBuzz();
  Serial.begin(9600);
  Serial.println("SafeDetect Arduino ready");
}

void loop() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();

    if (c == '\n' || c == '\r') {
      if (incomingLine.length() == 0) {
        continue;
      }

      incomingLine.trim();
      incomingLine.toUpperCase();

      if (incomingLine == "INTRUDER") {
        Serial.println("Intruder detected. Buzzing.");
        buzzPattern();
      } else if (incomingLine == "USER") {
        Serial.println("Authorized user detected. No buzz.");
        stopBuzz();
      } else {
        Serial.print("Unknown command: ");
        Serial.println(incomingLine);
      }

      incomingLine = "";
    } else {
      incomingLine += c;
    }
  }
}
