# Paperwork Labs Ops Stack — Hetzner VPS

Agent brain + social automation stack running on Hetzner Cloud CX33.

## Services

| Service | Port | Purpose |
|---------|------|---------|
| **n8n** | 5678 | Agent brain — Slack bot workflows, daily briefings, PR summaries, persona routing |
| **Postiz** | 5000 | Social media scheduler (TikTok, Instagram, Twitter/X) |
| **PostgreSQL** | 5432 | Shared database for n8n + Postiz |
| **Redis** | 6379 | Shared cache/queue for n8n + Postiz |

## Server Details

- **Provider**: Hetzner Cloud
- **Plan**: CX33 (4 vCPU, 8GB RAM, 80GB SSD) — EUR 5.49/mo
- **OS**: Ubuntu 24.04
- **Reverse Proxy**: Caddy (auto TLS via Let's Encrypt)
- **Account**: billing@paperworklabs.com

## Quick Start

### 1. Bootstrap the server

```bash
chmod +x infra/hetzner/setup.sh
./infra/hetzner/setup.sh <server-ip>
```

This installs Docker, Caddy, configures the firewall, and copies deployment files.

### 2. Configure environment

```bash
ssh root@<server-ip>
cd /opt/paperwork-ops
nano .env  # fill in all REQUIRED values
```

### 3. Start services

```bash
docker compose up -d
docker compose logs -f  # verify all healthy
```

### 4. Configure Caddy reverse proxy

Edit `/etc/caddy/Caddyfile`:

```
n8n.paperworklabs.com {
    reverse_proxy localhost:5678
}

social.paperworklabs.com {
    reverse_proxy localhost:5000
}
```

Then reload: `systemctl reload caddy`

### 5. DNS Records

Add A records pointing to the server IP:

| Record | Type | Value |
|--------|------|-------|
| `n8n.paperworklabs.com` | A | `<server-ip>` |
| `social.paperworklabs.com` | A | `<server-ip>` |

## Maintenance

```bash
ssh root@<server-ip>
cd /opt/paperwork-ops

docker compose logs -f          # tail all logs
docker compose ps               # check service status
docker compose pull && docker compose up -d  # update images
docker compose down              # stop all
```

## Backups

PostgreSQL data is stored in a Docker volume. To backup:

```bash
docker compose exec postgres pg_dumpall -U ops > backup_$(date +%Y%m%d).sql
```
