#include <Wire.h>

void setup() {
  Serial.begin(115200);
  Wire.begin(8, 9);
}

void loop() {
  for (byte addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) {
      Serial.println(addr, HEX);
    }
  }
  Serial.println("scan done");
  delay(2000);
}
