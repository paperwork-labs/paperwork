---
owner: infra-ops
last_reviewed: 2026-05-01
doc_kind: runbook
domain: infra
status: active
severity_default: yellow
related_runbooks:
  - docs/runbooks/CREDENTIAL_ACCESS.md
---
# Runbook: Hetzner Bootstrap & Operations

> Provision and operate the three-box Hetzner infrastructure (paperwork-ops, hetzner-build, hetzner-workers). Use this when adding a new box, recovering from a failed service, or onboarding a new engineer to infrastructure ops.

## When this fires

- A new Hetzner CX-series box has been purchased and needs provisioning
- A service on one of the three boxes is down and needs recovery
- GHA self-hosted runners stop appearing in GitHub Actions
- Docker is not running on a box after a reboot

## Severity ladder

| Level | Trigger | Action |
|---|---|---|
| YELLOW | One service on one box is down | SSH in, restart service, check logs |
| RED | paperwork-ops Postgres/Redis is down, OR all GHA runners offline | DM `#ops`, halt deploys, follow path below |

## Prerequisites

- SSH key in `~/.ssh/` that matches the authorized key on all three boxes
- `gh` CLI authenticated: `gh auth status`
- GitHub PAT with `repo` scope for GHA runner registration (store in Studio Vault as `GHA_RUNNER_PAT`)

## Box Architecture

| Hostname | Plan | IP | App dir | Compose file |
|---|---|---|---|---|
| paperwork-ops | CX33 (4 vCPU / 8 GB) | 204.168.147.100 | `/opt/paperwork-ops` | `infra/hetzner/compose.yaml` |
| hetzner-build | CX43 (8 vCPU / 16 GB) | 89.167.34.68 | `/opt/paperwork-build` | `infra/hetzner-build/compose.yaml` |
| hetzner-workers | CX43 (8 vCPU / 16 GB) | 204.168.165.156 | `/opt/paperwork-workers` | `infra/hetzner-workers/compose.yaml` |

## SSH Access

```bash
ssh root@204.168.147.100   # paperwork-ops
ssh root@89.167.34.68      # hetzner-build
ssh root@204.168.165.156   # hetzner-workers
```

## Triage (≤5 min)

```bash
# Quick health check across all three boxes
for ip in 204.168.147.100 89.167.34.68 204.168.165.156; do
  echo "=== $ip ==="; ssh root@$ip 'docker ps --format "table {{.Names}}\t{{.Status}}"' 2>&1; echo
done
```

If a container shows `Exited` or is missing → §"Path: restarting a service".
If SSH hangs → §"Path: box unreachable".
If GHA runners missing → §"Path: GHA runner registration".

## Path: Provision a New Box

Use this when you buy a fresh CX-series box from Hetzner Cloud.

1. Note the new box's IP from the Hetzner Cloud console.

2. Set the hostname:
   ```bash
   ssh root@<new-ip> 'hostnamectl set-hostname <hostname>'
   ```

3. Run the bootstrap script for the appropriate role:

   **For hetzner-build:**
   ```bash
   chmod +x infra/hetzner-build/setup.sh
   ./infra/hetzner-build/setup.sh <new-ip>
   ```

   **For hetzner-workers:**
   ```bash
   chmod +x infra/hetzner-workers/setup.sh
   ./infra/hetzner-workers/setup.sh <new-ip>
   ```

   **For paperwork-ops (replacement):**
   ```bash
   chmod +x infra/hetzner/setup.sh
   ./infra/hetzner/setup.sh <new-ip>
   ```

4. The script installs Docker, configures ufw, and creates the app directory. It also copies the compose file and a blank `.env`.

5. Populate the `.env`:
   ```bash
   ssh root@<new-ip>
   cd /opt/<app-dir>
   nano .env   # fill in all required values from Studio Vault
   ```

6. Start services:
   ```bash
   docker compose up -d
   docker compose logs -f   # verify all containers healthy
   ```

## Path: Register GHA Runners

Use this when runners need to be registered or re-registered on hetzner-build.

1. Obtain a GitHub PAT with `repo` scope (or use a time-limited RUNNER_TOKEN):
   ```bash
   # Generate registration token (valid 1h) — no long-lived PAT needed
   gh api -X POST repos/paperwork-labs/paperwork/actions/runners/registration-token --jq '.token'
   ```

2. SSH into hetzner-build and configure the `.env`:
   ```bash
   ssh root@89.167.34.68
   cd /opt/paperwork-build
   cat > .env <<EOF
   REPO_URL=https://github.com/paperwork-labs/paperwork
   ACCESS_TOKEN=<token-from-step-1>
   RUNNER_GROUP=default
   EOF
   ```

