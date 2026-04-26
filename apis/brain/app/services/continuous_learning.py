"""Continuous learning — merged PRs, decision docs, postmortems → memory episodes.

Idempotency: DB `source_ref` is canonical; JSON pin files under ``apis/brain/data/``
are updated atomically after successful stores for fast skips and operations.

medallion: ops
"""

from __future__ import annotations

import glob
import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.episode import Episode
from app.services.memory import store_episode

logger = logging.getLogger(__name__)

SOURCE_MERGED_PR = "merged_pr"
SOURCE_DECISION = "decision"
SOURCE_POSTMORTEM = "postmortem"

_GH_API = "https://api.github.com"
_PIN_TMP_SUFFIX = ".tmp"


def _brain_root() -> str:
    """Directory ``apis/brain`` (package root), containing ``/data``."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _data_dir() -> str:
    d = os.path.join(_brain_root(), "data")
    os.makedirs(d, exist_ok=True)
    return d


def _pin_path(name: str) -> str:
    return os.path.join(_data_dir(), name)


def _atomic_write_json(path: str, data: dict[str, Any]) -> None:
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    tmp = f"{path}{_PIN_TMP_SUFFIX}"
    raw = json.dumps(data, indent=2, sort_keys=True) + "\n"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(raw)
    os.replace(tmp, path)


def _load_json(path: str) -> dict[str, Any]:
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            out = json.load(f)
        return out if isinstance(out, dict) else {}
    except (OSError, json.JSONDecodeError):
        logger.warning("Could not read pin file %s — treating as empty", path)
        return {}


def _sha256_body(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _gh_headers() -> dict[str, str]:
    return {
        "Authorization": f"token {settings.GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }


def _repo_parts() -> tuple[str, str]:
    raw = settings.GITHUB_REPO.strip()
    parts = raw.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError("GITHUB_REPO must be 'owner/repo'")
    return parts[0], parts[1]


def _strip_pr_body_for_summary(body: str) -> str:
    """Remove HTML comments and strip markdown ``##`` boilerplate lines."""
    s = re.sub(r"<!--[\s\S]*?-->", "", body)
    lines_out: list[str] = []
    for line in s.splitlines():
        stripped = line.strip()
        if re.match(r"^#{1,6}\s+(\S+)", stripped) and re.match(
            r"^#+\s*(Summary|Related|Test plan|Checklist|Motivation|Context|Solution)\b",
            stripped,
            re.I,
        ):
            continue
        lines_out.append(line)
    text = "\n".join(lines_out).strip()
    if len(text) > 600:
        return text[:600] + "…"
    return text


def _top_level_dirs_from_paths(paths: list[str]) -> list[str]:
    out: set[str] = set()
    for p in paths:
        p = p.replace("\\", "/").strip()
        if not p:
            continue
        segs = [s for s in p.split("/") if s]
        if len(segs) >= 2:
            out.add(f"{segs[0]}/{segs[1]}")
        elif len(segs) == 1:
            out.add(segs[0])
    return sorted(out)


@dataclass
class MergedPRRecord:
    number: int
    title: str
    body: str
    merged_at: str
    labels: list[str]
    author: str
    base_ref: str
    file_paths: list[str]


def _parse_gh_merged_prs(
    pr: dict[str, Any],
    files: list[dict[str, Any]],
) -> MergedPRRecord:
    user = (pr.get("user") or {}) if isinstance(pr.get("user"), dict) else {}
    author = str(user.get("login") or "unknown")
    raw_labels = pr.get("labels") or []
    labels: list[str] = []
    if isinstance(raw_labels, list):
        for lb in raw_labels:
            if isinstance(lb, dict) and lb.get("name"):
                labels.append(str(lb["name"]))
    paths: list[str] = []
    for f in files:
        if isinstance(f, dict) and f.get("filename"):
            paths.append(str(f["filename"]))
    base = (pr.get("base") or {}) if isinstance(pr.get("base"), dict) else {}
    return MergedPRRecord(
        number=int(pr.get("number") or 0),
        title=str(pr.get("title") or ""),
        body=str(pr.get("body") or ""),
        merged_at=str(pr.get("merged_at") or ""),
        labels=labels,
        author=author,
        base_ref=str(base.get("ref") or ""),
        file_paths=paths,
    )


