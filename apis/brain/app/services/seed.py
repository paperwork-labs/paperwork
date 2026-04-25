"""Knowledge seed ingestion — reads docs/ files and stores them as episodes.
Splits large documents into chunks so the Brain can retrieve relevant sections.

medallion: ops
"""

import glob
import hashlib
import logging
import os
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.episode import Episode
from app.services.memory import store_episode

logger = logging.getLogger(__name__)

CHUNK_SIZE = 2000
CHUNK_OVERLAP = 200

DOCS_TO_INGEST = [
    "docs/KNOWLEDGE.md",
    "docs/TASKS.md",
    "docs/BRAIN_ARCHITECTURE.md",
    "docs/PRD.md",
    "docs/VENTURE_MASTER_PLAN.md",
    "docs/FINANCIALS.md",
    "docs/PARTNERSHIPS.md",
    "docs/AI_MODEL_REGISTRY.md",
    "docs/ARCHITECTURE.md",
    "docs/PRODUCT_SPEC.md",
]

# Source tag for episodes created from sprint "What we learned" sections.
# Studio's /admin/overview filters episodes by source prefix so these surface
# as "lessons learned" cards, distinct from "seed:docs" chunks.
SPRINT_LESSONS_SOURCE = "sprint:lessons"

# Sprint markdown lessons sections we recognize. The first match wins, so put
# the canonical heading first.
LESSONS_HEADERS = (
    "## What we learned",
    "## Lessons learned",
    "## Lessons",
)


def _chunk_by_headers(text: str, max_size: int = CHUNK_SIZE) -> list[dict[str, str]]:
    """Split markdown by ## headers, then by size if a section is too large."""
    sections = re.split(r"(?=^## )", text, flags=re.MULTILINE)
    chunks: list[dict[str, str]] = []

    for section in sections:
        section = section.strip()
        if not section:
            continue

        header_match = re.match(r"^##\s+(.+)", section)
        header = header_match.group(1).strip() if header_match else "Overview"

        if len(section) <= max_size:
            chunks.append({"header": header, "content": section})
        else:
            for i in range(0, len(section), max_size - CHUNK_OVERLAP):
                chunk_text = section[i : i + max_size]
                suffix = f" (part {i // (max_size - CHUNK_OVERLAP) + 1})" if i > 0 else ""
                chunks.append({"header": f"{header}{suffix}", "content": chunk_text})

    return chunks


async def ingest_docs(
    db: AsyncSession,
    repo_root: str,
    organization_id: str = "paperwork-labs",
    skip_embedding: bool = False,
) -> int:
    """Ingest all venture docs as seed episodes.

    Args:
        db: Database session
        repo_root: Root directory of the paperwork repo
        organization_id: Organization to seed docs into
        skip_embedding: Skip embedding generation (default False — embeddings enabled).

    Returns:
        Count of episodes created.
    """
    total = 0

    for doc_path in DOCS_TO_INGEST:
        full_path = os.path.join(repo_root, doc_path)
        if not os.path.exists(full_path):
            logger.warning("Skipping %s (not found)", doc_path)
            continue

        with open(full_path, encoding="utf-8") as f:
            content = f.read()

        filename = os.path.basename(doc_path)
        chunks = _chunk_by_headers(content)

        for chunk in chunks:
            await store_episode(
                db,
                organization_id=organization_id,
                source="seed:docs",
                summary=f"[{filename}] {chunk['header']}",
                full_context=chunk["content"],
                importance=0.8,
                metadata={"doc": doc_path, "section": chunk["header"]},
                skip_embedding=skip_embedding,
            )
            total += 1

        logger.info("Ingested %s: %d chunks", doc_path, len(chunks))

    logger.info(
        "Seed ingestion complete: %d total episodes (embeddings_skipped=%s)", total, skip_embedding
    )
    return total


