# Portfolio Sync Completeness — 2026 Q2 (Wave 8 spec)

**Status**: ACTIVE — Wave 8 spec (blocks W3.7 FileFree 1.1.0).
**Created**: 2026-04-22
**Decision log**: [D144](../KNOWLEDGE.md) commitment #12.
**Companions**: [PLATFORM_REVIEW_2026Q2.md](PLATFORM_REVIEW_2026Q2.md) (Chapter 8) · [BROKER_COVERAGE_TRACKER.md](BROKER_COVERAGE_TRACKER.md) (§7 ACATS playbook) · [GAPS_2026Q2.md](GAPS_2026Q2.md) (G22 FlexQuery validator).

---

## 1 — Founder symptoms (2026-04-22)

Direct quotes pinning scope:

1. *"i dont see lots and stuff in schwab and i am wondering if that is because these positions were acats — we should figure out a strategy to ingest that info"*
2. *"svhwab options dont show either — we should ensure we get options too from portfolios"*

Scope of this spec: **diagnose before coding**, then build the 4-path cost-basis recovery + surface sync completeness to the user.

---

## 2 — Why "just fix it" is wrong (and what we learned from D120 / D121)

Two recent ships already addressed the symptom layer:

- **[D139](../KNOWLEDGE.md)** (2026-04-22) — Schwab options sync fix: the `positionEffect` classification was dropping short-call and long-put positions from the normalized output. Merged to main.
- **[D140](../KNOWLEDGE.md)** (2026-04-22) — IBKR option tax-lot backfill via FIFO matcher: `OpenPositions` FlexQuery section was not being joined against historical `Trades` for option-specific lot identities. Backfill script ships per migration.

Per **[D120](../KNOWLEDGE.md)** "merging to main does not equal shipped": D139 and D140 could be (a) not deployed yet on the founder's Render instance, (b) deployed but needs a fresh sync run to populate data, (c) deployed and populated but blocked by a frontend cache / stale component. Per **[D121](../KNOWLEDGE.md)** evidence-based diagnosis: do the runbook first, only write new code for the residual (which may be zero).

Founder also clarified: **Schwab HSA has no options trading enabled** — so symptom 2 on the HSA account is expected ("you don't see options because there aren't any; the data is correct"). The right fix there is a **`options_enabled: Boolean` field on `BrokerConnection`** so the UI renders "Options: not enabled on this account" instead of the empty-state that reads like a bug.

Symptom 1 (Schwab missing tax lots on ACATS-transferred positions) is the real data recovery problem. That one needs the 4-path fallback.

---

## 3 — Diagnostic runbook (Wave 8.0, ship first)

Run these in order; STOP when you find the actual cause. Each step produces evidence.

### Step 1 — Confirm D139 / D140 are live in prod

```bash
# Current Render deploy SHA for API and worker
gh api repos/axiomfolio/axiomfolio/deployments \
  --jq '.[] | select(.environment=="production") | {sha: .sha, created: .created_at}' \
  | head -5

# D139 / D140 were merged in commits X / Y — verify both SHAs are <= current deploy SHA
git log --oneline origin/main | grep -E "(D139|D140|options.*positionEffect|option.*tax.?lot.*backfill)"
```

**Evidence**: both SHAs ≤ current prod SHA → proceed to Step 2. If not → wait for deploy; re-run later.

### Step 2 — Check `/api/v1/market-data/admin/health`

```bash
curl -s https://api.axiomfolio.com/api/v1/market-data/admin/health \
  -H "Authorization: Bearer $TOKEN" | jq .
```

**Evidence to collect**:
- `sync_runs[].broker` includes `schwab` and `ibkr` with `last_run_ok: true` within the last 24h.
- `sync_runs[].symbols_written` > 0 on the most recent run.
- Any `error_counters` that spiked on 2026-04-22 or after.

### Step 3 — Probe the founder's actual Schwab account

Write a one-off admin script (do not deploy; run via `make task-run TASK=admin.sync_probe`):

