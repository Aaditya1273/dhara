#!/bin/bash
# Runs ON the EC2 instance (first boot via user-data, later via SSM). Usage: server-deploy.sh <release-name>
# Required env: BUCKET, REGION, HOST
set -euo pipefail
RELEASE="$1"
cd /opt/dhara
aws s3 cp "s3://$BUCKET/deploy/$RELEASE.tar.gz" release.tar.gz --region "$REGION"
rm -rf src && mkdir src && tar -xzf release.tar.gz -C src
docker build -q -t dhara:"$RELEASE" src
[ -s secret_key ] || (head -c 48 /dev/urandom | base64 | tr -d '\n/+=' > secret_key && chmod 600 secret_key)
umask 077
cat > app.env <<ENV
SECRET_KEY=$(cat secret_key)
DEBUG=False
ALLOWED_HOSTS=$HOST
CSRF_TRUSTED_ORIGINS=https://$HOST
DATABASE_URL=sqlite:////app/data/db.sqlite3
STORAGE_BACKEND=s3
AWS_STORAGE_BUCKET_NAME=$BUCKET
AWS_REGION=$REGION
AWS_S3_PREFIX=dhara-prod
ENV
cat > Caddyfile <<CADDY
$HOST {
	encode gzip
	reverse_proxy dhara-app:8000
}
CADDY
docker network inspect dhara >/dev/null 2>&1 || docker network create dhara
docker rm -f dhara-app >/dev/null 2>&1 || true
docker run -d --name dhara-app --restart unless-stopped --network dhara --env-file app.env \
  -v dhara-data:/app/data dhara:"$RELEASE"
if ! docker ps --format '{{.Names}}' | grep -qx caddy; then
  docker rm -f caddy >/dev/null 2>&1 || true
  docker run -d --name caddy --restart unless-stopped --network dhara -p 80:80 -p 443:443 \
    -v /opt/dhara/Caddyfile:/etc/caddy/Caddyfile:ro -v caddy-data:/data -v caddy-config:/config caddy:2
fi
echo "$RELEASE" > current_release
echo "deployed $RELEASE"
