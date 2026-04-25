#!/usr/bin/env python3
"""Promote a sprint follow-up bullet to the Outcome section.

Sprint markdown files under `docs/sprints/` keep two living lists:

  ## Outcome
  - shipped 2026-04-25: bullet text (PR #142)

  ## Follow-ups
  - pending bullet text

When a follow-up actually ships, the operator (or an agent) wants to
move the line from `Follow-ups` to `Outcome` *in place*, with a date
stamp and an optional PR reference, so the Studio "Living tracker"
view shows it as shipped without losing chronological context. This
script does that — by substring match, with `--dry-run` and `--all`
flags so you can preview before writing.

Usage:

    # Promote the first followup matching "VMP-SUMMARY merge", attach PR 143:
    python3 scripts/sprint_promote_followup.py \\
        docs/sprints/DOCS_STREAMLINE_AND_TRACKERS_2026Q2.md \\
        "VMP-SUMMARY merge" --pr 143

    # Preview without writing:
    python3 scripts/sprint_promote_followup.py <file> "<match>" --dry-run

    # Promote multiple matches at once:
    python3 scripts/sprint_promote_followup.py <file> "Auto-generate" --all

The script intentionally does not auto-regenerate `tracker-index.json`;
run `python3 scripts/generate_tracker_index.py` after promotion (or let
the existing CI gate flag the drift).
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

OUTCOME_HEADERS = ["## Outcome", "## Outcomes"]
FOLLOWUPS_HEADERS = ["## Follow-ups", "## Followups", "## Follow ups"]
SECTION_HEADER_RE = re.compile(r"^##\s+", re.MULTILINE)


def find_section_block(text: str, headers: list[str]) -> tuple[int, int, str] | None:
    """Return (start_idx, end_idx, header_used) for the first matching `##` section."""
    for header in headers:
        idx = text.find(header)
        if idx == -1:
            continue
        # Section ends at the next "## " heading or EOF.
        next_match = SECTION_HEADER_RE.search(text, idx + len(header))
        end = next_match.start() if next_match else len(text)
        return idx, end, header
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("sprint_file", help="Path to docs/sprints/<name>.md")
    ap.add_argument("match", help="Substring to match against follow-up bullets")
    ap.add_argument("--pr", type=int, default=None, help="PR number to tag the shipped bullet with")
    ap.add_argument("--date", default=None, help="ISO date (YYYY-MM-DD); defaults to today UTC")
    ap.add_argument("--all", action="store_true", help="Promote every matching follow-up (else first only)")
    ap.add_argument("--dry-run", action="store_true", help="Print the new file without writing")
    args = ap.parse_args()

    path = Path(args.sprint_file)
    if not path.is_file():
        print(f"error: {path} not found", file=sys.stderr)
        return 2

    text = path.read_text(encoding="utf-8")
    outcome = find_section_block(text, OUTCOME_HEADERS)
    followups = find_section_block(text, FOLLOWUPS_HEADERS)

    if not followups:
        print(f"error: no Follow-ups section in {path}", file=sys.stderr)
        return 2
    if not outcome:
        print(f"error: no Outcome section in {path}", file=sys.stderr)
        return 2

    f_start, f_end, _ = followups
    o_start, o_end, o_header = outcome

    fu_block = text[f_start:f_end]
    out_block = text[o_start:o_end]

    fu_lines = fu_block.splitlines(keepends=True)
    out_lines = out_block.splitlines(keepends=True)

    bullet_re = re.compile(r"^\s*-\s+(.+)$")

    promoted: list[str] = []
    new_fu_lines: list[str] = []
    needle = args.match.lower()
    for line in fu_lines:
        m = bullet_re.match(line)
        if m and needle in m.group(1).lower():
            if not args.all and promoted:
                new_fu_lines.append(line)
                continue
            promoted.append(line)
            continue
        new_fu_lines.append(line)

    if not promoted:
        print(f"no follow-up bullet matched '{args.match}'", file=sys.stderr)
        return 1

    today = args.date or dt.datetime.now(dt.timezone.utc).date().isoformat()

    new_outcome_bullets: list[str] = []
    for line in promoted:
        match = bullet_re.match(line)
        if not match:
            continue
        body = match.group(1).strip()
        # Strip leading status tokens we don't want (we'll re-prepend "shipped").
        body = re.sub(r"^(?:shipped|pending|active)\b\s*[:\-—]?\s*", "", body, flags=re.IGNORECASE)
        body = re.sub(r"^✅\s*|^⏳\s*", "", body)

        pr_suffix = ""
        if args.pr:
            if not re.search(r"#\d+", body):
                pr_suffix = f" (PR #{args.pr})"
            else:
                # leave existing PR reference in body
                pr_suffix = ""
        new_outcome_bullets.append(f"- shipped {today}: {body}{pr_suffix}\n")

    # Insert at the top of the Outcome section (after the header line).
    if not out_lines:
        new_out_block = f"{o_header}\n\n" + "".join(new_outcome_bullets) + "\n"
    else:
        # Header is the first line; preserve following blank line(s) if any.
        header_line = out_lines[0]
        rest = out_lines[1:]
        # Skip leading blank lines after header so promoted bullets sit
        # immediately under the header for chronological newest-first.
        leading_blanks: list[str] = []
        while rest and not rest[0].strip():
            leading_blanks.append(rest.pop(0))
        new_out_block = (
            header_line
            + "".join(leading_blanks if leading_blanks else ["\n"])
            + "".join(new_outcome_bullets)
            + "".join(rest)
        )

    new_text = (
        text[:o_start]
        + new_out_block
        + text[o_end:f_start]
        + "".join(new_fu_lines)
        + text[f_end:]
    )

    if args.dry_run:
        print(new_text)
        return 0

    path.write_text(new_text, encoding="utf-8")
    print(f"✓ promoted {len(promoted)} bullet(s) in {path}")
    if args.pr:
        print(f"  tagged with PR #{args.pr}")
    print("  next: run `python3 scripts/generate_tracker_index.py` to refresh Studio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