```python
from backend.services.clients.schwab_client import SchwabClient
client = SchwabClient.for_user(user_id=1)  # founder user_id
positions = client.get_positions(account_id="<schwab-hsa-account>")
# Look specifically for: lot-level detail, cost_basis per lot, option positions if any
print(json.dumps(positions, indent=2))
```

**Evidence**:
- Count of positions with `averagePrice != 0` vs. `averagePrice == 0` (the ACATS-missing-cost-basis case).
- Count of option positions returned (expected 0 for HSA per founder; any number > 0 reveals bug).
- Raw `positionEffect` values on option positions (if any).

### Step 4 — Compare UI state to backend state

Open `https://app.axiomfolio.com/portfolio/schwab-hsa` and inspect network tab:
- `/api/v1/portfolio/positions?account_id=...` response body.
- `/api/v1/portfolio/tax-lots?account_id=...` response body.
- Frontend cache freshness (`stale-while-revalidate` TanStack Query key timestamps).

**Evidence**: if backend returns lot data that the frontend doesn't render, the bug is in the `PortfolioTaxCenter.tsx` / `TaxLotsTable.tsx` rendering path — not in sync.

### Step 5 — Classify root cause

After Steps 1–4, the symptom falls into exactly one of:

| Root cause | Fix |
|------------|-----|
| A. Deploy not live yet | Wait; re-verify |
| B. Deploy live but stale sync | Trigger fresh sync via `/api/v1/portfolio/sync/trigger?broker=schwab&account_id=...`; wait 5min; re-verify UI |
| C. Deploy live, data synced, frontend cache stale | Force refetch; if persists, fix frontend query invalidation |
| D. Backend returns cost-basis gaps on ACATS lots | Proceed to Wave 8.2–8.4 (4-path recovery) |
| E. HSA has no options (expected, not a bug) | Ship `BrokerConnection.options_enabled = false` + UI copy change (Wave 8.1) |
| F. Schwab options data truly missing after D139 ship | Root-cause the remaining D139 gap; fix; reship |

This runbook lives as an admin-only page at `/admin/diagnostics/sync-completeness` so the founder can re-run it self-serve.

---

## 4 — Wave 8 scope after runbook

Regardless of what the runbook finds, these ships stand because they're independently valuable (a better UI + schema even if D139/D140 already covered the data):

### 8.0 — Diagnostic runbook page (Week 1 Day 1)

- Admin-only React page at `/admin/diagnostics/sync-completeness`.
- Runs steps 1–4 programmatically; produces a "Here's what's happening on your account" report.
- Exposes raw API responses side-by-side with frontend-state snapshots for visual diffing.

### 8.1 — Schema additions (Week 1 Day 2)

Additive-only migration — no drops, no renames ([D144](../KNOWLEDGE.md) reversibility policy).

```python
# backend/alembic/versions/XXXX_wave8_sync_completeness.py
# TaxLot enrichment
op.add_column('tax_lot', sa.Column('cost_basis_source', sa.Enum(
    'broker_reported', 'acats_recovered_csv', 'acats_recovered_1099b',
    'manual_entry', 'unknown', name='cost_basis_source_enum'
), server_default='unknown', nullable=False))
op.add_column('tax_lot', sa.Column('cost_basis_quality', sa.Enum(
    'high', 'medium', 'low', name='cost_basis_quality_enum'
), server_default='high', nullable=False))
op.add_column('tax_lot', sa.Column('acats_transferred', sa.Boolean(), server_default='false', nullable=False))
op.add_column('tax_lot', sa.Column('prior_broker_id', sa.Integer(), sa.ForeignKey('broker_account.id'), nullable=True))

# BrokerConnection capabilities
op.add_column('broker_connection', sa.Column('options_enabled', sa.Boolean(), nullable=True))
op.add_column('broker_connection', sa.Column('margin_enabled', sa.Boolean(), nullable=True))
op.add_column('broker_connection', sa.Column('account_type', sa.String(32), nullable=True))  # taxable | ira | hsa | 401k | trust
```