async def _http_fetch_merged_prs(
    days: int = 7,
    limit: int = 50,
) -> list[MergedPRRecord]:
    if not settings.GITHUB_TOKEN or not str(settings.GITHUB_TOKEN).strip():
        raise ValueError("GITHUB_TOKEN not configured")
    owner, repo = _repo_parts()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    q = f"repo:{owner}/{repo} is:pr is:merged merged:>={cutoff}"
    out: list[MergedPRRecord] = []
    async with httpx.AsyncClient(
        base_url=_GH_API,
        headers=_gh_headers(),
        timeout=httpx.Timeout(90.0),
    ) as client:
        r = await client.get(
            "/search/issues",
            params={"q": q, "per_page": min(100, max(limit, 1))},
        )
        r.raise_for_status()
        payload = r.json()
    items = payload.get("items") or []
    if not isinstance(items, list):
        return []
    cap = min(int(limit), 100)
    nums: list[int] = []
    for it in items[:cap]:
        if not isinstance(it, dict):
            continue
        n = it.get("number")
        if isinstance(n, int):
            nums.append(n)

    async with httpx.AsyncClient(
        base_url=_GH_API,
        headers=_gh_headers(),
        timeout=httpx.Timeout(90.0),
    ) as client:
        for pr_num in sorted(set(nums), reverse=True):
            pr_r = await client.get(f"/repos/{owner}/{repo}/pulls/{pr_num}")
            if pr_r.status_code == 404:
                continue
            pr_r.raise_for_status()
            pr: dict[str, Any] = pr_r.json()
            if not pr.get("merged_at"):
                continue
            m_at = str(pr.get("merged_at") or "")
            try:
                m_dt = datetime.fromisoformat(m_at.replace("Z", "+00:00"))
            except ValueError:
                m_dt = None
            if m_dt and m_dt < datetime.now(timezone.utc) - timedelta(days=days + 1):
                continue
            all_files: list[dict[str, Any]] = []
            page = 1
            while page <= 10:
                fr = await client.get(
                    f"/repos/{owner}/{repo}/pulls/{pr_num}/files",
                    params={"per_page": 100, "page": page},
                )
                fr.raise_for_status()
                batch = fr.json()
                if not isinstance(batch, list) or not batch:
                    break
                all_files.extend(batch)
                if len(batch) < 100:
                    break
                page += 1
            out.append(_parse_gh_merged_prs(pr, all_files))
    out.sort(key=lambda r: r.merged_at or "", reverse=True)
    return out[: min(cap, 50)]


