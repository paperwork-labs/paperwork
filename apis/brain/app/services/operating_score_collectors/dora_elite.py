"""DORA pillar — deploy frequency, lead time, CFR, MTTR via `gh api`.

Writes raw measurements to ``apis/brain/data/dora_metrics.json`` for transparency.

medallion: ops
"""

from __future__ import annotations

import json
import math
import os
import subprocess
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

if TYPE_CHECKING:
    from pathlib import Path

_BOOTSTRAP = (75.0, False, "gh CLI unavailable; bootstrap estimate")


def _brain_data_dir() -> Path:
    from app.utils.paths import brain_data_dir

    return brain_data_dir()


def _repo_slug() -> str | None:
    env = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if env:
        return env
    try:
        cp = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    url = cp.stdout.strip().removesuffix(".git")
    parsed = urlparse(url)
    if parsed.scheme in ("https", "http") and parsed.netloc == "github.com":
        tail = parsed.path.strip("/").split("/")
    elif url.startswith("git@github.com:"):
        tail = url.split("git@github.com:", 1)[1].strip("/").split("/")
    elif url.startswith("ssh://git@github.com/"):
        tail = url.split("ssh://git@github.com/", 1)[1].strip("/").split("/")
    else:
        return None
    if len(tail) >= 2:
        return f"{tail[0]}/{tail[1]}"
    return None


