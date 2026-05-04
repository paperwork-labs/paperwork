# Brain Conversations — Postgres Backfill Runbook

**Applies to:** T1.0d Wave 0 PR — Conversations canonical Postgres migration  
**Author:** T1.0d subagent (claude-4.6-sonnet-medium-thinking)  
**Review gate:** Orchestrator (Opus) diff-review required before running in production

---

## Context

Prior to T1.0d, Brain Conversations were stored as JSON files in
`apis/brain/data/conversations/` with a SQLite FTS sidecar
(`apis/brain/data/conversations.fts.db`).  Render's ephemeral disk
means a service recycle wipes the only copy.

T1.0d rewrites `services/conversations.py` to use Postgres as the
canonical store.  **This runbook must be executed once before restarting
the Brain service** with the new code, so existing conversations are not
lost.

---

## Pre-deploy checklist

- [ ] Alembic migrations 015 have run on the target database
      (`alembic upgrade head` — verify with `alembic current`).
- [ ] A GCS (or local) snapshot of `apis/brain/data/conversations/` has
      been taken as a backup.
- [ ] `DATABASE_URL` in the Brain environment points to the correct Neon
      Postgres instance.

### Snapshot the JSON directory (before anything else)

```bash
# Option A — GCS (preferred for production)
gsutil -m cp -r apis/brain/data/conversations/ gs://paperwork-brain-backups/conversations-$(date +%Y%m%d)/

# Option B — local archive
tar -czf conversations-backup-$(date +%Y%m%d).tar.gz apis/brain/data/conversations/
```

---

## Step 1 — Deploy the PR

Merge and let Render auto-deploy.  Do **not** restart the service yet
(the existing JSON-backed service will be replaced by the new Postgres
service on restart — run the backfill first).

Actually: the migration order is:
1. Run Alembic migrations (015) — safe to run while old code is live.
2. Run backfill script (below).
3. Deploy / restart Brain service with new conversations.py.

---

## Step 2 — Run Alembic migration 015

```bash
# Via Render → Web Service → "Shell" or "render run"
cd /app
python -m alembic upgrade head
```

Verify:
```bash
python -m alembic current
# Should show: 015 (head)
```

---

## Step 3 — Dry-run the backfill

SSH into the Brain Render service or use `render run`:

```bash
render run --service brain-api -- \
  python -m apis.brain.scripts.backfill_conversations_to_postgres --dry-run
```

Expected output (example):
```
2026-05-04 12:00:00 INFO backfill_conversations: scanned=47 file_count (dry_run=True)
2026-05-04 12:00:00 INFO backfill_conversations: [DRY-RUN]: would insert conv <uuid> ("Daily Briefing — 2026-04-01") with 3 message(s)
... (one line per conversation) ...
2026-05-04 12:00:01 INFO backfill_conversations: scanned=47 file_count, inserted=47 conversations, skipped=0 existing, errors=0
2026-05-04 12:00:01 INFO backfill_conversations: [DRY-RUN]: would have inserted 47 conversations
```

Verify:
- `scanned` matches the number of `*.json` files in the conversations directory.
- `errors=0`.
- Exit code 0.

If `errors > 0`, review the log lines above the summary for the specific
file(s) that failed, fix or skip them, then re-run the dry-run.

---

## Step 4 — Run the actual backfill

```bash
render run --service brain-api -- \
  python -m apis.brain.scripts.backfill_conversations_to_postgres
```

Expected output:
```
...
2026-05-04 12:01:30 INFO backfill_conversations: backfill: SUCCESS — 47 inserted, 0 skipped
```

Exit code must be **0**.  If it is non-zero, do NOT proceed — review errors,
fix, and re-run.

---

## Step 5 — Verify in Studio

1. Open `https://paperworklabs.com/admin/brain/conversations` on your phone
   (Studio PWA).
2. Confirm existing conversation threads are visible and scrollable.
3. Post a new test message to one thread.
4. Confirm the reply appears and the conversation `updated_at` is refreshed.

---

## Step 6 — Render-restart survival check

1. In Render dashboard → Brain API → "Manual Deploy" or click "Restart".
2. Wait for the service to return to `Live`.
3. Re-open Studio on phone → `/admin/brain/conversations`.
4. Confirm all threads are still present (data survives the restart, proving
   Postgres is the source of truth, not the ephemeral disk).

---

## Step 7 — Post-verification cleanup (separate follow-up PR)

After 24 hours of healthy operation:

1. Open a separate PR titled `chore: remove legacy conversations JSON store`.
2. In that PR:
   - Delete `apis/brain/data/conversations/` from disk (or add to `.gitignore`
     + add a `startup` cleanup hook).
   - Delete `apis/brain/data/conversations.fts.db`.
3. Do **not** delete these files before 24-hour verification is complete.

---

## Rollback procedure

If production is broken after deploy:

1. Revert the PR (`git revert` or Render "Rollback to previous deploy").
2. The JSON files are still on disk (the backfill script does not delete them).
3. The old JSON-backed service will resume reading from disk.
4. Postgres rows are harmless — the old service ignores them.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `ImportError: cannot import app modules` | Script not run from repo root | `cd /app && PYTHONPATH=apis/brain python -m apis.brain.scripts...` |
| `ProgrammingError: column "content_tsv" does not exist` | Migration 015 not yet applied | Run `alembic upgrade head` first |
| `errors > 0` in backfill output | Malformed JSON files | Check specific filenames in log, fix or delete the bad files |
| Conversations missing after deploy | Backfill was skipped | Re-run backfill (idempotent — existing rows are skipped) |
| `COUNTER DRIFT` in log | Bug in backfill script | File a bug; restore from JSON backup |