# ---------------------------------------------------------------------------
# Sprint "What we learned" → memory episodes
# ---------------------------------------------------------------------------
#
# The user feedback that motivated this:
#
#   "I like lessons learnt part — this should be something the brain
#    should be learning too yeah"
#
# So we lift each bullet under `## What we learned` in every
# `docs/sprints/*.md` into its own episode. Each lesson becomes a small,
# self-contained memory the same retrieval (vector + FTS + recency) can
# surface for any question that relates to it — no need for the user to
# remember which sprint it lived in.


def _slug_from_path(path: str) -> str:
    base = os.path.basename(path)
    return base[:-3] if base.lower().endswith(".md") else base


def _extract_lessons(markdown: str) -> list[str]:
    """Pull bullet lines out of the first lessons-style section."""
    for header in LESSONS_HEADERS:
        if header in markdown:
            after = markdown.split(header, 1)[1]
            # Stop at the next H2 (start of next section).
            section = after.split("\n## ", 1)[0]
            bullets: list[str] = []
            for raw in section.splitlines():
                line = raw.strip()
                if line.startswith(("- ", "* ")):
                    bullets.append(line[2:].strip())
            return bullets
    return []


def _lesson_ref(slug: str, lesson_text: str) -> str:
    digest = hashlib.sha1(lesson_text.encode("utf-8")).hexdigest()[:10]
    return f"{slug}#{digest}"


async def ingest_sprint_lessons(
    db: AsyncSession,
    repo_root: str,
    organization_id: str = "paperwork-labs",
    skip_embedding: bool = False,
) -> dict[str, int]:
    """Ingest every sprint's `## What we learned` bullets as episodes.

    Idempotent: re-runs are no-ops because each lesson's episode is keyed by
    the SHA1 of its text under ``source_ref = "<sprint_slug>#<digest>"``.

    Args:
        db: Database session.
        repo_root: Root directory of the paperwork repo.
        organization_id: Organization to seed lessons into.
        skip_embedding: Skip embedding generation (default False).

    Returns:
        ``{"created": int, "skipped": int, "sprints_scanned": int}``.
    """
    sprints_dir = os.path.join(repo_root, "docs", "sprints")
    if not os.path.isdir(sprints_dir):
        logger.warning("ingest_sprint_lessons: %s does not exist", sprints_dir)
        return {"created": 0, "skipped": 0, "sprints_scanned": 0}

    md_files = sorted(glob.glob(os.path.join(sprints_dir, "*.md")))
    md_files = [
        p for p in md_files if os.path.basename(p).lower() != "readme.md"
    ]

    # Pull existing source_refs in one query so we can skip duplicates without
    # racing the unique index.
    existing_refs = {
        row[0]
        for row in (
            await db.execute(
                select(Episode.source_ref).where(
                    Episode.organization_id == organization_id,
                    Episode.source == SPRINT_LESSONS_SOURCE,
                )
            )
        ).all()
    }

    created = 0
    skipped = 0
    sprints_scanned = 0

    for md_path in md_files:
        with open(md_path, encoding="utf-8") as f:
            content = f.read()
        sprints_scanned += 1
        slug = _slug_from_path(md_path)
        lessons = _extract_lessons(content)
        if not lessons:
            continue

        for idx, lesson in enumerate(lessons):
            ref = _lesson_ref(slug, lesson)
            if ref in existing_refs:
                skipped += 1
                continue
            await store_episode(
                db,
                organization_id=organization_id,
                source=SPRINT_LESSONS_SOURCE,
                source_ref=ref,
                summary=lesson,
                full_context=lesson,
                importance=0.85,  # lessons are high-signal — bias retrieval
                metadata={
                    "sprint_slug": slug,
                    "sprint_path": os.path.relpath(md_path, repo_root),
                    "lesson_index": idx,
                },
                skip_embedding=skip_embedding,
            )
            created += 1

    logger.info(
        "ingest_sprint_lessons: scanned=%d created=%d skipped=%d "
        "(idempotent — skipped means already-stored)",
        sprints_scanned,
        created,
        skipped,
    )
    return {
        "created": created,
        "skipped": skipped,
        "sprints_scanned": sprints_scanned,
    }
