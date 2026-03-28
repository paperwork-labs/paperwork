#!/usr/bin/env python
"""Seed Brain with venture docs.

Usage:
    cd apis/brain
    python -m scripts.seed_knowledge

Or with explicit repo root:
    REPO_ROOT=/path/to/paperwork python -m scripts.seed_knowledge
"""

import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database import async_session_factory
from app.services.seed import ingest_docs

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    repo_root = os.environ.get(
        "REPO_ROOT",
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    )
    logger.info("Seeding Brain with docs from %s", repo_root)

    async with async_session_factory() as db:
        count = await ingest_docs(db, repo_root)
        await db.commit()
        logger.info("Seeded %d episodes", count)


if __name__ == "__main__":
    asyncio.run(main())
