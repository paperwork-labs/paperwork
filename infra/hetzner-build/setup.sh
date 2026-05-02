#!/usr/bin/env bash
set -euo pipefail

SERVER_IP="${1:?Usage: ./setup.sh <server-ip>}"

echo "=== paperwork-builders Bootstrap ==="
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
mkdir -p /opt/paperwork-build
echo "Directory ready: /opt/paperwork-build"

echo ""
echo "=== Bootstrap complete ==="
echo "Next steps:"
echo "  1. scp infra/hetzner-build/compose.yaml root@$HOSTNAME:/opt/paperwork-build/"
echo "  2. scp infra/hetzner-build/env.example root@$HOSTNAME:/opt/paperwork-build/.env"
echo "  3. ssh root@$HOSTNAME 'cd /opt/paperwork-build && nano .env'  # fill in ACCESS_TOKEN"
echo "  4. ssh root@$HOSTNAME 'cd /opt/paperwork-build && docker compose up -d'"
REMOTE

echo ""
echo "=== Copying deployment files ==="
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
scp "$SCRIPT_DIR/compose.yaml" root@"$SERVER_IP":/opt/paperwork-build/
scp "$SCRIPT_DIR/env.example" root@"$SERVER_IP":/opt/paperwork-build/.env

echo ""
echo "=== Done! ==="
echo "SSH in and configure ACCESS_TOKEN, then start runners:"
echo "  ssh root@$SERVER_IP"
echo "  cd /opt/paperwork-build"
echo "  nano .env          # fill in ACCESS_TOKEN (GitHub PAT with repo scope)"
echo "  docker compose up -d"
echo "  docker compose logs -f"
