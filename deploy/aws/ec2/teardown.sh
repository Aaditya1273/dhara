#!/bin/bash
# Stops all charges from the demo server: terminates the instance, releases the Elastic IP, removes the
# security group and the instance role. Bucket contents are kept unless EMPTY_BUCKET=1.
set -euo pipefail
REGION=${REGION:-ap-south-1}; export AWS_DEFAULT_REGION=$REGION; NAME=dhara-demo
IIDS=$(aws ec2 describe-instances --filters Name=tag:Name,Values=$NAME Name=instance-state-name,Values=pending,running,stopping,stopped --query 'Reservations[].Instances[].InstanceId' --output text)
if [ -n "$IIDS" ]; then aws ec2 terminate-instances --instance-ids $IIDS >/dev/null; aws ec2 wait instance-terminated --instance-ids $IIDS; echo "terminated $IIDS"; fi
ALLOC=$(aws ec2 describe-addresses --filters Name=tag:Name,Values=$NAME --query 'Addresses[0].AllocationId' --output text)
[ "$ALLOC" != "None" ] && aws ec2 release-address --allocation-id $ALLOC && echo "released Elastic IP"
SG=$(aws ec2 describe-security-groups --filters Name=group-name,Values=$NAME --query 'SecurityGroups[0].GroupId' --output text)
[ "$SG" != "None" ] && aws ec2 delete-security-group --group-id $SG && echo "deleted security group"
if aws iam get-role --role-name dhara-ec2 >/dev/null 2>&1; then
  aws iam remove-role-from-instance-profile --instance-profile-name dhara-ec2 --role-name dhara-ec2 || true
  aws iam delete-instance-profile --instance-profile-name dhara-ec2 || true
  aws iam delete-role-policy --role-name dhara-ec2 --policy-name dhara-s3 || true
  aws iam detach-role-policy --role-name dhara-ec2 --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore || true
  aws iam delete-role --role-name dhara-ec2 && echo "deleted IAM role"
fi
if [ "${EMPTY_BUCKET:-0}" = 1 ] && [ -n "${BUCKET:-}" ]; then
  python3 - "$BUCKET" <<'PY'
import json, subprocess, sys
b = sys.argv[1]
while True:
    out = json.loads(subprocess.check_output(['aws', 's3api', 'list-object-versions', '--bucket', b, '--max-items', '900', '--output', 'json']) or '{}')
    objs = [{'Key': o['Key'], 'VersionId': o['VersionId']} for o in out.get('Versions', []) + out.get('DeleteMarkers', [])]
    if not objs:
        break
    subprocess.run(['aws', 's3api', 'delete-objects', '--bucket', b, '--delete', json.dumps({'Objects': objs, 'Quiet': True})], check=True)
print('bucket emptied')
PY
fi
echo "Done. Remaining billable items for DHARA: S3 storage only (if the bucket still has objects)."
