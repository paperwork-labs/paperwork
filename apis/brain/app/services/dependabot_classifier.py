"""Dependabot bump classifier — port of .github/workflows/dependabot-auto-approve.yaml.

Pure function over PR metadata. No I/O, no side effects. Classifies a Dependabot
PR into one of four decisions so the webhook handler can act deterministically:

    safe    — patch / minor (including grouped) → approve + mark auto-merge ready
    major   — major-version bump → route to Brain's pr_review LLM for risk triage
    unknown — title doesn't match any heuristic → human review
    ignore  — not a Dependabot PR at all

Intentionally mirrors the old workflow's decision surface byte-for-byte so the
behaviour is identical before and after the migration. Deviations are tracked as
FIXMEs and require a Brain episode to document.

medallion: ops
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Iterable

Decision = Literal["safe", "major", "unknown", "ignore"]


DEPENDABOT_LOGINS = frozenset({"dependabot[bot]", "dependabot-preview[bot]"})

# Title patterns: semver from/to bumps, requirement pin updates, major jumps (e.g. actions).
_SEMVER_FROM_TO_RE = re.compile(
    r"from\s+>?=?\s*(?P<from>\d+(?:\.\d+){0,2})\s+to\s+>?=?\s*(?P<to>\d+(?:\.\d+){0,2})",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Classification:
    decision: Decision
    reason: str
    from_version: str | None = None
    to_version: str | None = None
    bump_kind: Literal["patch", "minor", "major", "unknown", "n/a"] = "n/a"


def _compare_semver(a: str, b: str) -> Literal["patch", "minor", "major", "unknown"]:
    """Return the semver "distance" between two version strings."""

    def split(v: str) -> tuple[int, int, int]:
        parts = v.split(".")
        nums = [int(p) for p in parts if p.isdigit()]
        while len(nums) < 3:
            nums.append(0)
        return (nums[0], nums[1], nums[2])

    try:
        ma, mi, pa = split(a)
        mb, mi2, pb = split(b)
    except (ValueError, IndexError):
        return "unknown"

    if ma != mb:
        return "major"
    if mi != mi2:
        return "minor"
    if pa != pb:
        return "patch"
    return "unknown"


def classify_pr(
    *,
    author_login: str,
    title: str,
    labels: Iterable[str] = (),
    dependabot_update_type: str | None = None,
) -> Classification:
    """Classify a PR. `dependabot_update_type` is the header
    `X-GitHub-Dependency-Update-Type` when we have it (from fetch-metadata);
    otherwise we fall back to title heuristics so this works without it.
    """
    if author_login not in DEPENDABOT_LOGINS:
        return Classification(decision="ignore", reason=f"author={author_login!r}")

    label_set = {lbl.strip().lower() for lbl in labels if isinstance(lbl, str)}
    if "needs-human-review" in label_set:
        return Classification(decision="unknown", reason="label: needs-human-review")

    # Preferred path: Dependabot's own metadata gives us the authoritative type.
    # fetch-metadata surfaces this as "version-update:semver-{patch,minor,major}"
    # for grouped PRs too; we treat the group's outer label the same way the
    # old workflow did.
    norm = (dependabot_update_type or "").strip().lower()
    if norm.endswith(("semver-patch", "semver-minor")):
        return Classification(
            decision="safe",
            reason=f"dependabot metadata: {norm}",
            bump_kind="patch" if "patch" in norm else "minor",
        )
    if norm.endswith("semver-major"):
        return Classification(
            decision="major",
            reason=f"dependabot metadata: {norm}",
            bump_kind="major",
        )

    # Fallback: parse the PR title. Handles the 'requirement from >=X to >=Y'
    # case that fetch-metadata can't classify.
    m = _SEMVER_FROM_TO_RE.search(title)
    if not m:
        return Classification(decision="unknown", reason="no version pattern in title")

    fv = m.group("from")
    tv = m.group("to")
    distance = _compare_semver(fv, tv)
    if distance == "major":
        return Classification(
            decision="major",
            reason=f"title heuristic: {fv} → {tv}",
            from_version=fv,
            to_version=tv,
            bump_kind="major",
        )
    if distance in ("minor", "patch"):
        return Classification(
            decision="safe",
            reason=f"title heuristic: {fv} → {tv}",
            from_version=fv,
            to_version=tv,
            bump_kind=distance,
        )

    return Classification(
        decision="unknown",
        reason=f"indeterminate version delta: {fv} → {tv}",
        from_version=fv,
        to_version=tv,
    )
