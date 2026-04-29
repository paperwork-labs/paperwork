# Brain Self-Merge Graduation

Brain self-merge starts in a narrow data-only tier and graduates only after a clean track record. The source of truth is `apis/brain/data/self_merge_promotions.json`, with service logic in `apis/brain/app/services/self_merge_gate.py`.

## Tiers

- `data-only`: Brain may self-merge PRs touching only `apis/brain/data/**`, `docs/**`, and `.cursor/rules/**`.
- `brain-code`: Brain may also self-merge paths under `apis/brain/**`. Promotion requires 50 clean data-only self-merges.
- `app-code`: Brain may self-merge app and package code. Promotion requires 50 clean brain-code self-merges.

Every PR path must be allowed by the current tier. If any path is outside the tier, `pr_merge_sweep` skips the merge and logs:

```text
self-merge gate: PR #<number> has paths outside current tier (<tier>); skipping
```

## Status

Read status through the admin endpoint:

```bash
curl -H "X-Brain-Secret: $BRAIN_API_SECRET" \
  "$BRAIN_API_URL/api/v1/admin/self-merge-status"
```

Example response:

```json
{
  "success": true,
  "data": {
    "current_tier": "data-only",
    "clean_merge_count": 12,
    "eligible_for_promotion": false,
    "recent_merges_last_10": [],
    "recent_reverts_last_5": []
  }
}
```

## Promotion

The daily `self_merge_promotion` scheduler checks the gate once per day. If Brain has at least 50 clean merges in the current tier and no current-tier revert in the last 7 days, it promotes to the next tier and logs:

```text
Brain promoted from <from-tier> to <to-tier>
```

Founder override uses the same eligibility check:

```bash
curl -X POST -H "X-Brain-Secret: $BRAIN_API_SECRET" \
  "$BRAIN_API_URL/api/v1/admin/self-merge-promote"
```

If the gate is not eligible, the endpoint returns HTTP 409.

## Reverts

Record a revert when a Brain self-merged PR is rolled back because it caused or plausibly contributed to a production issue, post-merge CI failure, deploy failure, or operator-triggered rollback. Recent current-tier reverts block graduation for 7 days, and reverts in the 30-day clean window remove the original PR from the clean merge count.
