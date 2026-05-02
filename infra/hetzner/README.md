# Paperwork Labs — Hetzner Infrastructure

Three-box architecture running all non-Vercel workloads on Hetzner Cloud (Helsinki, billing@paperworklabs.com).

## Box Summary

| Hostname | Plan | IP | Role |
|---|---|---|---|
| **paperwork-ops** | CX33 (4 vCPU / 8 GB) | 204.168.147.100 | State + social: Postgres, Redis, Postiz, Temporal |
| **paperwork-builders** | CX43 (8 vCPU / 16 GB) | 89.167.34.68 | CI: GHA self-hosted runners, Vercel --prebuilt |
| **paperwork-workers** | CX43 (8 vCPU / 16 GB) | 204.168.165.156 | Brain background: schedulers, dispatcher, transcript ingest |

## paperwork-ops (`infra/hetzner/compose.yaml`)

Runs persistent state and social media services. **Do not run production workloads here.**

| Service | Port | Purpose |
|---------|------|---------|
| **Postiz** | 5000 | Social media scheduler (TikTok, Instagram, Twitter/X) |
| **PostgreSQL** | 5432 | Shared database for Postiz |
| **Redis** | 6379 | Shared cache/queue for Postiz + Temporal |
| **Temporal** | 7233 | Workflow orchestration for Postiz |

> **n8n removed**: Brain (Render-hosted FastAPI + LLM) replaced n8n for all agent workflows in 2026-Q1. The n8n and n8n-worker services have been removed from this compose.

### Quick Start

```bash
chmod +x infra/hetzner/setup.sh
./infra/hetzner/setup.sh 204.168.147.100
```

### Env file location

`/opt/paperwork-ops/.env` — populated from Studio Vault.

---

## paperwork-builders (`infra/hetzner-build/`)

Runs 5 GitHub Actions self-hosted runners (4 cheap-agent slots + 1 heavy-ci slot).

See [`infra/hetzner-build/`](../hetzner-build/) for compose and setup script.

### Quick Start

```bash
chmod +x infra/hetzner-build/setup.sh
./infra/hetzner-build/setup.sh 89.167.34.68
```

Then configure `/opt/paperwork-build/.env` with a GitHub PAT and run `docker compose up -d`.

### Runner labels

| Runner name | Labels |
|---|---|
| paperwork-builders-slot-1 | `self-hosted,paperwork-builders,cheap-agent-slot-1` |
| paperwork-builders-slot-2 | `self-hosted,paperwork-builders,cheap-agent-slot-2` |
| paperwork-builders-slot-3 | `self-hosted,paperwork-builders,cheap-agent-slot-3` |
| paperwork-builders-slot-4 | `self-hosted,paperwork-builders,cheap-agent-slot-4` |
| paperwork-builders-heavy-ci | `self-hosted,paperwork-builders,heavy-ci` |

---

## paperwork-workers (`infra/hetzner-workers/`)

Placeholder for Brain background workers (added in Wave 8 PRs).

See [`infra/hetzner-workers/`](../hetzner-workers/) for compose and setup script.

### Quick Start

```bash
chmod +x infra/hetzner-workers/setup.sh
./infra/hetzner-workers/setup.sh 204.168.165.156
```

---

## SSH Access

From founder laptop: `ssh root@<ip>` (no `-i` flag needed — uses `~/.ssh/` default key).

```bash
ssh root@204.168.147.100   # paperwork-ops
ssh root@89.167.34.68      # paperwork-builders
ssh root@204.168.165.156   # paperwork-workers
```

## Maintenance

```bash
ssh root@<server-ip>
cd /opt/<app-dir>

docker compose logs -f                         # tail all logs
docker compose ps                              # check service status
docker compose pull && docker compose up -d    # update images
docker compose down                            # stop all
```

## Backups

PostgreSQL data is in a Docker volume on paperwork-ops:

```bash
ssh root@204.168.147.100
cd /opt/paperwork-ops
docker compose exec postgres pg_dumpall -U ops > backup_$(date +%Y%m%d).sql
```

## Runbook

See [`docs/runbooks/hetzner-bootstrap.md`](../../docs/runbooks/hetzner-bootstrap.md) for full provisioning and operations runbook.
