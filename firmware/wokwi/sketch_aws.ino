// DHARA tank probe for Wokwi, AWS IoT Core path: ESP32 + DS18B20 -> MQTT/TLS (X.509) -> AWS IoT Core
// -> rule dhara_forward -> HTTPS POST to DHARA's ingest API (and rule dhara_archive -> S3).
// Same payload as ../dhara_tank_probe. Fill the placeholders locally; never commit or publicly save real keys.
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <time.h>

#define WIFI_SSID        "Wokwi-GUEST"
#define WIFI_PASSWORD    ""
#define THING_NAME       "dhara-wokwi-01"            // AWS IoT thing name = DHARA device ID = MQTT client ID
#define AWS_IOT_ENDPOINT "PASTE-AWS-IOT-ENDPOINT"    // aws iot describe-endpoint --endpoint-type iot:Data-ATS
#define DHARA_TOKEN      "PASTE-SENSOR-TOKEN-HERE"
static const char AWS_ROOT_CA[] = R"EOF(PASTE-AmazonRootCA1.pem)EOF";
static const char DEVICE_CERT[] = R"EOF(PASTE-cert.pem.crt)EOF";
static const char DEVICE_KEY[]  = R"EOF(PASTE-private.pem.key)EOF";

const int ONE_WIRE_PIN = 4;
const unsigned long READ_INTERVAL_MS = 20UL * 1000UL;

OneWire oneWire(ONE_WIRE_PIN);
DallasTemperature probe(&oneWire);
WiFiClientSecure tls;
PubSubClient mqtt(tls);
unsigned long lastRead = 0;

bool timeIsValid() { return time(nullptr) > 1700000000; }

String isoUtc(time_t t) {
  char out[32];
  strftime(out, sizeof(out), "%Y-%m-%dT%H:%M:%S+00:00", gmtime(&t));
  return String(out);
}

void connectMqtt() {
  while (!mqtt.connected()) {
    Serial.print("Connecting to AWS IoT Core... ");
    if (mqtt.connect(THING_NAME)) Serial.println("connected");
    else { Serial.printf("failed, state %d; retrying\n", mqtt.state()); delay(3000); }
  }
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
  tls.setCACert(AWS_ROOT_CA);
  tls.setCertificate(DEVICE_CERT);
  tls.setPrivateKey(DEVICE_KEY);
  mqtt.setServer(AWS_IOT_ENDPOINT, 8883);
  mqtt.setBufferSize(1024);
}

void loop() {
  connectMqtt();
  mqtt.loop();
  if (lastRead && millis() - lastRead < READ_INTERVAL_MS) { delay(100); return; }
  lastRead = millis();
  probe.requestTemperatures();
  float c = probe.getTempCByIndex(0);
  if (c <= -20 || c >= 80 || c == 85.0) { Serial.printf("probe value %.2f ignored\n", c); return; }
  String body = String("{\"token\":\"") + DHARA_TOKEN + "\",\"readings\":[{\"measured_at\":\"" + isoUtc(time(nullptr)) +
                "\",\"water_temp_c\":" + String(c, 2) + "}]}";
  String topic = String("dhara/") + THING_NAME + "/telemetry";
  bool ok = mqtt.publish(topic.c_str(), body.c_str());
  Serial.printf("%.2f C -> MQTT publish %s on %s\n", c, ok ? "OK" : "FAILED", topic.c_str());
}
