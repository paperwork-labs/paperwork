# Stage Quality Health: Diagnosis (2026 Q2)

## Symptom

`/admin/health` shows **Stage Quality — Critical** with subtitle
`0 invalid, 2834 monotonicity · recomputed nightly`. Every other dimension is
Healthy. Founder reports it has been Critical "always".

## Root cause

Two compounding bugs in the **health-evaluation layer** (not the stage math):

1. **Absolute-count threshold for a scale-dependent counter.**
   `HEALTH_THRESHOLDS["stage_monotonicity_max"] = 15`. The
   `monotonicity_issues` counter is the number of `(symbol, day-pair)` rows in
   the 120-day history window where `current_stage_days` does not match the
   previous row by +1 (or reset to 1 on a transition). For a 2,544-symbol
   universe × up to 120 snapshots per symbol, the denominator is ~305K
   row-pairs. 2,834 drift events is ~0.9% of that denominator — well within
   the expected noise floor after a single indicator recompute — but the
   threshold of "15 absolute" guarantees the dim stays red forever.

2. **Binary status mapping.** `_build_stage_dimension` uses
   `_dim_status(ok)` which returns only `green`/`red`. There is no
   intermediate `yellow`/`warning` path, so any drift >15 flips the dim
   straight to Critical even when `invalid_count=0` and `unknown_rate<1%`.

The counter itself is correct and useful (weekend-gap aware per
`test_monotonicity_weekend_fix.py`); it's a *data-hygiene signal for the
stage-days counter*, not an indicator-math failure. The label
"monotonicity" is also opaque to non-authors — what's being checked is
`current_stage_days` continuity across consecutive trading sessions.

## Evidence

- `backend/services/market/admin_health_service.py:44` — hardcoded
  `"stage_monotonicity_max": 15`.
- `backend/services/market/admin_health_service.py:415-419` — binary AND
  across `unknown_rate / invalid / monotonicity`.
- `backend/services/market/stage_quality_service.py:158-186` — counter
  increments per consecutive-trading-day pair, so the natural scale is
  "fraction of checked row-pairs", not an absolute.

## Fix (this PR)

Scoped to the health layer — **no changes to `indicator_engine.py` or
`stage_classifier.py`**.

1. Return `stage_history_rows_checked` from
   `stage_quality_summary` (purely additive field).
2. Replace the `stage_monotonicity_max` absolute threshold with
   `stage_days_drift_pct_warn` / `stage_days_drift_pct_crit` (rate-based)
   and add `stage_unknown_rate_crit` so we can distinguish warning from
   critical on unknowns too.
3. Return a three-state status (`green` / `yellow` / `red`) with an
   explicit `unknown` state when the counter cannot be computed —
   per `no-silent-fallback.mdc`, missing data surfaces as an explicit
   degraded state, not silent green.
4. Frontend subtitle: "0 invalid · 2834 stage-day drift (0.9%) ·
   recomputed nightly" (accurate copy).

## Expected prod state post-fix

Given current prod numbers (`invalid_count=0`, `unknown_rate<1%`,
`monotonicity_issues=2834`, `history_rows_checked ≈ 305k`):

- drift_pct ≈ 0.9% → below the 2% warn threshold
- Dimension flips to **Healthy** (green)
- Dashboard composite may drop from red to green depending on other dims.