3. Start the runners:
   ```bash
   docker compose up -d
   docker compose logs -f
   ```

4. Verify in GitHub:
   - Go to https://github.com/paperwork-labs/paperwork/settings/actions/runners
   - All 5 runners should appear as **Idle**

## Path: Restarting a Service

```bash
ssh root@<box-ip>
cd /opt/<app-dir>

docker compose ps                    # identify which service is down
docker compose logs <service-name>   # check why it stopped
docker compose restart <service-name>
docker compose ps                    # confirm running
```

For `paperwork-ops` Postgres restart (triggers cascading restarts):
```bash
ssh root@204.168.147.100
cd /opt/paperwork-ops
docker compose restart postgres redis
sleep 10
docker compose restart postiz temporal
docker compose ps
```

## Path: Box Unreachable

1. Check Hetzner Cloud console at https://console.hetzner.cloud — verify box power state.
2. If powered off: start via console or Hetzner API.
3. If powered on but SSH unreachable: use the Hetzner Cloud console emergency shell.
4. Check `ufw status` — ensure 22/tcp is allowed. If locked out, temporarily disable ufw from the console shell.

## Path: Scale GHA Runners

To add more runner slots (e.g., runner-5, runner-6):

1. Edit `infra/hetzner-build/compose.yaml` — copy a `runner-N` service block and increment names/labels/volumes.
2. Commit and push.
3. Deploy to hetzner-build:
   ```bash
   scp infra/hetzner-build/compose.yaml root@89.167.34.68:/opt/paperwork-build/
   ssh root@89.167.34.68 'cd /opt/paperwork-build && docker compose up -d'
   ```
4. Verify new runners appear in GitHub Actions settings.

**Scale trigger**: Only add runners when sustained queue time > 5 min OR CX43 CPU is >70% for 7 consecutive days.

## Verification

```bash
# All services running on paperwork-ops
ssh root@204.168.147.100 'docker ps --format "table {{.Names}}\t{{.Status}}"'

# All services running on hetzner-build
ssh root@89.167.34.68 'docker ps --format "table {{.Names}}\t{{.Status}}"'

# All services running on hetzner-workers
ssh root@204.168.165.156 'docker ps --format "table {{.Names}}\t{{.Status}}"'

# GHA runners online (requires gh auth)
gh api repos/paperwork-labs/paperwork/actions/runners --jq '.runners[] | {name, status, busy}'
```

Expected: All containers in `Up` state; 5 runners with `status: online`.

## Rollback

- If a service update breaks Postgres: restore from latest backup dump.
  ```bash
  ssh root@204.168.147.100
  cd /opt/paperwork-ops
  docker compose exec -T postgres psql -U ops < backup_YYYYMMDD.sql
  ```
- If a bad compose.yaml was pushed: `git revert <sha>`, re-scp the file, `docker compose up -d`.
- If GHA runners won't register: the ACCESS_TOKEN may be expired — generate a fresh registration token (§ Path: Register GHA Runners step 1).

## Escalation

- Primary: `#ops` Slack channel — DM the founder.
- Hetzner outage: check https://status.hetzner.com and file ticket at https://console.hetzner.cloud/support.
- GitHub Actions outage: check https://www.githubstatus.com.

## Post-incident

- Add a row to `docs/KNOWLEDGE.md` under "Recent incidents" with pattern and resolution.
- If a new guard is needed, file a `.cursor/rules/*.mdc` update PR.
- Bump `last_reviewed` in this file's frontmatter.

## Appendix

### Useful links

- Hetzner Cloud console: https://console.hetzner.cloud
- GitHub runner settings: https://github.com/paperwork-labs/paperwork/settings/actions/runners
- GitHub Actions status: https://www.githubstatus.com
- Hetzner status: https://status.hetzner.com

### Env file locations

| Box | Env file | Populated from |
|---|---|---|
| paperwork-ops | `/opt/paperwork-ops/.env` | Studio Vault |
| hetzner-build | `/opt/paperwork-build/.env` | Studio Vault (`GHA_RUNNER_PAT`) |
| hetzner-workers | `/opt/paperwork-workers/.env` | Studio Vault |

### Scaling reference

| Signal | Action |
|---|---|
| hetzner-build CPU >70% for 7d | Add more runner slots OR upgrade to CX53 |
| hetzner-workers RAM >70% for 7d | Upgrade to CX53 (same IP, brief reboot) |
| AxiomFolio walk-forward moves to Hetzner | Provision dedicated box or rescale workers |
