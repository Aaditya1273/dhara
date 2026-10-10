#!/bin/bash
# Ship the current commit to the running server via S3 + Systems Manager (no SSH).
set -euo pipefail
REGION=${REGION:-ap-south-1}; BUCKET=${BUCKET:?set BUCKET}; export AWS_DEFAULT_REGION=$REGION
IID=$(aws ec2 describe-instances --filters Name=tag:Name,Values=dhara-demo Name=instance-state-name,Values=running --query 'Reservations[0].Instances[0].InstanceId' --output text)
REL="dhara-$(git rev-parse --short HEAD)"
git archive --format=tar.gz -o "/tmp/$REL.tar.gz" HEAD
aws s3 cp "/tmp/$REL.tar.gz" "s3://$BUCKET/deploy/$REL.tar.gz" --only-show-errors
aws s3 cp deploy/aws/ec2/server-deploy.sh "s3://$BUCKET/deploy/server-deploy.sh" --only-show-errors
CMD=$(aws ssm send-command --instance-ids $IID --document-name AWS-RunShellScript --parameters \
  "commands=[\"source /etc/profile.d/dhara.sh\",\"aws s3 cp s3://$BUCKET/deploy/server-deploy.sh /opt/dhara/server-deploy.sh --region $REGION\",\"bash /opt/dhara/server-deploy.sh $REL\"]" \
  --query Command.CommandId --output text)
aws ssm wait command-executed --command-id $CMD --instance-id $IID || true
aws ssm get-command-invocation --command-id $CMD --instance-id $IID --query '[Status,StandardOutputContent,StandardErrorContent]' --output text
