#!/bin/bash
# Logs real AWS state with epoch-ms timestamps while the simulated board publishes.
export AWS_DEFAULT_REGION=ap-south-1; B=dhara-evidence-181259113188-aps1; P=dhara/iot-raw/dhara-wokwi-01/; OUT=/home/bajrangi/Wins/dhara/video/cap/live
END=$(( $(date +%s) + ${1:-540} ))
( while [ $(date +%s) -lt $END ]; do
    R=$(aws s3api list-objects-v2 --bucket $B --prefix $P$(date -u +%Y/%m/%d)/ --query 'sort_by(Contents,&LastModified)[-1].[Key,LastModified]' --output text 2>/dev/null)
    echo "$(date +%s%3N)|$R" >> $OUT/s3.log; sleep 1.5; done ) &
Q=$(printf '%s\n' "from qr_app.models import SensorDevice, TankObservation" "d=SensorDevice.objects.get(thing_name='dhara-wokwi-01')" "for o in TankObservation.objects.filter(device=d).order_by('-recorded_at')[:3]: print(o.measured_at.strftime('%H:%M:%S'), o.recorded_at.strftime('%H:%M:%S'), o.value)" | base64 -w0)
while [ $(date +%s) -lt $END ]; do
  T0=$(date +%s%3N)
  C=$(aws ssm send-command --instance-ids i-0524f7292278c129d --document-name AWS-RunShellScript --parameters "commands=[\"echo $Q | base64 -d | docker exec -i dhara-app python manage.py shell 2>&1 | grep -v 'INFO\\\\|objects imported'\"]" --query Command.CommandId --output text)
  aws ssm wait command-executed --command-id $C --instance-id i-0524f7292278c129d 2>/dev/null
  O=$(aws ssm get-command-invocation --command-id $C --instance-id i-0524f7292278c129d --query StandardOutputContent --output text | grep -E '^[0-9]' | tr '\n' ';')
  echo "$T0|$(date +%s%3N)|$O" >> $OUT/db.log
done
wait
