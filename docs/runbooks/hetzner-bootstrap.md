---
owner: infra-ops
last_reviewed: 2026-05-02
doc_kind: runbook
domain: infra
status: active
severity_default: yellow
related_runbooks:
  - docs/runbooks/credential-access.md
---
# Runbook: Hetzner Bootstrap & Operations

> **Category**: ops
> **Owner**: @infra-ops
> **Last verified**: 2026-05-02
> **Status**: active

> Provision and operate the three-box Hetzner infrastructure (paperwork-ops, paperwork-builders, paperwork-workers). Use this when adding a new box, recovering from a failed service, or onboarding a new engineer to infrastructure ops.

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
| paperwork-builders | CX43 (8 vCPU / 16 GB) | 89.167.34.68 | `/opt/paperwork-build` | `infra/hetzner-build/compose.yaml` |
| paperwork-workers | CX43 (8 vCPU / 16 GB) | 204.168.165.156 | `/opt/paperwork-workers` | `infra/hetzner-workers/compose.yaml` |

## SSH Access

```bash
ssh root@204.168.147.100   # paperwork-ops
ssh root@89.167.34.68      # paperwork-builders
ssh root@204.168.165.156   # paperwork-workers
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

   **For paperwork-builders:**
   ```bash
   chmod +x infra/hetzner-build/setup.sh
   ./infra/hetzner-build/setup.sh <new-ip>
   ```

   **For paperwork-workers:**
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

Use this when runners need to be registered or re-registered on paperwork-builders.

> **Token choice — known gotcha (2026-05-03 bootstrap)**
>
> The `myoung34/github-runner` image accepts either of two env vars:
>
> - `RUNNER_TOKEN` — short-lived registration token (valid 1h). The runner uses
>   it once to register, then writes a permanent `.runner` config into the named
>   docker volume. With `restart: unless-stopped` and the volume mounted, the
>   container survives restarts and reboots without re-registering.
> - `ACCESS_TOKEN` — long-lived GitHub PAT with `repo` scope. The runner mints
>   its own registration tokens on every start. Useful only if you ever wipe the
>   runner volume.
>
> **Do NOT use a key called `GHA_RUNNER_PAT` from the Studio Vault** — that
> name was speculative; the vault only ships `GITHUB_PAT` (which has been
> observed to be expired) and `GITHUB_PAT_FINEGRAINED`. Default to
> `RUNNER_TOKEN` for a fresh bootstrap; if a vault PAT is available and you
> want auto-recovery from a wiped volume, use `ACCESS_TOKEN` instead.

1. Mint a registration token (valid 1h, no long-lived PAT needed):
   ```bash
   gh api -X POST repos/paperwork-labs/paperwork/actions/runners/registration-token --jq '.token'
   ```

2. SSH into paperwork-builders and configure the `.env`:
   ```bash
   ssh root@89.167.34.68
   mkdir -p /opt/paperwork-build
   cd /opt/paperwork-build
   cat > .env <<EOF
   REPO_URL=https://github.com/paperwork-labs/paperwork
   RUNNER_TOKEN=<token-from-step-1>
   RUNNER_GROUP=default
   EOF
   chmod 600 .env
   ```

   > **Repo URL gotcha**: the GitHub org slug is `paperwork-labs` (with a
   > hyphen). Internal docs sometimes write `paperworklabs` — that 404s.

3. Start the runners (compose file lives at `infra/hetzner-build/compose.yaml`):
   ```bash
   # From the founder laptop (not the box):
   scp infra/hetzner-build/compose.yaml root@89.167.34.68:/opt/paperwork-build/

   ssh root@89.167.34.68
   cd /opt/paperwork-build
   docker compose pull
   docker compose up -d
   docker compose logs -f      # Look for "√ Runner successfully added" + "Listening for Jobs"
   ```

4. Verify in GitHub:
   - Go to https://github.com/paperwork-labs/paperwork/settings/actions/runners
   - All 5 runners should appear as **Idle**.
   - Or check the API (see § Verification at the bottom).

   Expected labels per runner (the runner image adds `self-hosted,Linux,X64`
   automatically; `hetzner` + slot-specific labels come from `RUNNER_LABELS` in
   `compose.yaml`):

   ```text
   self-hosted, Linux, X64, hetzner, paperwork-builders, cheap-agent-slot-1
   self-hosted, Linux, X64, hetzner, paperwork-builders, cheap-agent-slot-2
   self-hosted, Linux, X64, hetzner, paperwork-builders, cheap-agent-slot-3
   self-hosted, Linux, X64, hetzner, paperwork-builders, cheap-agent-slot-4
   self-hosted, Linux, X64, hetzner, paperwork-builders, heavy-ci
   ```

   Workflows can target this fleet via either the canonical
   `runs-on: [self-hosted, hetzner]` or a legacy slot label.

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
3. Deploy to paperwork-builders:
   ```bash
   scp infra/hetzner-build/compose.yaml root@89.167.34.68:/opt/paperwork-build/
   ssh root@89.167.34.68 'cd /opt/paperwork-build && docker compose up -d'
   ```
4. Verify new runners appear in GitHub Actions settings.

**Scale trigger**: Only add runners when sustained queue time > 5 min OR CX43 CPU is >70% for 7 consecutive days.

## Verification

### Per-box service health

```bash
# All services running on paperwork-ops
ssh root@204.168.147.100 'docker ps --format "table {{.Names}}\t{{.Status}}"'

