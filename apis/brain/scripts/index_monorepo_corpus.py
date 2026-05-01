#!/usr/bin/env python
"""Index key monorepo files into Brain's episodic memory for RAG.

Indexes: .cursor/rules/*.mdc, docs/**/*.md, AGENTS.md, docs/sprints/*.md.

Usage:
    cd apis/brain
    python -m scripts.index_monorepo_corpus

Or with explicit repo root:
    REPO_ROOT=/path/to/paperwork python -m scripts.index_monorepo_corpus

Idempotent: existing episodes keyed by source_ref are skipped.

medallion: ops
"""

from __future__ import annotations

import asyncio
import glob
import hashlib
import logging
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import select

from app.database import async_session_factory
from app.models.episode import Episode
from app.services.memory import store_episode

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

_DEFAULT_REPO_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)

SOURCE_TAG = "corpus:monorepo"
ORG_ID = "paperwork-labs"
CHUNK_SIZE = 2000
CHUNK_OVERLAP = 200
BATCH_SIZE = 5


def _repo_root() -> str:
    return os.environ.get("REPO_ROOT", _DEFAULT_REPO_ROOT)


def _rel(repo_root: str, full_path: str) -> str:
    rel = os.path.relpath(full_path, repo_root)
    return rel.replace(os.sep, "/")


def _source_ref(rel_path: str, chunk_index: int) -> str:
    digest = hashlib.sha1(f"{rel_path}:{chunk_index}".encode()).hexdigest()[:10]
    return f"corpus:{rel_path}#{digest}"


def _collect_paths(repo_root: str) -> list[str]:
    """Return sorted list of absolute paths to index."""
    patterns = [
        ".cursor/rules/*.mdc",
        "docs/**/*.md",
        "AGENTS.md",
        "apis/axiomfolio/AGENTS.md",
    ]
    seen: set[str] = set()
    paths: list[str] = []

    for pattern in patterns:
        full_pattern = os.path.join(repo_root, pattern)
        for match in sorted(glob.glob(full_pattern, recursive=True)):
            norm = os.path.normpath(match)
            if norm not in seen and os.path.isfile(norm):
                seen.add(norm)
                paths.append(norm)

    return paths


def _chunk_text(text: str, rel_path: str) -> list[dict[str, str | int]]:
    """Split by markdown H2 headers; fall back to fixed-size chunks."""
    sections = re.split(r"(?=^## )", text, flags=re.MULTILINE)
    chunks: list[dict[str, str | int]] = []
    idx = 0

    for section in sections:
        section = section.strip()
        if not section:
            continue

        header_match = re.match(r"^##\s+(.+)", section)
        header = header_match.group(1).strip() if header_match else os.path.basename(rel_path)

        if len(section) <= CHUNK_SIZE:
            chunks.append({"header": header, "content": section, "index": idx})
            idx += 1
        else:
            for i in range(0, len(section), CHUNK_SIZE - CHUNK_OVERLAP):
                part = section[i : i + CHUNK_SIZE]
                suffix = f" (part {i // (CHUNK_SIZE - CHUNK_OVERLAP) + 1})" if i > 0 else ""
                chunks.append({"header": f"{header}{suffix}", "content": part, "index": idx})
                idx += 1

    return chunks


async def _get_existing_refs(db, org_id: str) -> set[str]:
    result = await db.execute(
        select(Episode.source_ref).where(
            Episode.organization_id == org_id,
            Episode.source == SOURCE_TAG,
            Episode.source_ref.is_not(None),
        )
    )
    return {row[0] for row in result.all()}


async def run(
    repo_root: str,
    org_id: str = ORG_ID,
    skip_embedding: bool = False,
) -> dict[str, int]:
    """Index monorepo corpus into Brain episodic memory.

    Returns {"created": int, "skipped": int, "files_scanned": int}.
    """
    paths = _collect_paths(repo_root)
    logger.info("Found %d files to index from %s", len(paths), repo_root)

    async with async_session_factory() as db:
        existing_refs = await _get_existing_refs(db, org_id)
        logger.info("Existing corpus refs: %d", len(existing_refs))

        created = 0
        skipped = 0
        batch: list[dict] = []

        for full_path in paths:
            rel_path = _rel(repo_root, full_path)
            try:
                text = Path(full_path).read_text(encoding="utf-8")
            except OSError as exc:
                logger.warning("Skipping %s: %s", rel_path, exc)
                continue

            chunks = _chunk_text(text, rel_path)

            for chunk in chunks:
                ref = _source_ref(rel_path, int(chunk["index"]))
                if ref in existing_refs:
                    skipped += 1
                    continue

                batch.append(
                    {
                        "ref": ref,
                        "rel_path": rel_path,
                        "header": chunk["header"],
                        "content": chunk["content"],
                    }
                )

            # Flush batch
            while len(batch) >= BATCH_SIZE:
                flush = batch[:BATCH_SIZE]
                batch = batch[BATCH_SIZE:]
                for item in flush:
                    await store_episode(
                        db,
                        organization_id=org_id,
                        source=SOURCE_TAG,
                        summary=f"[{item['rel_path']}] {item['header']}",
                        full_context=item["content"],
                        source_ref=item["ref"],
                        importance=0.7,
                        metadata={
                            "corpus_path": item["rel_path"],
                            "section": item["header"],
                        },
                        skip_embedding=skip_embedding,
                    )
                    created += 1
                await db.commit()
                logger.info(
                    "Committed batch of %d episodes (total created=%d)",
                    BATCH_SIZE,
                    created,
                )

        # Flush remainder
        for item in batch:
            await store_episode(
                db,
                organization_id=org_id,
                source=SOURCE_TAG,
                summary=f"[{item['rel_path']}] {item['header']}",
                full_context=item["content"],
                source_ref=item["ref"],
                importance=0.7,
                metadata={
                    "corpus_path": item["rel_path"],
                    "section": item["header"],
                },
                skip_embedding=skip_embedding,
            )
            created += 1
        if batch:
            await db.commit()

    result = {"created": created, "skipped": skipped, "files_scanned": len(paths)}
    logger.info(
        "Corpus indexing complete: created=%d skipped=%d files_scanned=%d",
        created,
        skipped,
        len(paths),
    )
    return result


def main() -> None:
    repo_root = _repo_root()
    skip_embedding = os.environ.get("SKIP_EMBEDDING", "").lower() in ("1", "true", "yes")
    logger.info("Indexing monorepo corpus from %s (skip_embedding=%s)", repo_root, skip_embedding)
    result = asyncio.run(run(repo_root, skip_embedding=skip_embedding))
    logger.info("Done: %s", result)


if __name__ == "__main__":
    main()
