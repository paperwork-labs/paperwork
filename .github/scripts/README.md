# GitHub Actions helper scripts

## `lhci_summary_to_brain.py`

Parses Lighthouse-CI output left under `.lighthouseci/` (after `lhci collect`) into `apis/brain/data/lighthouse_ci_runs.json`. It walks JSON reports produced by Lighthouse, averages category scores (performance, accessibility, best-practices, SEO), captures key timings (LCP, CLS, TBT, FCP), stamps `run_at`, `commit_sha` (`GITHUB_SHA` when provided), appends one entry, and keeps the latest 200 runs.

Called from [`.github/workflows/lighthouse-ci.yml`](../workflows/lighthouse-ci.yml) on **push to `main`** after `lhci collect` / `assert` / `upload`.

The **`Lighthouse CI` workflow**:

- Runs on PRs labelled `lighthouse` (or pushes to `main`) to conserve minutes on unlabelled PRs; main always runs Lighthouse against `https://studio.paperworklabs.com` unless Vercel status provides a preview URL elsewhere in the workflow.
- On main, persists the summarized JSON via this script so Brain’s Paperwork Operating Score **pillar `web_perf_ux`** reads the newest run from that file locally.
