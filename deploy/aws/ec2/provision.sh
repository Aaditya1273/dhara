#!/bin/bash
# Creates the DHARA demo server: EC2 t3.micro (Amazon Linux 2023) + Elastic IP + Caddy HTTPS on <ip>.sslip.io.
# No SSH: admin through AWS Systems Manager. App credentials come from an IAM role scoped to the bucket.
# Usage: BUCKET=... ./deploy/aws/ec2/provision.sh      (run from the repo root, AWS CLI configured)
set -euo pipefail
REGION=${REGION:-ap-south-1}; BUCKET=${BUCKET:?set BUCKET}; NAME=dhara-demo
export AWS_DEFAULT_REGION=$REGION
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)

echo "1/7 IAM role for the instance"
if ! aws iam get-role --role-name dhara-ec2 >/dev/null 2>&1; then
  aws iam create-role --role-name dhara-ec2 --assume-role-policy-document \
    '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}' >/dev/null
  aws iam attach-role-policy --role-name dhara-ec2 --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
  aws iam create-instance-profile --instance-profile-name dhara-ec2 >/dev/null
  aws iam add-role-to-instance-profile --instance-profile-name dhara-ec2 --role-name dhara-ec2
fi
aws iam put-role-policy --role-name dhara-ec2 --policy-name dhara-s3 --policy-document "{
  \"Version\":\"2012-10-17\",\"Statement\":[
   {\"Effect\":\"Allow\",\"Action\":[\"s3:GetObject\",\"s3:PutObject\",\"s3:DeleteObject\"],\"Resource\":\"arn:aws:s3:::$BUCKET/dhara-prod/*\"},
   {\"Effect\":\"Allow\",\"Action\":\"s3:GetObject\",\"Resource\":\"arn:aws:s3:::$BUCKET/deploy/*\"},
   {\"Effect\":\"Allow\",\"Action\":\"s3:ListBucket\",\"Resource\":\"arn:aws:s3:::$BUCKET\",
    \"Condition\":{\"StringLike\":{\"s3:prefix\":[\"dhara-prod/*\",\"deploy/*\"]}}}]}"

echo "2/7 security group (80/443 only; no SSH)"
VPC=$(aws ec2 describe-vpcs --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text)
SG=$(aws ec2 describe-security-groups --filters Name=group-name,Values=$NAME Name=vpc-id,Values=$VPC --query 'SecurityGroups[0].GroupId' --output text)
if [ "$SG" = "None" ]; then
  SG=$(aws ec2 create-security-group --group-name $NAME --description "DHARA demo web" --vpc-id $VPC --query GroupId --output text)
  for P in 80 443; do aws ec2 authorize-security-group-ingress --group-id $SG --protocol tcp --port $P --cidr 0.0.0.0/0 >/dev/null; done
fi

echo "3/7 Elastic IP and hostname"
ALLOC=$(aws ec2 describe-addresses --filters Name=tag:Name,Values=$NAME --query 'Addresses[0].AllocationId' --output text)
if [ "$ALLOC" = "None" ]; then
  ALLOC=$(aws ec2 allocate-address --domain vpc --tag-specifications "ResourceType=elastic-ip,Tags=[{Key=Name,Value=$NAME}]" --query AllocationId --output text)
fi
IP=$(aws ec2 describe-addresses --allocation-ids $ALLOC --query 'Addresses[0].PublicIp' --output text)
HOST="${IP//./-}.sslip.io"; echo "   https://$HOST"

echo "4/7 upload release to s3://$BUCKET/deploy/"
REL="dhara-$(git rev-parse --short HEAD)"
git archive --format=tar.gz -o "/tmp/$REL.tar.gz" HEAD
aws s3 cp "/tmp/$REL.tar.gz" "s3://$BUCKET/deploy/$REL.tar.gz" --only-show-errors
aws s3 cp deploy/aws/ec2/server-deploy.sh "s3://$BUCKET/deploy/server-deploy.sh" --only-show-errors

echo "5/7 launch instance"
AMI=$(aws ssm get-parameter --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 --query Parameter.Value --output text)
USERDATA=$(cat <<UD
#!/bin/bash
set -eux
dnf install -y docker
systemctl enable --now docker
mkdir -p /opt/dhara
cat > /etc/profile.d/dhara.sh <<ENV
export BUCKET=$BUCKET REGION=$REGION HOST=$HOST
ENV
aws s3 cp s3://$BUCKET/deploy/server-deploy.sh /opt/dhara/server-deploy.sh --region $REGION
chmod +x /opt/dhara/server-deploy.sh
BUCKET=$BUCKET REGION=$REGION HOST=$HOST /opt/dhara/server-deploy.sh $REL
UD
)
sleep 10   # new instance profiles take a few seconds to become usable
IID=$(aws ec2 run-instances --image-id $AMI --instance-type t3.micro --security-group-ids $SG \
  --iam-instance-profile Name=dhara-ec2 \
  --metadata-options HttpTokens=required,HttpPutResponseHopLimit=2,HttpEndpoint=enabled \
  --block-device-mappings 'DeviceName=/dev/xvda,Ebs={VolumeSize=16,VolumeType=gp3,Encrypted=true}' \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$NAME}]" \
  --user-data "$USERDATA" --query 'Instances[0].InstanceId' --output text)
echo "   $IID"
aws ec2 wait instance-running --instance-ids $IID

echo "6/7 attach Elastic IP"
aws ec2 associate-address --instance-id $IID --allocation-id $ALLOC >/dev/null

echo "7/7 waiting for https://$HOST/healthz/ (build + certificate, usually 3-6 min)"
for i in $(seq 1 60); do
  if curl -fsS --max-time 5 "https://$HOST/healthz/" 2>/dev/null; then echo; echo "LIVE: https://$HOST"; exit 0; fi
  sleep 10
done
echo "Not up yet. Check: aws ssm start-session --target $IID   then: sudo cat /var/log/cloud-init-output.log"; exit 1