async def ingest_merged_prs(
    db: AsyncSession,
    repo_root: str,
    organization_id: str = "paperwork-labs",
    *,
    dry_run: bool = False,
    limit: int | None = 50,
    days: int = 7,
    skip_embedding: bool = False,
) -> dict[str, int | str | bool | list[int]]:
    """Ingest recently merged PRs (GitHub API). Idempotent on ``source_ref=pr-N``."""
    _ = repo_root
    pin_path = _pin_path("ingested_prs.json")
    pin: dict[str, str] = {str(k): str(v) for k, v in _load_json(pin_path).items()}

    existing_refs: set[str | None] = {
        row[0]
        for row in (
            await db.execute(
                select(Episode.source_ref).where(
                    Episode.organization_id == organization_id,
                    Episode.source == SOURCE_MERGED_PR,
                )
            )
        ).all()
    }

    try:
        prs = await _http_fetch_merged_prs(days=days, limit=50)
    except (httpx.HTTPError, ValueError) as e:
        logger.exception("ingest_merged_prs: fetch failed: %s", e)
        return {
            "created": 0,
            "skipped": 0,
            "error": str(e)[:500],
            "dry_run": dry_run,
            "candidates": [],
        }

    max_new = int(limit) if limit is not None and limit > 0 else 50
    created = 0
    skipped = 0
    new_nums: list[int] = []

    for rec in prs:
        ref = f"pr-{rec.number}"
        if ref in existing_refs:
            skipped += 1
            if not dry_run and str(rec.number) not in pin:
                pin[str(rec.number)] = rec.merged_at
                _atomic_write_json(pin_path, pin)
            continue
        if created >= max_new:
            break

        summary = _strip_pr_body_for_summary(rec.body)
        top_dirs = _top_level_dirs_from_paths(rec.file_paths)
        full = (
            f"PR #{rec.number} — {rec.title}\n\n"
            f"Summary: {summary}\n\n"
            f"Labels: {', '.join(rec.labels) if rec.labels else '(none)'}\n"
            f"Top-level paths: {', '.join(top_dirs) if top_dirs else '(n/a)'}\n"
            f"Merged: {rec.merged_at}\n"
            f"Author: @{rec.author}\n"
            f"Base: {rec.base_ref or 'unknown'}"
        )
        if dry_run:
            created += 1
            new_nums.append(rec.number)
            continue

        await store_episode(
            db,
            organization_id=organization_id,
            source=SOURCE_MERGED_PR,
            source_ref=ref,
            summary=f"#{rec.number} {rec.title}"[:2000],
            full_context=full,
            importance=0.75,
            metadata={
                "source": "merged_pr",
                "pr": rec.number,
                "labels": rec.labels,
                "dirs": top_dirs,
                "author": rec.author,
                "merged_at": rec.merged_at,
            },
            skip_embedding=skip_embedding,
        )
        await db.commit()
        existing_refs.add(ref)
        pin[str(rec.number)] = rec.merged_at
        _atomic_write_json(pin_path, pin)
        created += 1
        new_nums.append(rec.number)

    msg = f"ingested {created} new PRs, skipped {skipped} existing"
    if dry_run:
        msg += " (dry_run)"
    print(msg)
    return {
        "created": created,
        "skipped": skipped,
        "dry_run": dry_run,
        "candidates": new_nums,
    }


# --- frontmatter & markdown ---

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*", re.DOTALL | re.MULTILINE)


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        fm = {}
    if not isinstance(fm, dict):
        fm = {}
    body = text[m.end() :]
    return fm, body


def _first_h1(body: str) -> str:
    for line in body.splitlines():
        if line.strip().startswith("# "):
            return line.strip()[2:].strip()
    return "Untitled"


def _first_paragraph(body: str) -> str:
    buf: list[str] = []
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            if buf:
                break
            continue
        buf.append(line)
    return " ".join(buf)[:2000] if buf else ""


def _iter_decision_files(repo_root: str) -> list[str]:
    out: set[str] = set()
    dec = os.path.join(repo_root, "docs", "decisions")
    if os.path.isdir(dec):
        for p in glob.glob(os.path.join(dec, "**", "*.md"), recursive=True):
            if os.path.isfile(p):
                out.add(p)
    for p in glob.glob(os.path.join(repo_root, "docs", "**", "DECISIONS.md"), recursive=True):
        if os.path.isfile(p):
            out.add(p)
    for p in glob.glob(os.path.join(repo_root, "docs", "**", "decisions", "**", "*.md"), recursive=True):
        if os.path.isfile(p) and "node_modules" not in p:
            out.add(p)
    # frontmatter search (docs only, shallow+deep bound)
    docs_root = os.path.join(repo_root, "docs")
    if os.path.isdir(docs_root):
        for root, _dirs, files in os.walk(docs_root):
            if "node_modules" in root or ".git" in root:
                continue
            for name in files:
                if not name.lower().endswith(".md"):
                    continue
                path = os.path.join(root, name)
                if path in out:
                    continue
                try:
                    head = open(path, encoding="utf-8", errors="replace").read(4000)
                except OSError:
                    continue
                if re.search(r"^doc_kind:\s*decision\s*$", head, re.MULTILINE | re.IGNORECASE):
                    out.add(path)
    return sorted(out)


