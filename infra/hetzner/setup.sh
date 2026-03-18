#!/usr/bin/env bash
set -euo pipefail

SERVER_IP="${1:?Usage: ./setup.sh <server-ip>}"

echo "=== Paperwork Labs Ops Stack Setup ==="
echo "Target: $SERVER_IP"
echo ""

ssh root@"$SERVER_IP" bash <<'REMOTE'
set -euo pipefail

echo "--- Updating system ---"
apt-get update && apt-get upgrade -y

echo "--- Installing Docker ---"
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
    echo "Docker installed: $(docker --version)"
else
    echo "Docker already installed: $(docker --version)"
fi

echo "--- Installing Docker Compose plugin ---"
if ! docker compose version &> /dev/null; then
    apt-get install -y docker-compose-plugin
    echo "Docker Compose installed: $(docker compose version)"
else
    echo "Docker Compose already installed: $(docker compose version)"
fi

echo "--- Setting up firewall (ufw) ---"
apt-get install -y ufw
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
echo "Firewall configured"

echo "--- Installing Caddy (reverse proxy + auto TLS) ---"
if ! command -v caddy &> /dev/null; then
    apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
    apt-get update
    apt-get install -y caddy
    echo "Caddy installed: $(caddy version)"
else
    echo "Caddy already installed: $(caddy version)"
fi

echo "--- Creating app directory ---"
mkdir -p /opt/paperwork-ops
echo "Directory ready: /opt/paperwork-ops"

echo ""
echo "=== Server bootstrap complete ==="
echo "Next steps:"
echo "  1. scp infra/hetzner/compose.yaml root@$HOSTNAME:/opt/paperwork-ops/"
echo "  2. scp infra/hetzner/env.example root@$HOSTNAME:/opt/paperwork-ops/.env"
echo "  3. ssh root@$HOSTNAME 'cd /opt/paperwork-ops && nano .env'  # fill in secrets"
echo "  4. ssh root@$HOSTNAME 'cd /opt/paperwork-ops && docker compose up -d'"
REMOTE

echo ""
echo "=== Copying deployment files ==="
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
scp "$SCRIPT_DIR/compose.yaml" root@"$SERVER_IP":/opt/paperwork-ops/
scp "$SCRIPT_DIR/env.example" root@"$SERVER_IP":/opt/paperwork-ops/.env

echo ""
echo "=== Done! ==="
echo "SSH in and configure:"
echo "  ssh root@$SERVER_IP"
echo "  cd /opt/paperwork-ops"
echo "  nano .env          # fill in all REQUIRED values"
echo "  docker compose up -d"
echo "  docker compose logs -f"
