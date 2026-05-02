#!/usr/bin/env bash
set -euo pipefail

SERVER_IP="${1:?Usage: ./setup.sh <server-ip>}"

echo "=== hetzner-workers Bootstrap ==="
echo "Target: $SERVER_IP"
echo ""

ssh root@"$SERVER_IP" bash <<'REMOTE'
set -euo pipefail

echo "--- Updating system ---"
apt-get update && apt-get upgrade -y

echo "--- Installing Docker ---"
if ! command -v docker &> /dev/null; then
    apt-get install -y ca-certificates curl gnupg
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    systemctl enable docker
    systemctl start docker
    echo "Docker installed: $(docker --version)"
else
    echo "Docker already installed: $(docker --version)"
fi

echo "--- Configuring firewall (ufw) ---"
apt-get install -y ufw
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
echo "Firewall configured"

echo "--- Creating app directory ---"
mkdir -p /opt/paperwork-workers
echo "Directory ready: /opt/paperwork-workers"

echo ""
echo "=== Bootstrap complete ==="
echo "Next steps:"
echo "  1. scp infra/hetzner-workers/compose.yaml root@$HOSTNAME:/opt/paperwork-workers/"
echo "  2. scp infra/hetzner-workers/env.example root@$HOSTNAME:/opt/paperwork-workers/.env"
echo "  3. ssh root@$HOSTNAME 'cd /opt/paperwork-workers && nano .env'"
echo "  4. ssh root@$HOSTNAME 'cd /opt/paperwork-workers && docker compose up -d'"
REMOTE

echo ""
echo "=== Copying deployment files ==="
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
scp "$SCRIPT_DIR/compose.yaml" root@"$SERVER_IP":/opt/paperwork-workers/

echo ""
echo "=== Done! ==="
echo "SSH in and start the healthcheck placeholder:"
echo "  ssh root@$SERVER_IP"
echo "  cd /opt/paperwork-workers"
echo "  docker compose up -d"
echo "  docker compose logs"