def _file_mtime_iso(path: str) -> str:
    try:
        ts = os.path.getmtime(path)
    except OSError:
        return ""
    return datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()


async def ingest_decisions(
    db: AsyncSession,
    repo_root: str,
    organization_id: str = "paperwork-labs",
    *,
    dry_run: bool = False,
    limit: int | None = None,
    skip_embedding: bool = False,
) -> dict[str, int | str | list[str]]:
    pin_path = _pin_path("ingested_decisions.json")
    pin: dict[str, str] = {str(k): str(v) for k, v in _load_json(pin_path).items()}

    existing_ref_set: set[str | None] = {
        row[0]
        for row in (
            await db.execute(
                select(Episode.source_ref).where(
                    Episode.organization_id == organization_id,
                    Episode.source == SOURCE_DECISION,
                )
            )
        ).all()
    }

    paths = _iter_decision_files(repo_root)
    created = 0
    skipped = 0
    max_new = int(limit) if limit and limit > 0 else 10_000

    for path in paths:
        relp = os.path.relpath(path, repo_root) if path.startswith(repo_root) else path
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                raw = f.read()
        except OSError:
            continue
        fm, body = _split_frontmatter(raw)
        h = _sha256_body(body)
        ref = f"decision:{h}"
        if ref in existing_ref_set:
            skipped += 1
            if h not in pin and not dry_run:
                pin[h] = relp
                _atomic_write_json(pin_path, pin)
            continue
        if created >= max_new:
            break

        title = _first_h1(body)
        decision_t = str(fm.get("decision") or "").strip()
        context_t = str(fm.get("context") or "").strip()
        cons = str(fm.get("consequences") or "").strip()
        if decision_t or context_t or cons:
            detail = "\n\n".join(
                x
                for x in (
                    f"Decision: {decision_t}" if decision_t else "",
                    f"Context: {context_t}" if context_t else "",
                    f"Consequences: {cons}" if cons else "",
                )
                if x
            )
        else:
            detail = _first_paragraph(body)

        last_reviewed = str(fm.get("last_reviewed") or fm.get("last_reviewd") or "").strip()
        mtime = _file_mtime_iso(path)
        date_note = last_reviewed or mtime

        full = f"{title}\n\n{detail}\n\nPath: {relp}\nLast review / mtime: {date_note}"
        if dry_run:
            created += 1
            continue

        await store_episode(
            db,
            organization_id=organization_id,
            source=SOURCE_DECISION,
            source_ref=ref,
            summary=title[:2000],
            full_context=full,
            importance=0.8,
            metadata={
                "source": "decision",
                "path": relp,
                "body_hash": h,
            },
            skip_embedding=skip_embedding,
        )
        await db.commit()
        existing_ref_set.add(ref)
        pin[h] = relp
        _atomic_write_json(pin_path, pin)
        created += 1

    if dry_run:
        print(
            f"ingested {created} new decisions, skipped {skipped} existing" + (" (dry_run)" if dry_run else "")
        )
    else:
        print(f"ingested {created} new decisions, skipped {skipped} existing")
    return {"created": created, "skipped": skipped, "dry_run": dry_run, "scanned": len(paths)}


def _extract_sprint_postmortems(
    path: str,
    raw: str,
) -> list[tuple[str, str]]:
    """Return (key_suffix, text) for abandoned sprint postmortem sections."""
    fm, body = _split_frontmatter(raw)
    status = str(fm.get("status") or "").lower().strip()
    if status != "abandoned":
        return []
    found: list[tuple[str, str]] = []
    for heading in (
        "## Postmortem",
        "## Post-mortem",
        "## What went wrong",
    ):
        if heading in body:
            after = body.split(heading, 1)[1]
            section = re.split(r"\n##\s", after, maxsplit=1)[0]
            key = f"{os.path.basename(path)}:{heading}"
            found.append((key, f"{heading}\n{section}".strip()[:20_000]))
    return found


