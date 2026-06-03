#include <Arduino.h>

const int BUZZER_PIN = 8;
const int LED_PIN = LED_BUILTIN;
const unsigned int BUZZER_FREQ = 4500;
const unsigned long BEEP_ON_MS = 300;
const unsigned long BEEP_OFF_MS = 90;

String incomingLine;

void buzzAlert() {
  for (int i = 0; i < 3; i++) {
    digitalWrite(LED_PIN, HIGH);
    tone(BUZZER_PIN, BUZZER_FREQ);
    delay(BEEP_ON_MS);

    noTone(BUZZER_PIN);
    digitalWrite(LED_PIN, LOW);
    delay(BEEP_OFF_MS);
  }
}

void stopBuzz() {
  noTone(BUZZER_PIN);
  digitalWrite(BUZZER_PIN, LOW);
  digitalWrite(LED_PIN, LOW);
}

void handleCommand(String command) {
  command.trim();
  command.toUpperCase();

  if (command == "INTRUDER") {
    Serial.println("Intruder detected. Buzzing.");
    buzzAlert();
  } else if (command == "USER") {
    Serial.println("Authorized user detected. No buzz.");
    stopBuzz();
  } else if (command.length() > 0) {
    Serial.print("Unknown command: ");
    Serial.println(command);
  }
}

void setup() {
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(LED_PIN, OUTPUT);
  stopBuzz();

  Serial.begin(9600);
  delay(500);
  Serial.println("SafeDetect PlatformIO buzzer sketch ready");
  Serial.println("Send INTRUDER or USER over Serial.");
}

void loop() {
  while (Serial.available() > 0) {
    char c = static_cast<char>(Serial.read());

    if (c == '\n' || c == '\r') {
      if (incomingLine.length() > 0) {
        handleCommand(incomingLine);
        incomingLine = "";
      }
    } else {
      incomingLine += c;
    }
  }
}
