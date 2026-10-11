// DHARA tank probe for the Wokwi simulator (https://wokwi.com): ESP32 + DS18B20 on GPIO4.
// Same reading format as ../dhara_tank_probe, but posts straight to DHARA over HTTPS (no AWS IoT certificates),
// joins Wokwi's virtual Wi-Fi, and reads every 20 s so you can watch it work.
// Paste your sensor token below. Don't save a public Wokwi project with a real token in it.
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <time.h>

#define WIFI_SSID        "Wokwi-GUEST"
#define WIFI_PASSWORD    ""
#define DHARA_INGEST_URL "https://43-204-133-35.sslip.io/api/sensors/ingest/"
#define DHARA_TOKEN      "PASTE-SENSOR-TOKEN-HERE"

const int ONE_WIRE_PIN = 4;
const unsigned long READ_INTERVAL_MS = 20UL * 1000UL;

OneWire oneWire(ONE_WIRE_PIN);
DallasTemperature probe(&oneWire);
unsigned long lastRead = 0;

bool timeIsValid() { return time(nullptr) > 1700000000; }

String isoUtc(time_t t) {
  char out[32];
  strftime(out, sizeof(out), "%Y-%m-%dT%H:%M:%S+00:00", gmtime(&t));
  return String(out);
}

void setup() {
  Serial.begin(115200);
  probe.begin();
  Serial.print("Connecting to Wi-Fi");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD, 6);
  while (WiFi.status() != WL_CONNECTED) { delay(250); Serial.print("."); }
  Serial.println(" connected");
  configTime(0, 0, "pool.ntp.org", "time.google.com");
  Serial.print("Syncing time");
  while (!timeIsValid()) { delay(250); Serial.print("."); }
  Serial.println(" " + isoUtc(time(nullptr)));
}

void loop() {
  if (lastRead && millis() - lastRead < READ_INTERVAL_MS) { delay(100); return; }
  lastRead = millis();
  probe.requestTemperatures();
  float c = probe.getTempCByIndex(0);
  if (c <= -20 || c >= 80 || c == 85.0) { Serial.printf("probe value %.2f ignored\n", c); return; }

  String body = String("{\"token\":\"") + DHARA_TOKEN + "\",\"readings\":[{\"measured_at\":\"" + isoUtc(time(nullptr)) +
                "\",\"water_temp_c\":" + String(c, 2) + "}]}";
  WiFiClientSecure tls;
  tls.setInsecure();   // simulator only: pin the server certificate on real hardware
  HTTPClient http;
  http.begin(tls, DHARA_INGEST_URL);
  http.addHeader("Content-Type", "application/json");
  int code = http.POST(body);
  Serial.printf("%.2f C -> HTTP %d %s\n", c, code, http.getString().c_str());
  http.end();
}
