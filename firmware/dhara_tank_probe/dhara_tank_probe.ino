// DHARA in-tank temperature probe: ESP32 + waterproof DS18B20 (data pin GPIO4, 4.7 kΩ pull-up to 3.3 V).
// Reads every 5 minutes, timestamps with NTP (UTC), and sends JSON readings to DHARA either through
// AWS IoT Core (MQTT/TLS, topic dhara/<thing>/telemetry) or directly over HTTPS.
// Libraries: OneWire, DallasTemperature, PubSubClient (Arduino Library Manager); ESP32 core >= 2.0.
// STATUS: written for this project; NOT compiled or bench-tested yet. Verify on hardware before relying on it.
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <PubSubClient.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <time.h>
#include "secrets.h"

const int ONE_WIRE_PIN = 4;
const unsigned long READ_INTERVAL_MS = 5UL * 60UL * 1000UL;
const int MAX_BUFFER = 48;                     // ~4 h of readings kept in RAM while offline

OneWire oneWire(ONE_WIRE_PIN);
DallasTemperature probe(&oneWire);
WiFiClientSecure tls;
PubSubClient mqtt(tls);

struct Reading { time_t at; float c; };
Reading buffer[MAX_BUFFER];
int buffered = 0;
unsigned long lastRead = 0;

bool timeIsValid() { return time(nullptr) > 1700000000; }   // NTP has synced (after Nov 2023)

void connectWifi() {
  if (WiFi.status() == WL_CONNECTED) return;
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  for (int i = 0; i < 40 && WiFi.status() != WL_CONNECTED; i++) delay(500);
}

String isoUtc(time_t t) {
  char out[32];
  strftime(out, sizeof(out), "%Y-%m-%dT%H:%M:%S+00:00", gmtime(&t));
  return String(out);
}

String payload() {
  String body = "{\"token\":\"" DHARA_TOKEN "\",\"readings\":[";
  for (int i = 0; i < buffered; i++) {
    if (i) body += ",";
    body += "{\"measured_at\":\"" + isoUtc(buffer[i].at) + "\",\"water_temp_c\":" + String(buffer[i].c, 2) + "}";
  }
  return body + "]}";
}

bool sendBuffer() {
  if (!buffered || WiFi.status() != WL_CONNECTED) return false;
#if USE_AWS_IOT
  if (!mqtt.connected()) {
    if (!mqtt.connect(THING_NAME)) return false;
  }
  String topic = String("dhara/") + THING_NAME + "/telemetry";
  return mqtt.publish(topic.c_str(), payload().c_str());
#else
  HTTPClient http;
  tls.setInsecure();   // bench testing only: pin your server's CA certificate for real deployments
  http.begin(tls, DHARA_INGEST_URL);
  http.addHeader("Content-Type", "application/json");
  int code = http.POST(payload());
  http.end();
  return code == 200;
#endif
}

void setup() {
  Serial.begin(115200);
  probe.begin();
  connectWifi();
  configTime(0, 0, "pool.ntp.org", "time.google.com");
#if USE_AWS_IOT
  tls.setCACert(AWS_ROOT_CA);
  tls.setCertificate(DEVICE_CERT);
  tls.setPrivateKey(DEVICE_KEY);
  mqtt.setServer(AWS_IOT_ENDPOINT, 8883);
  mqtt.setBufferSize(4096);
#endif
}

void loop() {
  connectWifi();
  mqtt.loop();
  if (millis() - lastRead >= READ_INTERVAL_MS || lastRead == 0) {
    lastRead = millis();
    probe.requestTemperatures();
    float c = probe.getTempCByIndex(0);
    // Skip disconnected-probe (-127) and power-on (85) sentinel values, and never send without real time.
    if (c > -20 && c < 80 && c != 85.0 && timeIsValid()) {
      if (buffered == MAX_BUFFER) { memmove(buffer, buffer + 1, sizeof(Reading) * (MAX_BUFFER - 1)); buffered--; }
      buffer[buffered++] = {time(nullptr), c};
      Serial.printf("reading %.2f C (%d buffered)\n", c, buffered);
    }
    if (sendBuffer()) { Serial.println("sent"); buffered = 0; }
  }
  delay(1000);
}