def _iter_runbook_incidents(repo_root: str) -> list[tuple[str, str, str]]:
    """(relpath, key, text) for runbook ``## Incident`` blocks with a date line."""
    rb = os.path.join(repo_root, "docs", "runbooks")
    if not os.path.isdir(rb):
        return []
    out: list[tuple[str, str, str]] = []
    for p in glob.glob(os.path.join(rb, "*.md")):
        if not os.path.isfile(p):
            continue
        try:
            raw = open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        if "## Incident" not in raw and "## incident" not in raw.lower():
            continue
        # Case-normalize split
        low = raw.lower()
        pos = low.find("## incident")
        if pos < 0:
            continue
        after = raw[pos:]
        section = re.split(r"\n##\s", after, maxsplit=1)
        if len(section) < 1:
            continue
        block0 = section[0]
        # need a date: YYYY-MM-DD or "Month D, YYYY"
        if not re.search(r"20\d{2}[-/]\d{2}[-/]\d{2}|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? 20\d{2}", block0, re.I):
            continue
        relp = os.path.relpath(p, repo_root)
        key = f"runbook:{relp}:{_sha256_body(block0)[:12]}"
        out.append((relp, key, block0.strip()[:20_000]))
    return out


async def ingest_postmortems(
    db: AsyncSession,
    repo_root: str,
    organization_id: str = "paperwork-labs",
    *,
    dry_run: bool = False,
    limit: int | None = None,
    skip_embedding: bool = False,
) -> dict[str, int | str]:
    pin_path = _pin_path("ingested_postmortems.json")
    pin: dict[str, str] = {str(k): str(v) for k, v in _load_json(pin_path).items()}

    existing_ref_set: set[str | None] = {
        row[0]
        for row in (
            await db.execute(
                select(Episode.source_ref).where(
                    Episode.organization_id == organization_id,
                    Episode.source == SOURCE_POSTMORTEM,
                )
            )
        ).all()
    }

    # Collect (ref, title, full_text, h) where ref is stable from full body hash
    items: list[tuple[str, str, str, str]] = []
    sprints_dir = os.path.join(repo_root, "docs", "sprints")
    if os.path.isdir(sprints_dir):
        for p in glob.glob(os.path.join(sprints_dir, "*.md")):
            if os.path.basename(p).lower() == "readme.md":
                continue
            try:
                raw = open(p, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            for _key, text in _extract_sprint_postmortems(p, raw):
                h = _sha256_body(text)
                ref = f"pm:{h}"
                title = f"Abandoned sprint postmortem: {os.path.basename(p)}"
                items.append((ref, title, text, h))

    for relp, _rkey, text in _iter_runbook_incidents(repo_root):
        h = _sha256_body(text)
        ref = f"pm:rb:{h}"
        title = f"Runbook incident: {relp}"
        items.append((ref, title, text, h))

    created = 0
    skipped = 0
    max_new = int(limit) if limit and limit > 0 else 10_000

    for ref, title, text, h in items:
        if ref in existing_ref_set:
            skipped += 1
            if h not in pin and not dry_run:
                pin[h] = ref
                _atomic_write_json(pin_path, pin)
            continue
        if created >= max_new:
            break
        if dry_run:
            created += 1
            continue
        full = f"{title}\n\n{text}"
        await store_episode(
            db,
            organization_id=organization_id,
            source=SOURCE_POSTMORTEM,
            source_ref=ref,
            summary=title[:2000],
            full_context=full,
            importance=0.82,
            metadata={"source": "postmortem", "body_hash": h},
            skip_embedding=skip_embedding,
        )
        await db.commit()
        existing_ref_set.add(ref)
        pin[h] = ref
        _atomic_write_json(pin_path, pin)
        created += 1

    if dry_run:
        print(
            f"ingested {created} new postmortems, skipped {skipped} existing"
            + (" (dry_run)" if dry_run else "")
        )
    else:
        print(f"ingested {created} new postmortems, skipped {skipped} existing")
    return {"created": created, "skipped": skipped, "dry_run": dry_run, "scanned": len(items)}
