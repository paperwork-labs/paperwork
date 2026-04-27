#!/usr/bin/env python3
"""Group open Dependabot PRs by ecosystem, merge into a weekly rollup branch, open one PR per group.

Excludes security-tagged PRs. Skips a source PR on merge conflict (leaves a comment) without failing the run.
If fewer than 2 PRs are successfully merged in a group, the rollup branch is discarded (individual PRs stay open).

medallion: ops
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SECURITY_LABELS = frozenset(
    s.lower() for s in os.environ.get("ROLLUP_EXCLUDE_LABELS", "security,dependencies:security").split(",") if s.strip()
)
SKIP_LABELS = frozenset(
    s.lower() for s in os.environ.get("ROLLUP_DEFER_TO_IMMEDIATE", "security").split(",") if s.strip()
)

_IN_PATH = re.compile(r"in (\/[^\s)]+|\/)(?:\s|$)", re.IGNORECASE)


def _run(
    *args: str, check: bool = True, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    e = {**os.environ, **(env or {})}
    return subprocess.run(
        list(args), cwd=REPO_ROOT, text=True, capture_output=True, check=check, env=e
    )


def _gh_json(*gh_args: str) -> list[dict] | dict:
    p = _run("gh", *gh_args, check=False)
    if p.returncode != 0:
        print("gh error:", p.stderr, file=sys.stderr)
        return []
    if not p.stdout.strip():
        return []
    return json.loads(p.stdout)


def infer_eco(title: str, labels: list[dict]) -> str | None:
    names = {str((x or {}).get("name") or "").lower() for x in (labels or []) if isinstance(x, dict)}
    t = (title or "").lower()
    for n in names:
        if n in ("github_actions", "github-actions", "github actions"):
            return "github-actions"
    if re.search(r"\bactions/c[\w-]+", t) or "github_actions" in t or "/.github" in t:
        return "github-actions"
    m = _IN_PATH.search(title or "")
    path = (m.group(1) if m else "/").rstrip(")")
    if path.startswith("/apps/"):
        return "npm"
    if path.startswith("/apis/") or re.match(r"^/apis$", path):
        return "pip"
    if "docker" in t or "dockerfile" in t:
        return "docker"
    if path in ("/",) or "pnpm" in t or "package" in t:
        if "workflows" in t or "actions" in t:
            return "github-actions"
        return "npm"
    if "requirements" in t or "pip" in t:
        return "pip"
    if ("ci" in names and "workspace-root" in names) or "workflows" in t:
        return "github-actions"
    if "frontend" in names or "studio" in names:
        return "npm"
    if "backend" in names:
        return "pip"
    return "npm"


def is_security_pr(labels: list[dict], title: str) -> bool:
    names = {str((x or {}).get("name") or "").lower() for x in (labels or []) if isinstance(x, dict)}
    if names & (SKIP_LABELS | SECURITY_LABELS):
        return True
    if "security" in (title or "").lower():
        return True
    return False


def group_prs(prs: list[dict]) -> dict[str, list[dict]]:
    g: dict[str, list[dict]] = defaultdict(list)
    for pr in prs:
        author = str((pr.get("author") or pr.get("user") or {}).get("login") or "")
        if author not in ("dependabot[bot]", "dependabot-preview[bot]"):
            continue
        if is_security_pr(list(pr.get("labels") or []), str(pr.get("title") or "")):
            print(f"skip (security) #{pr.get('number')}", file=sys.stderr)
            continue
        eco = infer_eco(str(pr.get("title") or ""), list(pr.get("labels") or []))
        if not eco:
            continue
        g[eco].append(pr)
    return g


def merge_one_rollup(
    eco: str,
    group: list[dict],
    date_ymd: str,
) -> tuple[int | None, list[int], list[str]]:
    """Returns (rollup_pr_number, closed_individuals, failed_numbers_with_reason)."""
    if len(group) < 2:
        return (None, [], [])

    branch = f"chore/deps-rollup-{eco}-{date_ymd.replace('-', '')}"
    _run("git", "fetch", "origin", "main", check=True)
    _run("git", "branch", "-D", branch, check=False)  # noqa: S603
    _ = _run("git", "checkout", "-B", branch, "origin/main", check=True)
    failed: list[str] = []
    merged_in: list[int] = []
    for pr in sorted(group, key=lambda p: int(p.get("number") or 0)):
        num = int(pr.get("number") or 0)
        if not num:
            continue
        head = str(pr.get("headRefName") or "").strip()
        if not head:
            failed.append(f"{num} no head")
            continue
        _run("git", "fetch", "origin", head, check=True)
        m = _run(
            "git",
            "merge",
            "--no-ff",
            f"origin/{head}",
            "-m",
            f"chore(deps): rollup merge #{num} into {branch}",
            check=False,
        )
        if m.returncode != 0:
            _ = _run("git", "merge", "--abort", check=False)
            note = f"Rolled up into another branch failed at merge of #{num} (conflict). This PR was skipped; resolve locally or wait for a smaller rollup. Raw: {m.stderr[:300]!r}"
            _ = _run(
                "gh",
                "pr",
                "comment",
                str(num),
                "--body",
                note,
            )
            failed.append(f"{num} conflict")
            print(f"merge conflict {num} — skipped", file=sys.stderr)
            continue
        merged_in.append(num)
        print(f"merged #{num} into rollup branch", file=sys.stderr)

    if len(merged_in) < 2:
        _ = _run("git", "checkout", "main", check=False)
        _ = _run("git", "branch", "-D", branch, check=False)
        print(f"eco {eco}: <2 successful merges, abandoning", file=sys.stderr)
        return (None, [], failed)

    if eco == "npm":
        _run("corepack", "enable", check=False)
        p = _run("pnpm", "install", "--no-frozen-lockfile", check=False)
        if p.returncode != 0:
            print("pnpm install failed; continuing", p.stderr, file=sys.stderr)
    if eco == "pip":
        for req in REPO_ROOT.glob("apis/*/requirements.txt"):
            p = _run(sys.executable, "-m", "pip", "install", "-q", "-r", str(req), check=False)
            if p.returncode != 0:
                print("pip", req, p.stderr, file=sys.stderr)
    if eco == "github-actions" or eco == "docker":
        pass

    _run("git", "add", "-A", check=False)
    st = _run("git", "status", "-s", check=True)
    if st.stdout.strip():
        _run("git", "commit", "-m", f"chore(deps): post-rollup install refresh ({eco})", check=False)
    pr_title = f"chore(deps): weekly {eco} rollup ({date_ymd})"
    push = _run("git", "push", "-u", "origin", branch, check=False)
    if push.returncode != 0:
        print("git push failed", push.stderr, file=sys.stderr)
        _ = _run("git", "checkout", "main", check=False)
        _ = _run("git", "branch", "-D", branch, check=False)
        return (None, [], failed + ["git push failed"])

    p = _run(
        "gh",
        "pr",
        "create",
        "--base",
        "main",
        "--head",
        branch,
        "--title",
        pr_title,
        "--body",
        f"Weekly rollup of Dependabot PRs for **{eco}**.\n\n"
        f"Closes: {', '.join(f'#{n}' for n in merged_in)}",
        check=False,
    )
    if p.returncode != 0:
        print("gh pr create failed", p.stderr, file=sys.stderr)
        _ = _run("git", "checkout", "main", check=False)
        return (None, [], failed + ["rollup create failed"])

    out = (p.stdout or "").strip() + (p.stderr or "")
    m = re.search(r"(?:github\.com\/[^/]+\/[^/]+\/pull\/|pulls\/#)(\d+)", out) or re.search(
        r"pull\/(\d+)", out
    )
    rollup_no = int(m.group(1)) if m else None
    for n in merged_in:
        if rollup_no is not None:
            _ = _run(
                "gh",
                "pr",
                "close",
                str(n),
                "--comment",
                f"Rolled up into #{rollup_no}.",
            )
    return (rollup_no, merged_in, failed)


def main() -> int:
    now = datetime.now(timezone.utc)
    ymd = now.strftime("%Y-%m-%d")
    prs = _gh_json(
        "pr",
        "list",
        "--state",
        "open",
        "--limit",
        "200",
        "--json",
        "number,title,headRefName,labels,author",
    )
    if not isinstance(prs, list) or not prs:
        print("no open PRs", file=sys.stderr)
        return 0
    prs = [x for x in prs if isinstance(x, dict) and (x.get("author") or {}).get("login") in (
        "dependabot[bot]",
        "dependabot-preview[bot]",
    )]
    if not prs:
        print("no open dependabot PRs", file=sys.stderr)
        return 0
    g = group_prs(prs)
    for eco, pr_list in g.items():
        r, closed, _fail = merge_one_rollup(eco, pr_list, ymd)
        print(json.dumps({"ecosystem": eco, "rollup": r, "closed": closed, "date": ymd}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
