"""Autonomy pillar — self-merge ratio, self-proposal ratio, founder ops minutes.

Sub-score weights:
  40%  self-merge ratio       (brain-authored PRs / total merged, from pr_outcomes.json)
  25%  self-proposal ratio    (brain dispatches / (brain dispatches + founder PRs))
  25%  founder ops minutes    (git log heuristic; 0 min→100, 30 min→80, 60 min→50, 120+→0)
  10%  app registry conformance (avg conformance score across registered apps)

Bootstrap: corpus <10 pr_outcomes OR <20 agent_dispatch_log entries → measured=False.

medallion: ops
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path

from app.services import app_registry

logger = logging.getLogger(__name__)

_MINS_PER_FOUNDER_COMMIT = 20
_BOT_EMAIL_PATTERNS = (
    "github-actions",
    "dependabot",
    "noreply",
    "brain@",
    "bot@",
    "renovate",
)


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _brain_data_dir() -> Path:
    from app.utils.paths import brain_data_dir

    return brain_data_dir()


def _pr_outcomes_path() -> Path:
    env = os.environ.get("BRAIN_PR_OUTCOMES_JSON", "").strip()
    if env:
        return Path(env)
    return _brain_data_dir() / "pr_outcomes.json"


def _dispatch_log_path() -> Path:
    env = os.environ.get("BRAIN_AGENT_DISPATCH_LOG_JSON", "").strip()
    if env:
        return Path(env)
    return _brain_data_dir() / "agent_dispatch_log.json"


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------


def _load_outcomes(path: Path) -> list[dict[str, object]]:
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and isinstance(raw.get("outcomes"), list):
            return [r for r in raw["outcomes"] if isinstance(r, dict)]
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("autonomy: pr_outcomes unreadable — %s", exc)
    return []


def _load_dispatches(path: Path) -> list[dict[str, object]]:
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and isinstance(raw.get("dispatches"), list):
            return [d for d in raw["dispatches"] if isinstance(d, dict)]
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("autonomy: agent_dispatch_log unreadable — %s", exc)
    return []


# ---------------------------------------------------------------------------
# Sub-score helpers
# ---------------------------------------------------------------------------


def _score_ratio(ratio: float) -> float:
    """Linear 0->100 for a 0.0-1.0 ratio (clamped)."""
    return max(0.0, min(100.0, ratio * 100.0))


def _estimate_founder_ops_minutes() -> float:
    """Count non-bot commits to ops paths in last 30 days x _MINS_PER_FOUNDER_COMMIT."""
    try:
        cp = subprocess.run(
            [
                "git",
                "log",
                "--since=30 days ago",
                "--format=%ae",
                "--",
                "apis/brain/",
                "infra/",
                "scripts/",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        emails = [e.strip().lower() for e in cp.stdout.splitlines() if e.strip()]
        founder_commits = sum(1 for e in emails if not any(pat in e for pat in _BOT_EMAIL_PATTERNS))
        return float(founder_commits * _MINS_PER_FOUNDER_COMMIT)
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("autonomy: git log unavailable — %s", exc)
        return 30.0


def _score_founder_ops_minutes(mins: float) -> float:
    """Heuristic: 0 min→100, 30 min→80 (L4 target), 60 min→50, 120+→0."""
    if mins <= 0:
        return 100.0
    if mins <= 30:
        return 100.0 - (mins / 30.0) * 20.0
    if mins <= 60:
        return 80.0 - ((mins - 30.0) / 30.0) * 30.0
    if mins <= 120:
        return 50.0 - ((mins - 60.0) / 60.0) * 50.0
    return 0.0


def _registry_component() -> tuple[float, float, bool, str]:
    """Return (legacy_bonus 0-10, conformance_score 0-100, measured, note)."""
    try:
        registry = app_registry.load_registry()
    except FileNotFoundError:
        return (0.0, 50.0, False, "app registry missing — no autonomy penalty")
    scores = [entry.conformance.score for entry in registry.apps]
    avg = sum(scores) / len(scores) if scores else 0.0
    bonus = 10.0 if avg > 0.8 else 0.0
    return (bonus, avg * 100.0, True, f"registry conformance avg={avg:.2f}")


# ---------------------------------------------------------------------------
# Public collector
# ---------------------------------------------------------------------------


def collect() -> tuple[float, bool, str]:
    outcomes = _load_outcomes(_pr_outcomes_path())
    dispatches = _load_dispatches(_dispatch_log_path())

    legacy_bonus, s_registry, registry_measured, registry_note = _registry_component()

    # Bootstrap guard — corpus too thin to compute meaningful ratios
    if len(outcomes) < 10 or len(dispatches) < 20:
        return (
            min(100.0, 20.0 + legacy_bonus),
            registry_measured,
            f"bootstrap estimate — corpus building; {registry_note}",
        )

    # Sub-score 1: self-merge ratio (40%)
    # A PR counts as brain-merged when merged_by_agent starts with "brain-"
    brain_merges = sum(
        1 for r in outcomes if str(r.get("merged_by_agent") or "").startswith("brain-")
    )
    self_merge_ratio = brain_merges / len(outcomes)
    s_merge = _score_ratio(self_merge_ratio)

    # Sub-score 2: self-proposal ratio (25%)
    # Treat each dispatch log entry as one brain-initiated proposal.
    # Founder proposals are estimated from pr_outcomes entries authored by "founder".
    founder_prs = sum(1 for r in outcomes if str(r.get("merged_by_agent") or "") == "founder")
    brain_dispatch_count = len(dispatches)
    total_proposals = brain_dispatch_count + founder_prs
    self_proposal_ratio = brain_dispatch_count / max(total_proposals, 1)
    s_proposal = _score_ratio(self_proposal_ratio)

    # Sub-score 3: founder ops minutes proxy (25%)
    founder_mins = _estimate_founder_ops_minutes()
    s_founder = _score_founder_ops_minutes(founder_mins)

    # Sub-score 4: app registry conformance (10%)
    # s_registry is 0-100 (avg conformance x 100)

    total = 0.40 * s_merge + 0.25 * s_proposal + 0.25 * s_founder + 0.10 * s_registry
    total = max(0.0, min(100.0, total))

    notes = (
        f"autonomy: self_merge={brain_merges}/{len(outcomes)} ({self_merge_ratio:.0%}) "
        f"s_merge={s_merge:.1f} "
        f"self_proposal={brain_dispatch_count}/{total_proposals} ({self_proposal_ratio:.0%}) "
        f"s_proposal={s_proposal:.1f} "
        f"founder_ops_mins_est={founder_mins:.0f} s_founder={s_founder:.1f} "
        f"{registry_note}"
    )
    return (total, True, notes)
