'use strict';

// Body-text + title block-list for auto-merge workflows.
//
// Wave 0 / T1.0c — fixes the PR #664 silent-merge root cause: prior to this
// module, every auto-merge surface (auto-merge-sweep.yaml, auto-merge-agent-prs.yaml,
// auto-merge.yaml) only consulted the PR's *labels*. A PR whose body said
// "DO NOT MERGE" or "🛑 HOLD FOR FOUNDER" would still squash-merge if its
// labels were clean.
//
// This module is the single source of truth. Every auto-merge workflow that
// can squash-merge a PR must `require()` it and call
// `hasBlockingPhraseInBodyOrTitle(pr)` BEFORE invoking
// `github.rest.pulls.merge()`. Tests live at
// `scripts/check_auto_merge_body_guard.mjs` and are wired into
// `.github/workflows/code-quality.yaml`.
//
// Doctrine: master plan T1.0c (`docs/plans/PAPERWORK_LABS_2026Q2_MASTER_PLAN.md`),
// `.cursor/rules/no-silent-fallback.mdc`.

/**
 * Canonical block-list of regular expressions matched against the
 * concatenation of `pr.title + "\n" + pr.body`.
 *
 * Adding a phrase: think hard about false-positives. The cost of a
 * false-positive (PR has to be relabeled / re-pushed) is far less than the
 * cost of a false-negative (silent merge of "DO NOT MERGE" — that's the bug
 * we're fixing). When in doubt, add the phrase.
 */
const BLOCKING_PHRASES = [
  // Variant spelling tolerated: "DO NOT MERGE", "DO_NOT_MERGE", "DO-NOT-MERGE", lower or upper.
  /\bDO[\s_-]*NOT[\s_-]*MERGE\b/i,
  // Holds: "HOLD FOR REVIEW / FOUNDER / MERGE / LATER / CHECK / SIGNOFF / SIGN-OFF / APPROVAL".
  /\bHOLD\s+FOR\s+(REVIEW|FOUNDER|MERGE|LATER|CHECK|SIGNOFF|SIGN-OFF|APPROVAL)\b/i,
  // Stop-sign emoji is the universal "halt" signal.
  /🛑/,
  // Conventional WIP markers.
  /\[\s*WIP\s*\]/i,
  /\bWIP\s*:/i,
];

/**
 * @param {{ title?: string | null, body?: string | null } | null | undefined} pr
 * @returns {{ blocked: true, phrase: string, pattern: string } | { blocked: false }}
 */
function hasBlockingPhraseInBodyOrTitle(pr) {
  const title = (pr && pr.title) || '';
  const body = (pr && pr.body) || '';
  const haystack = `${title}\n${body}`;
  for (const re of BLOCKING_PHRASES) {
    const m = haystack.match(re);
    if (m) {
      return { blocked: true, phrase: m[0], pattern: re.toString() };
    }
  }
  return { blocked: false };
}

module.exports = { hasBlockingPhraseInBodyOrTitle, BLOCKING_PHRASES };
