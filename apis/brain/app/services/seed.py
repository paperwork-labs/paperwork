"""Knowledge seed ingestion — reads docs/ files and stores them as episodes.
Splits large documents into chunks so the Brain can retrieve relevant sections."""

import logging
import os
import re

from sqlalchemy.ext.asyncio import AsyncSession

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


async def ingest_docs(db: AsyncSession, repo_root: str, organization_id: str = "paperwork-labs") -> int:
    """Ingest all venture docs as seed episodes. Returns count of episodes created."""
    total = 0

    for doc_path in DOCS_TO_INGEST:
        full_path = os.path.join(repo_root, doc_path)
        if not os.path.exists(full_path):
            logger.warning("Skipping %s (not found)", doc_path)
            continue

        with open(full_path) as f:
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
            )
            total += 1

        logger.info("Ingested %s: %d chunks", doc_path, len(chunks))

    logger.info("Seed ingestion complete: %d total episodes", total)
    return total
