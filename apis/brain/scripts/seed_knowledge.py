#!/usr/bin/env python
"""Seed Brain with venture docs and static knowledge (personas, rules, architecture).

Usage:
    cd apis/brain
    python -m scripts.seed_knowledge

Or with explicit repo root:
    REPO_ROOT=/path/to/paperwork python -m scripts.seed_knowledge
"""

from __future__ import annotations

import asyncio
import glob
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.episode import Episode
from app.services.memory import store_episode
from app.services.seed import ingest_docs

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# Script: apis/brain/scripts/seed_knowledge.py → repo root is four parents up.
_DEFAULT_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

EXPLICIT_KNOWLEDGE_FILES = [
    ".cursorrules",
    "AGENTS.md",
    "docs/AXIOMFOLIO_INTEGRATION.md",
    "docs/BRAIN_ARCHITECTURE.md",
]

BATCH_COMMIT_SIZE = 5


def _normalize_rel_path(repo_root: str, full_path: str) -> str:
    """Return POSIX-style path relative to repo root for source_ref."""
    rel = os.path.relpath(full_path, repo_root)
    return rel.replace(os.sep, "/")


def _collect_knowledge_paths(repo_root: str) -> list[str]:
    """Ordered list of repo-relative paths: all .cursor/rules/*.mdc then explicit files."""
    rules_glob = os.path.join(repo_root, ".cursor", "rules", "*.mdc")
    mdc_paths = sorted(glob.glob(rules_glob))

    seen: set[str] = set()
    ordered: list[str] = []

    for abs_path in mdc_paths:
        rel = _normalize_rel_path(repo_root, abs_path)
        if rel not in seen:
            seen.add(rel)
            ordered.append(rel)

    for rel in EXPLICIT_KNOWLEDGE_FILES:
        if rel not in seen:
            seen.add(rel)
            ordered.append(rel)

    return ordered


def _persona_for_source_ref(source_ref: str) -> str:
    """Map file path to persona slug (matches user examples for .mdc and .cursorrules)."""
    name = Path(source_ref).name
    if name.endswith(".mdc"):
        return Path(name).stem
    if name == ".cursorrules":
        return "engineering"
    if name == "AGENTS.md":
        return "engineering"
    if name == "BRAIN_ARCHITECTURE.md":
        return "agent-ops"
    if "AXIOMFOLIO" in name.upper():
        return "engineering"
    return "engineering"


def _summary_prefix(text: str, max_chars: int = 200) -> str:
    """First up to max_chars of content, trimmed at a word boundary."""
    stripped = text.strip()
    if not stripped:
        return ""
    if len(stripped) <= max_chars:
        return stripped
    chunk = stripped[:max_chars]
    last_space = chunk.rfind(" ")
    if last_space > max_chars // 2:
        return chunk[:last_space].rstrip()
    return chunk.rstrip()


def _truncate_context(text: str, max_len: int = 10000) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len]


async def _already_seeded(
    db: AsyncSession,
    *,
    organization_id: str,
    source_ref: str,
) -> bool:
    result = await db.execute(
        select(Episode.id)
        .where(
            Episode.organization_id == organization_id,
            Episode.source == "seed:knowledge",
            Episode.source_ref == source_ref,
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def seed_static_knowledge(
    db: AsyncSession,
    repo_root: str,
    *,
    organization_id: str = "paperwork-labs",
    skip_embedding: bool = True,
) -> int:
    """Ingest persona rules and key repo files as seed:knowledge episodes (one per file).

    Skips files already present with matching source_ref. Commits every BATCH_COMMIT_SIZE paths.
    """
    created = 0
    batch_count = 0
    rel_paths = _collect_knowledge_paths(repo_root)

    for source_ref in rel_paths:
        full_path = os.path.join(repo_root, *source_ref.split("/"))
        if not os.path.isfile(full_path):
            logger.warning("Skipping missing file %s", source_ref)
            batch_count += 1
            if batch_count >= BATCH_COMMIT_SIZE:
                await db.commit()
                batch_count = 0
            continue

        if await _already_seeded(db, organization_id=organization_id, source_ref=source_ref):
            logger.info("Already seeded, skip %s", source_ref)
            batch_count += 1
            if batch_count >= BATCH_COMMIT_SIZE:
                await db.commit()
                batch_count = 0
            continue

        with open(full_path, encoding="utf-8") as f:
            raw = f.read()

        summary = _summary_prefix(raw)
        if not summary:
            summary = f"[{Path(source_ref).name}] (empty)"

        await store_episode(
            db,
            organization_id=organization_id,
            source="seed:knowledge",
            summary=summary,
            full_context=_truncate_context(raw),
            persona=_persona_for_source_ref(source_ref),
            source_ref=source_ref,
            model_used="seed",
            importance=0.8,
            skip_embedding=skip_embedding,
        )
        created += 1
        logger.info("Seeded knowledge episode for %s", source_ref)

        batch_count += 1
        if batch_count >= BATCH_COMMIT_SIZE:
            await db.commit()
            batch_count = 0

    if batch_count:
        await db.commit()

    logger.info("Static knowledge seed complete: %d new episodes", created)
    return created


async def main() -> None:
    repo_root = os.environ.get("REPO_ROOT", _DEFAULT_REPO_ROOT)
    logger.info("Seeding Brain from repo root %s", repo_root)

    async with async_session_factory() as db:
        n_static = await seed_static_knowledge(db, repo_root)
        n_docs = await ingest_docs(db, repo_root)
        await db.commit()
        logger.info("Done: %d static knowledge episodes, %d doc chunks", n_static, n_docs)


if __name__ == "__main__":
    asyncio.run(main())