**Backfill strategy**: existing `TaxLot` rows get `cost_basis_source='broker_reported'` if `cost_basis > 0`, else `'unknown'`. Backfill runs inline in the migration — safe because table is user-scoped and additive fields.

### 8.2 — CSV import (Path 3; Week 1 Day 3–4)

New endpoint: `POST /api/v1/portfolio/tax-lots/import-csv`

Accepts multipart form with CSV columns:
```
symbol,acquired_date,quantity,cost_basis_per_share,total_cost_basis,sub_account_id,lot_notes
AAPL,2022-03-14,100,145.20,14520.00,schwab-hsa-123,ACATS from Fidelity
MSFT,2021-07-09,50,289.30,14465.00,schwab-hsa-123,
```

Server-side validations:
- Symbol must match an existing `Symbol` row.
- `acquired_date` parseable as ISO 8601.
- `quantity * cost_basis_per_share` matches `total_cost_basis` within $0.01 tolerance.
- `sub_account_id` must resolve to a `BrokerConnection` owned by `current_user`.

Writes `TaxLot` rows with `cost_basis_source='acats_recovered_csv'`, `cost_basis_quality='medium'` (user-asserted), `acats_transferred=true`.

### 8.3 — 1099-B PDF parser (Path 2; Week 1 Day 5 — Week 2 Day 2)

Uses existing `pymupdf` dependency. Parser contract:

```python
# backend/services/tax/parsers/form_1099b.py
class Form1099BParser:
    def parse(self, pdf_bytes: bytes) -> list[RealizedEventRow]:
        """
        Extract Box 1a (symbol), Box 1b (acquired), Box 1c (sold),
        Box 1d (proceeds), Box 1e (cost basis), Box 1f (accrued market discount),
        Box 1g (wash sale loss disallowed), Box 2 (type - short/long).
        
        Returns list of RealizedEventRow; caller decides whether to
        write as TaxLot (for year-end unknowns) or RealizedEvent (for closes).
        """
```

UI: upload page at `/settings/tax/import-1099b` with broker-specific template detection (Schwab 1099-Composite vs. IBKR 1099-B vs. TastyTrade 1099-B all have different PDF layouts).

Writes events with `cost_basis_source='acats_recovered_1099b'`, `cost_basis_quality='high'` (IRS-authoritative).

### 8.4 — Manual entry (Path 4; Week 2 Day 3–4)

New UI: `/desk/portfolio/{account_id}/lots` — editable grid of `TaxLot` rows for one account.

- Inline edit of `acquired_date`, `quantity`, `cost_basis_per_share`.
- Add new row / delete row with confirmation.
- "I confirm this data is accurate" checkbox required before save.
- Writes with `cost_basis_source='manual_entry'`, `cost_basis_quality='low'`.
- Audit event `TAX_LOT_MANUAL_EDIT` captures before/after values.

### 8.5 — Sync completeness API + UI (Week 2 Day 5)

New endpoint: `GET /api/v1/portfolio/sync-completeness`

```json
{
  "accounts": [
    {
      "account_id": 123,
      "broker": "schwab",
      "account_type": "hsa",
      "options_enabled": false,
      "completeness": {
        "positions_synced": true,
        "tax_lots_synced": "partial",
        "missing_cost_basis_count": 7,
        "missing_cost_basis_dollar_exposure": 45230.50,
        "options_expected": false,
        "last_sync": "2026-04-22T14:30:00Z"
      },
      "recovery_suggestions": [
        {"path": "csv_import", "label": "Upload CSV for 7 ACATS positions", "url": "/settings/tax/import-csv"},
        {"path": "form_1099b", "label": "Upload Schwab 1099-B (if closed positions)", "url": "/settings/tax/import-1099b"}
      ]
    }
  ]
}
```

