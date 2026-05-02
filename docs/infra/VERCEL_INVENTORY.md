---
owner: infra-ops
last_reviewed: 2026-04-30
doc_kind: reference
domain: infra
status: active
---
# Vercel Inventory — 2026-04-30

**Owner**: `infra-ops` persona.
**Team**: `team_RwfzJ9ySyLuVcoWdKJfXC7h5` (Paperwork Labs, Hobby tier).

## Production Projects

| Project | ID | Root Dir | Framework | Custom Domain | Status |
|---|---|---|---|---|---|
| `studio` | `prj_FZvJJnDdQqawjBpJAwC0SuwyMzFT` | `apps/studio` | Next.js | `paperworklabs.com` | active |
| `axiomfolio` | `prj_7L9N3FpOFRsc12tMfKKWa8q2lDLE` | `apps/axiomfolio` | Next.js | `www.axiomfolio.com` | active |
| `filefree` | `prj_DNPGX5GrYcwer9oANv90NKqIT67I` | `apps/filefree` | Next.js | `filefree.ai` | active |
| `launchfree` | `prj_hXQNtz5g7IAwx8lvCkODWxOyHcP7` | `apps/launchfree` | Next.js | `launchfree.ai` | active |
| `distill` | `prj_1TKlkMmY3vLVNfAfRxUY57z43m11` | `apps/distill` | Next.js | `distill.tax` | active |
| `design` | `prj_L14nQSlh3AognlHdC8KaJotVJzit` | `apps/design` | Vite (Storybook) | `design.paperworklabs.com` | active |

## Orphan Projects (not git-linked)

| Project | Path | Notes |
|---|---|---|
| `trinkets` | `apps/trinkets` | Needs `vercel link` + `vercel git connect` |

## Slated for Decommission

| Project | ID | Reason |
|---|---|---|
| `accounts` | `prj_DidXdCyMrnrigX5us9Sv4noysUil` | Clerk hosts Account Portal natively; redundant |

## Domain Summary

| Domain | Project | Type |
|---|---|---|
| `paperworklabs.com` | studio | apex |
| `www.axiomfolio.com` | axiomfolio | www |
| `filefree.ai` | filefree | apex |
| `launchfree.ai` | launchfree | apex |
| `distill.tax` | distill | apex |
| `design.paperworklabs.com` | design | subdomain |

## Deploy Limits

- **Hobby tier**: 100 deploys/day
- Pre-deploy guard: `scripts/check_pre_deploy.py`

## Related

- `docs/infra/VERCEL_PROJECTS.md` — detailed project documentation
- `docs/infra/VERCEL_LINKING.md` — linking and env workflows
- `docs/infra/VERCEL_AUTO_PROMOTE.md` — production promotion
- `docs/runbooks/pre-deploy-guard.md` — quota enforcement
