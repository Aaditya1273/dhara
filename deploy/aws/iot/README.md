# AWS IoT Core setup for DHARA tank probes

**Status:** run against a real AWS account (ap-south-1) on 11 Oct 2026 and verified end to end with a simulated device:
a Wokwi ESP32 + DS18B20 (`firmware/wokwi/sketch_aws.ino`, thing `dhara-wokwi-01`) connected to AWS IoT Core with its X.509
certificate and published every 20 s. The `dhara_forward` rule delivered the readings to the live DHARA ingest API (stored
on the demo tank, source `dhara-wokwi-01`), and `dhara_archive` wrote one S3 object per message with the token removed.
Not yet tested: a physical ESP32 and probe.

```
ESP32 + DS18B20 ──MQTT/TLS (X.509)──▶ AWS IoT Core ──rule──▶ S3  dhara/iot-raw/…   (raw archive, no token)
                  topic dhara/<thing>/telemetry      └─rule──▶ HTTPS POST /api/sensors/ingest/ (DHARA validates token)
```

Two security layers apply:
- **AWS authenticates the device** with its certificate. The policy lets it publish only to its own topic.
- **DHARA authenticates the reading** with the device token, then validates the time and value range.

The S3 archive rule leaves the token out.

## Prerequisites
- AWS CLI v2, configured: `aws configure`, or SSO with `aws sso login`.
- DHARA deployed at a public **HTTPS** URL. AWS IoT HTTP actions cannot reach `localhost`.
- A private S3 bucket. The bucket used for evidence works, since the prefix is separate.
- The sensor already registered in DHARA (tank page → *Register temperature sensor*), so you have its token.

## Steps
```bash
export AWS_REGION=ap-south-1 THING=dhara-tank-a-01 BUCKET=your-private-bucket DHARA_HOST=your.dhara.host
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
cd deploy/aws/iot

# 1. Thing, certificate, policy
aws iot create-thing --thing-name $THING
aws iot create-keys-and-certificate --set-as-active \
  --certificate-pem-outfile cert.pem.crt --private-key-outfile private.pem.key \
  --query certificateArn --output text > cert.arn
curl -so AmazonRootCA1.pem https://www.amazontrust.com/repository/AmazonRootCA1.pem
sed "s/REGION/$AWS_REGION/; s/ACCOUNT_ID/$ACCOUNT_ID/" policy.json > /tmp/dhara-policy.json
aws iot create-policy --policy-name dhara-probe --policy-document file:///tmp/dhara-policy.json
aws iot attach-policy --policy-name dhara-probe --target $(cat cert.arn)
aws iot attach-thing-principal --thing-name $THING --principal $(cat cert.arn)
aws iot describe-endpoint --endpoint-type iot:Data-ATS     # -> AWS_IOT_ENDPOINT in secrets.h

# 2. Role allowing IoT to write the raw archive
aws iam create-role --role-name dhara-iot-s3-archive --assume-role-policy-document file://trust-policy.json
sed "s/BUCKET/$BUCKET/" s3-archive-role-policy.json > /tmp/dhara-s3.json
aws iam put-role-policy --role-name dhara-iot-s3-archive --policy-name s3-archive --policy-document file:///tmp/dhara-s3.json

# 3. Rules
sed "s/ACCOUNT_ID/$ACCOUNT_ID/; s/BUCKET/$BUCKET/" archive-rule.json > /tmp/archive.json
aws iot create-topic-rule --rule-name dhara_archive --topic-rule-payload file:///tmp/archive.json
aws iot create-topic-rule-destination --destination-configuration \
  "httpUrlConfiguration={confirmationUrl=https://$DHARA_HOST/api/sensors/ingest/}"
#   DHARA logs "AWS IoT destination confirmation received … token XXX". Then confirm it, and enable it
#   (a confirmed destination starts DISABLED):
#   aws iot confirm-topic-rule-destination --confirmation-token XXX
#   aws iot update-topic-rule-destination --arn <destination arn> --status ENABLED
sed "s/DHARA_HOST/$DHARA_HOST/" forward-rule.json > /tmp/forward.json
aws iot create-topic-rule --rule-name dhara_forward --topic-rule-payload file:///tmp/forward.json
```

Then put the endpoint, `AmazonRootCA1.pem`, `cert.pem.crt` and `private.pem.key` into `firmware/dhara_tank_probe/secrets.h`, and flash the ESP32. **Never commit the key files.** Delete them from this folder once they are on the device.

## Verify it really works (for the demo video)
1. In the AWS IoT console *MQTT test client*, subscribe to `dhara/#`. You should see the probe's messages arrive.
2. `aws s3 ls s3://$BUCKET/dhara/iot-raw/$THING/ --recursive` lists the archived objects.
3. The DHARA tank page shows readings tagged **sensor**, and the activity log shows `sensor.ingested`.
4. CloudWatch Logs: enable IoT logging if a rule action fails.

## Cost note
At one message every 5 minutes, a probe sends about 8,600 messages a month. Check current AWS IoT Core and S3 pricing for your region; this is expected to be small but has not been measured here.