def _search_issues_total(q: str) -> int:
    # gh api wraps query into field param
    cp = subprocess.run(
        [
            "gh",
            "api",
            "-X",
            "GET",
            "search/issues",
            "-f",
            f"q={q}",
            "--jq",
            ".total_count",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    n = int(cp.stdout.strip() or "0")
    return max(0, n)


def _parse_github_dt(s: str) -> datetime | None:
    if not isinstance(s, str) or not s.strip():
        return None
    txt = s.strip()
    if txt.endswith("Z"):
        txt = txt[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(txt)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _score_deploy_frequency(count_7d: int) -> float:
    return min(100.0, (float(count_7d) / 20.0) * 100.0)


def _score_lead_time_hours(median_hours: float) -> float:
    if median_hours <= 8:
        return 100.0
    if median_hours <= 24:
        return 80.0
    if median_hours <= 72:
        return 50.0
    if median_hours <= 168:
        return 20.0
    return 0.0


def _score_cfr_pct(pct: float) -> float:
    if pct <= 15:
        return 100.0
    if pct <= 25:
        return 80.0
    if pct <= 40:
        return 50.0
    return 20.0


def _score_mttr_hours(median_hours: float) -> float:
    if median_hours <= 1:
        return 100.0
    if median_hours <= 4:
        return 80.0
    if median_hours <= 24:
        return 50.0
    return 0.0


def median_float(xs: list[float]) -> float | None:
    if not xs:
        return None
    ys = sorted(xs)
    n = len(ys)
    mid = n // 2
    if n % 2:
        return ys[mid]
    return (ys[mid - 1] + ys[mid]) / 2.0


def _fetch_merged_prs_page(
    slug: str, base_branch: str, page: int, per_page: int
) -> list[dict[str, Any]]:
    owner, _, repo = slug.partition("/")
    subpath = (
        f"repos/{owner}/{repo}/pulls?state=closed&base={base_branch}"
        f"&sort=updated&direction=desc&per_page={per_page}&page={page}"
    )
    cp = subprocess.run(
        ["gh", "api", subpath],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    raw = json.loads(cp.stdout)
    return raw if isinstance(raw, list) else []


def _lead_time_hours(pr: dict[str, Any]) -> float | None:
    merged_at = pr.get("merged_at")
    created_at = pr.get("created_at")
    if not merged_at or not created_at:
        return None
    tm = _parse_github_dt(str(merged_at))
    tc = _parse_github_dt(str(created_at))
    if tm is None or tc is None:
        return None
    delta = tm - tc
    return max(0.0, delta.total_seconds() / 3600.0)


def _lead_time_median_recent(
    slug: str, base_branch: str
) -> tuple[float | None, list[dict[str, Any]]]:
    """Median lead time (hours) over up to 30 most recently merged PRs."""
    merged_rows: list[dict[str, Any]] = []
    for page in range(1, 11):
        chunk = _fetch_merged_prs_page(slug, base_branch, page, 100)
        if not chunk:
            break
        for pr in chunk:
            if pr.get("merged_at"):
                merged_rows.append(pr)
        if len(chunk) < 100:
            break

    def merged_ts(pr: dict[str, Any]) -> datetime:
        m = _parse_github_dt(str(pr.get("merged_at") or ""))
        return m if m is not None else datetime.min.replace(tzinfo=UTC)

    merged_rows.sort(key=merged_ts, reverse=True)
    picked = merged_rows[:30]
    hours_list = [_lead_time_hours(p) for p in picked]
    finite = [h for h in hours_list if h is not None]
    return (median_float(finite), picked)


def _workflow_mttr_hours(slug: str, workflow_file: str, branch: str) -> float | None:
    owner, _, repo = slug.partition("/")
    path = (
        f"repos/{owner}/{repo}/actions/workflows/{workflow_file}/runs?branch={branch}&per_page=100"
    )
    runs_raw: list[dict[str, Any]] = []
    for page in range(1, 4):
        cp = subprocess.run(
            ["gh", "api", f"{path}&page={page}"],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        payload = json.loads(cp.stdout)
        wr = payload.get("workflow_runs") if isinstance(payload, dict) else None
        if not isinstance(wr, list) or len(wr) == 0:
            break
        runs_raw.extend(wr)
        if len(wr) < 100:
            break

    def created_key(r: dict[str, Any]) -> str:
        return str(r.get("created_at") or "")

    runs_sorted = sorted(runs_raw, key=created_key)
    intervals: list[float] = []
    in_red = False
    red_start: datetime | None = None

    for run in runs_sorted:
        conclusion = str(run.get("conclusion") or "")
        created_s = str(run.get("created_at") or "")
        created = _parse_github_dt(created_s)
        if created is None:
            continue
        if conclusion == "success":
            if in_red and red_start is not None:
                hrs = max(0.0, (created - red_start).total_seconds() / 3600.0)
                intervals.append(hrs)
            in_red = False
            red_start = None
        elif conclusion == "failure":
            if not in_red:
                in_red = True
                red_start = created

    return median_float(intervals)


def collect() -> tuple[float, bool, str]:
    slug = _repo_slug()
    base_branch = os.environ.get("BRAIN_DORA_DEFAULT_BRANCH", "main").strip() or "main"
    wf_mttr = (
        os.environ.get("BRAIN_DORA_MTTR_WORKFLOW", "lighthouse-ci.yml").strip()
        or "lighthouse-ci.yml"
    )

    if not slug:
        return _BOOTSTRAP

    try:
        now = datetime.now(tz=UTC)
        day_7 = (now - timedelta(days=7)).date().isoformat()
        day_30 = (now - timedelta(days=30)).date().isoformat()

        q7 = f"repo:{slug} is:pr is:merged base:{base_branch} merged:>={day_7}"
        deploy_count = _search_issues_total(q7)

        q_merge_30 = f"repo:{slug} is:pr is:merged base:{base_branch} merged:>={day_30}"
        merge_total = _search_issues_total(q_merge_30)
        revert_total = _search_issues_total(f"{q_merge_30} Revert in:title")
        cfr_pct = (float(revert_total) / float(merge_total) * 100.0) if merge_total else 0.0

        lead_med, lead_picked = _lead_time_median_recent(slug, base_branch)

        mttr_med = _workflow_mttr_hours(slug, wf_mttr, base_branch)

        s_deploy = _score_deploy_frequency(deploy_count)
        s_lead = 0.0 if lead_med is None else _score_lead_time_hours(lead_med)
        s_cfr = _score_cfr_pct(cfr_pct)
        s_mttr = 100.0 if mttr_med is None else _score_mttr_hours(mttr_med)

        pillars_avg = (s_deploy + s_lead + s_cfr + s_mttr) / 4.0
        total = max(0.0, min(100.0, math.floor(pillars_avg * 10000 + 0.5) / 10000))

        blob = {
            "schema": "dora_metrics/v1",
            "computed_at": now.isoformat().replace("+00:00", "Z"),
            "deploy_frequency_per_week": float(deploy_count),
            "lead_time_median_hours": float(lead_med or 0.0),
            "change_failure_rate_pct": round(float(cfr_pct), 4),
            "mttr_median_hours": float(mttr_med or 0.0),
            "sub_scores": {
                "deploy_frequency": round(s_deploy, 4),
                "lead_time": round(s_lead, 4),
                "change_failure_rate": round(s_cfr, 4),
                "mttr": round(s_mttr, 4),
            },
        }
        out_path = _brain_data_dir() / "dora_metrics.json"
        out_path.write_text(json.dumps(blob, indent=2) + "\n", encoding="utf-8")

        notes = (
            f"DORA from gh api ({slug}); deploy_7d={deploy_count} merges_30d={merge_total} "
            f"reverts={revert_total} lead_n={len(lead_picked)} wf={wf_mttr}"
        )
        return (total, True, notes)
    except (
        OSError,
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        json.JSONDecodeError,
        ValueError,
    ):
        return _BOOTSTRAP