UI: banner on `/portfolio/tax-center` when any account has `completeness.tax_lots_synced != "complete"`. Click → `/settings/tax/import-csv` with the account pre-selected.

---

## 5 — The 4-path ACATS recovery (re-stated with ownership)

| Path | Source | Quality | Who owns data | UI surface |
|------|--------|---------|---------------|-----------|
| 1 | Broker-native API | High | Broker | automatic; already the happy path |
| 2 | 1099-B PDF parse | High (IRS authoritative) | User (uploads PDF) | `/settings/tax/import-1099b` |
| 3 | CSV import | Medium (user-asserted) | User | `/settings/tax/import-csv` |
| 4 | Manual entry | Low | User | `/desk/portfolio/{id}/lots` |

Fallback order: always try Path 1; escalate to Path 2 on year-end (wins over 3 because IRS-authoritative); only fall to Paths 3 / 4 when brokers physically don't return the data.

---

## 6 — Cross-broker wash-sale implications

ACATS cost-basis recovery unlocks **cross-broker wash-sale watching** (Wave 3.7, [G20](GAPS_2026Q2.md)): we can't detect a wash-sale between a Schwab HSA loss and an IBKR taxable buy if we don't know when/what was bought in Schwab. Wave 8 is therefore a **blocking dependency** for the Quant Desk tax-alpha moat layer. This is the single most important reason to ship Wave 8 first.

---

## 7 — Testing plan

**Unit tests**:
- `Form1099BParser` round-trips on 3 Schwab / 2 IBKR / 1 TastyTrade 1099-B fixtures.
- CSV import validates column headers, date formats, arithmetic consistency.
- `cost_basis_source` enum values properly serialized to FileFree 1.1.0 export.

**Integration tests**:
- Import CSV → verify `TaxLot` rows created with `acats_transferred=true`.
- Import 1099-B → verify `RealizedEvent` rows + `TaxLot` updates.
- Multi-tenancy isolation: User A's import does not touch User B's lots.

**Founder acceptance (the only test that matters)**:
1. Founder opens `/admin/diagnostics/sync-completeness` on his Schwab HSA.
2. Sees classification of what's missing with a specific count.
3. Uploads 1099-B or CSV to close the gap.
4. Verifies `/portfolio/tax-center/schwab-hsa` now shows complete lots.
5. Verifies FileFree preview export includes the recovered lots with the correct `cost_basis_source` flag.

---

## 8 — Rollout waves

Wave 8 sub-waves:

| Sub-wave | Scope | Week | Gates |
|----------|-------|------|-------|
| 8.0 | Diagnostic runbook page | W1 D1 | None; ship first |
| 8.1 | Schema migration + `options_enabled` copy fix | W1 D2 | 8.0 findings reviewed |
| 8.2 | CSV import | W1 D3–4 | 8.1 ships |
| 8.3 | 1099-B parser | W1 D5 – W2 D2 | 8.1 ships |
| 8.4 | Manual entry UI | W2 D3–4 | 8.1 ships |
| 8.5 | Sync-completeness API + UI banner | W2 D5 | 8.2 + 8.4 ship |

Wave 8 as a whole must complete before Wave 3.7 FileFree 1.1.0 begins.

---

## 9 — Open questions to pin during W8.0

- **Which Schwab account types return cost-basis fields reliably?** Expected: taxable ≥ IRA ≥ HSA (transferred-in). Confirm via probe.
- **Does Schwab's 1099-B layout change between HSA custodial and brokerage?** Parser needs to handle both.
- **Is there a Schwab-specific ACATS-aware endpoint we're missing?** TDA legacy had `/accounts/{id}/transactions?type=TRANSFER` — Schwab migration may expose similar.
- **IBKR FlexQuery completeness on ACATS-in**: does `Transfers` section include cost basis for inbound ACATS? G22 validator per handoff should close this.

Pin answers as inline comments in W8.0 runbook output.

---

*Last reviewed: 2026-04-22. Reviewed again after W8.5 ships.*
