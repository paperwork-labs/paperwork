# Slack Sprint Messaging (Agent-Only)

Sprint operations run as high-quality agent output in Slack. We do not depend on Canvas or List templates.

## Channel

- Canonical sprint channel: `#sprints`
- Automated posts:
  - Monday kickoff from `Sprint Kickoff`
  - Friday retro from `Sprint Close`

## Daily Operating Pattern

1. Keep all sprint execution in the kickoff thread.
2. Post concise updates in this format:
   - `Done:` shipped items and merged PRs
   - `Next:` immediate planned work
   - `Blocked:` blockers with owner and ETA
3. When decisions are made, capture them in-thread with clear rationale.

## Midweek and Close Rhythm

- **Midweek pulse (Wednesday)**: one threaded update covering progress, risk, and scope changes.
- **Friday close**: retro post summarizes shipped work, misses, quality, and next sprint preview.

## Message Quality Standard

- Lead with outcomes, not activity.
- Use short sections and bullets.
- Include links to PRs/issues when relevant.
- Keep tone direct, specific, and operator-ready.
