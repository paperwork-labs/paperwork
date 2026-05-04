#!/usr/bin/env node
/**
 * Regression test for `.github/scripts/auto-merge-body-guard.cjs`.
 *
 * Wired into `.github/workflows/code-quality.yaml` so any change to the
 * shared body-guard module (or to this test) gets re-validated on every PR.
 *
 * Run locally:  node scripts/check_auto_merge_body_guard.mjs
 *
 * Refs: master plan T1.0c, `.cursor/rules/no-silent-fallback.mdc`,
 * Wave 0 / PR #664 silent-merge root cause.
 */
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const guardPath = path.join(__dirname, '..', '.github', 'scripts', 'auto-merge-body-guard.cjs');
const { hasBlockingPhraseInBodyOrTitle } = require(guardPath);

/** @type {Array<{ pr: { title?: string|null, body?: string|null }, blocked: boolean, name: string }>} */
const cases = [
  // ---- Should BLOCK ----
  {
    pr: { title: 'feat: add cool thing', body: 'DO NOT MERGE — pending CFO sign-off' },
    blocked: true,
    name: 'DO NOT MERGE in body (canonical)',
  },
  {
    pr: { title: 'DO_NOT_MERGE: chore: tweak readme', body: '' },
    blocked: true,
    name: 'DO_NOT_MERGE in title with underscores',
  },
  {
    pr: { title: 'feat: foo', body: 'do-not-merge yet — see #123' },
    blocked: true,
    name: 'do-not-merge with hyphens, lowercase',
  },
  {
    pr: { title: 'feat: foo', body: 'HOLD FOR REVIEW by founder' },
    blocked: true,
    name: 'HOLD FOR REVIEW',
  },
  {
    pr: { title: 'feat: foo', body: 'HOLD FOR FOUNDER\nbody continues' },
    blocked: true,
    name: 'HOLD FOR FOUNDER',
  },
  {
    pr: { title: 'feat: foo', body: 'HOLD FOR sign-off from QA' },
    blocked: true,
    name: 'HOLD FOR SIGN-OFF (with hyphen)',
  },
  {
    pr: { title: 'feat: foo', body: '🛑 do not merge yet, ARS run pending' },
    blocked: true,
    name: '🛑 emoji in body',
  },
  {
    pr: { title: '🛑 wip', body: '' },
    blocked: true,
    name: '🛑 emoji in title',
  },
  {
    pr: { title: '[WIP] feat: refactor billing', body: '' },
    blocked: true,
    name: '[WIP] in title',
  },
  {
    pr: { title: '[ WIP ] feat: foo', body: '' },
    blocked: true,
    name: '[WIP] with surrounding spaces',
  },
  {
    pr: { title: 'WIP: feat: foo', body: '' },
    blocked: true,
    name: 'WIP: prefix in title',
  },
  {
    pr: { title: 'feat: foo', body: 'WIP: still drafting acceptance criteria' },
    blocked: true,
    name: 'WIP: prefix in body',
  },

  // ---- Should NOT block (no false-positives) ----
  {
    pr: { title: 'feat: add things', body: 'normal body, no markers' },
    blocked: false,
    name: 'plain feat PR',
  },
  {
    pr: { title: 'docs: chip-list', body: 'Holiday work followed' },
    blocked: false,
    name: 'word "Hold" without "FOR <kind>" clause',
  },
  {
    pr: { title: 'feat: foo', body: 'household renovation discussed in design doc' },
    blocked: false,
    name: 'household — substring contains hold but not the phrase',
  },
  {
    pr: { title: 'feat: foo', body: 'pipwip and swipe references in tests' },
    blocked: false,
    name: 'pipwip / swipe — no false-positive on "wip" substring',
  },
  {
    pr: { title: 'feat: foo', body: 'mention of merge later in passing' },
    blocked: false,
    name: 'random "merge" mention — does not match DO_NOT_MERGE',
  },
  {
    pr: { title: 'feat: foo', body: '' },
    blocked: false,
    name: 'empty body',
  },
  {
    pr: { title: 'feat: foo', body: null },
    blocked: false,
    name: 'null body',
  },
  {
    pr: { title: '', body: '' },
    blocked: false,
    name: 'empty title and body',
  },
  {
    pr: null,
    blocked: false,
    name: 'null pr (defensive)',
  },
];

let failures = 0;
for (const c of cases) {
  const got = hasBlockingPhraseInBodyOrTitle(c.pr);
  const ok = got.blocked === c.blocked;
  if (!ok) {
    failures += 1;
    const detail = got.blocked
      ? `unexpectedly blocked by ${got.phrase} (${got.pattern})`
      : 'expected to be blocked but was not';
    console.error(`FAIL: ${c.name} — ${detail}`);
  } else {
    const tag = got.blocked ? `blocked by ${got.phrase}` : 'allowed';
    console.log(`PASS: ${c.name} — ${tag}`);
  }
}

if (failures > 0) {
  console.error(`\n${failures} of ${cases.length} test case(s) failed`);
  process.exit(1);
}
console.log(`\nAll ${cases.length} test cases passed`);