# All services running on paperwork-builders
ssh root@89.167.34.68 'docker ps --format "table {{.Names}}\t{{.Status}}"'

# All services running on paperwork-workers
ssh root@204.168.165.156 'docker ps --format "table {{.Names}}\t{{.Status}}"'
```

Expected: All containers in `Up` state.

### GHA self-hosted runners

```bash
# Full picture — id, name, status, busy, labels
gh api /repos/paperwork-labs/paperwork/actions/runners \
  --jq '.runners[] | {id, name, status, busy, labels: [.labels[].name]}'

# Quick "are at least N runners online" check (CI-friendly)
gh api /repos/paperwork-labs/paperwork/actions/runners \
  --jq '[.runners[] | select(.status == "online")] | length'
```

Expected: 5 runners, every one with `status: "online"`. Labels must include
`self-hosted`, `Linux`, `X64`, `hetzner`, and `paperwork-builders`. Workflows
that use `runs-on: [self-hosted, hetzner]` will not pick up jobs unless every
listed label is present on at least one runner — if a registration drift
removes the `hetzner` label, those jobs queue indefinitely.

If `length` returns `0` after a fresh bootstrap, the most likely causes are:

1. The registration token expired before `docker compose up -d` finished
   pulling the image (the pull is ~600 MB on a fresh box). Mint a new token
   and re-run.
2. The repo URL in `.env` uses `paperworklabs/paperwork` instead of
   `paperwork-labs/paperwork`.
3. The runner volume from a previous bootstrap still exists with stale
   credentials. Run `docker compose down -v` to wipe volumes, then start over.

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

## Repurposing (legacy Social VPS)

> **Merged from:** former `hetzner-socials-repurpose.md`. **Context:** a historical **CX22** box once hosted deprecated Brain-mirror **n8n** workflows; n8n was later removed from the production automation path (**WS-69**). Treat the notes below as **archival procedure** if you ever repurpose **a** small Hetzner VPS for experimentation — not as current required ops for the three-box fleet above.

**TL;DR:** If you clean legacy automation off a leftover VPS and reinstall tooling behind **Cloudflare Tunnel**, follow phased cleanup → install → wiring. Validate against [n8n-deprecated-cleanup.md](n8n-deprecated-cleanup.md) (deprecated) and [decommission-checklist.md](decommission-checklist.md).

### Historical context

- **VPS:** Hetzner CX22-class host, historically used for deprecated Brain-mirror n8n (Slack adapter, error notifications, infra slash command).
- **Exposure target:** UI and webhooks secured via **Cloudflare Tunnel** + **Zero Trust** (no raw public automation ports).

### Phase 1: Cleanup

Operational checklist when taking a leftover box from legacy mode into a clean slate:

- [ ] Take VPS snapshot (insurance backup).
- [ ] Stop and remove deprecated n8n containers (and orphan volumes if safe).
- [ ] Remove deprecated Brain-mirror workflow configs from disk (see [n8n-deprecated-cleanup.md](n8n-deprecated-cleanup.md)).
- [ ] Document current VPS state: `docker ps -a`, disk use, open ports (should be minimal pre-tunnel), kernel/hostname, and snapshot ID.

### Phase 2: Fresh install (if reviving automation on a box)

- [ ] **Docker Compose:** pinned images + tunnel sidecar (or separate tunnel container).
- [ ] **Cloudflare Zero Trust:** operator UI hostname + separate webhook hostname (narrow access / WAF as needed).
- [ ] **Backups:** daily export of app data to agreed object storage.
- [ ] **Health check:** lightweight HTTP endpoint monitored from Brain or external probe.

### Phase 3: Product wiring

- [ ] Platform API tokens in Vault (or sanctioned secret store).
- [ ] Publishing pipeline contracts (webhook or queue — define in product spec).
- [ ] Scheduling, idempotency, failure alerts via agreed channels.

### Access / rollback

- **SSH:** documented in Vault (Hetzner project + host key pinning per team practice).
- **Dashboard:** prefer Cloudflare Tunnel hostname over raw public IP.
- **Rollback:** restore from Phase 1 snapshot if repurpose fails mid-flight; leave legacy stack **stopped** until a second maintenance window.

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
| paperwork-builders | `/opt/paperwork-build/.env` | Studio Vault (`GHA_RUNNER_PAT`) |
| paperwork-workers | `/opt/paperwork-workers/.env` | Studio Vault |

### Scaling reference

| Signal | Action |
|---|---|
| paperwork-builders CPU >70% for 7d | Add more runner slots OR upgrade to CX53 |
| paperwork-workers RAM >70% for 7d | Upgrade to CX53 (same IP, brief reboot) |
| AxiomFolio walk-forward moves to Hetzner | Provision dedicated box or rescale workers |
