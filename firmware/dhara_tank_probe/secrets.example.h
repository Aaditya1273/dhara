// Copy to secrets.h (git-ignored) and fill in. Never commit secrets.h.
#pragma once
#define WIFI_SSID      "your-wifi"
#define WIFI_PASSWORD  "your-password"
#define DHARA_TOKEN    "token shown once when you registered the sensor in DHARA"
#define THING_NAME     "dhara-tank-a-01"   // same as the Device ID in DHARA and the AWS IoT thing name

// Mode 1 (default): AWS IoT Core over MQTT/TLS. Fill from `aws iot describe-endpoint --endpoint-type iot:Data-ATS`
#define USE_AWS_IOT    1
#define AWS_IOT_ENDPOINT "xxxxxxxxxxxx-ats.iot.ap-south-1.amazonaws.com"
static const char AWS_ROOT_CA[] PROGMEM = R"EOF(-----BEGIN CERTIFICATE-----
...AmazonRootCA1.pem...
-----END CERTIFICATE-----)EOF";
static const char DEVICE_CERT[] PROGMEM = R"EOF(-----BEGIN CERTIFICATE-----
...certificate.pem.crt...
-----END CERTIFICATE-----)EOF";
static const char DEVICE_KEY[] PROGMEM = R"EOF(-----BEGIN RSA PRIVATE KEY-----
...private.pem.key...
-----END RSA PRIVATE KEY-----)EOF";

// Mode 2: direct HTTPS to DHARA (set USE_AWS_IOT 0). Bypasses AWS; useful for bench testing.
#define DHARA_INGEST_URL "https://your-dhara-host/api/sensors/ingest/"
