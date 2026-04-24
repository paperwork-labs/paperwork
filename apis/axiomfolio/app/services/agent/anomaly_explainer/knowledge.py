"""
Runbook knowledge index used to ground LLM explanations.

The repo's ``docs/MARKET_DATA_RUNBOOK.md`` (and friends) contains the
canonical operator playbook. The explainer feeds the most relevant
sections into the prompt so the LLM can cite real procedures instead of
inventing them.

This v1 implementation is intentionally *simple*:

* Chunks are H2-bounded sections from the markdown file.
* Retrieval is a keyword-overlap scorer, not embeddings. That keeps the
  module dependency-free (no ``sentence-transformers`` install on every
  worker), and is plenty good for a corpus of < 50 chunks.
* The :class:`RunbookKnowledge` class wraps the chunk list so we can
  swap in an embeddings backend later without touching the explainer.

If/when we want better recall we can add a ``EmbeddingRunbookKnowledge``
that implements the same surface and let ``AnomalyExplainer`` accept
either via duck typing.

medallion: ops
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9_]+")
_STOPWORDS = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
        "has", "have", "in", "is", "it", "its", "of", "on", "or", "that",
        "the", "this", "to", "was", "were", "will", "with", "you", "your",
        "we", "our", "if", "when", "than", "then", "but", "not", "no",
        "do", "does", "did", "so",
    }
)


def _tokenize(text: str) -> List[str]:
    return [tok for tok in _TOKEN_RE.findall(text.lower()) if tok not in _STOPWORDS]


@dataclass(frozen=True)
class RunbookChunk:
    """One H2-bounded section of a runbook markdown file."""

    source_path: str
    heading: str
    anchor: str  # GitHub-flavor lower-case-dash anchor
    body: str
    keywords: frozenset = field(default_factory=frozenset)

    def reference(self) -> str:
        """Stable citation string the LLM and humans can click."""
        return f"{Path(self.source_path).name}#{self.anchor}"


def _slugify_anchor(heading: str) -> str:
    """Mimic GitHub's anchor generation closely enough for cross-linking.

    GitHub's algorithm strips punctuation but does NOT collapse runs of
    whitespace before converting to dashes -- "ASCII / Unicode #1" yields
    ``ascii--unicode-1`` (double dash where the slash sat), not the
    collapsed single-dash form. We preserve that behavior so cross-doc
    anchor links keep working without manual normalization.
    """
    slug = heading.lower().strip()
    # Drop everything that isn't a word char, whitespace, or dash. We do
    # NOT collapse the whitespace afterwards.
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\t\n\r\f\v]", " ", slug).replace(" ", "-")
    slug = slug.strip("-")
    return slug or "section"


def load_runbook_chunks(path: Path | str) -> List[RunbookChunk]:
    """Parse a markdown file into H2-bounded :class:`RunbookChunk` objects.

    Anything before the first H2 (introduction, top-level H1) is captured
    in a synthetic ``"Overview"`` chunk so it's still searchable. Empty
    sections are dropped.
    """
    p = Path(path)
    if not p.exists():
        logger.warning("runbook not found at %s; returning empty knowledge base", p)
        return []
    raw = p.read_text(encoding="utf-8")

    sections: List[tuple] = []  # (heading, body_lines)
    current_heading = "Overview"
    current_body: List[str] = []

    for line in raw.splitlines():
        if line.startswith("## "):
            if current_body or sections:
                sections.append((current_heading, "\n".join(current_body).strip()))
            current_heading = line[3:].strip()
            current_body = []
        else:
            current_body.append(line)
    if current_body:
        sections.append((current_heading, "\n".join(current_body).strip()))

    chunks: List[RunbookChunk] = []
    for heading, body in sections:
        if not body:
            continue
        keywords = frozenset(_tokenize(f"{heading}\n{body}"))
        chunks.append(
            RunbookChunk(
                source_path=str(p),
                heading=heading,
                anchor=_slugify_anchor(heading),
                body=body,
                keywords=keywords,
            )
        )
    return chunks


class RunbookKnowledge:
    """Keyword-scored retrieval over a fixed list of runbook chunks.

    The scorer counts overlapping non-stopword tokens between the query
    (built from the anomaly's category, title, facts, and raw evidence)
    and each chunk's keyword set. Ties are broken by chunk order so
    output is deterministic for tests.
    """

    def __init__(self, chunks: Sequence[RunbookChunk]) -> None:
        self._chunks: List[RunbookChunk] = list(chunks)

    def __len__(self) -> int:
        return len(self._chunks)

    def find_relevant(self, query_text: str, top_k: int = 3) -> List[RunbookChunk]:
        if not self._chunks or top_k <= 0:
            return []
        query_tokens = set(_tokenize(query_text))
        if not query_tokens:
            return []

        scored: List[tuple] = []
        for idx, chunk in enumerate(self._chunks):
            overlap = len(query_tokens & chunk.keywords)
            if overlap > 0:
                scored.append((-overlap, idx, chunk))  # neg for descending sort
        scored.sort()
        return [chunk for _, _, chunk in scored[:top_k]]

    @classmethod
    def from_paths(cls, paths: Iterable[Path | str]) -> "RunbookKnowledge":
        """Convenience: load multiple files and concatenate their chunks."""
        all_chunks: List[RunbookChunk] = []
        for p in paths:
            all_chunks.extend(load_runbook_chunks(p))
        return cls(all_chunks)


# Sentinel: used by the explainer when no knowledge is wired up.
EMPTY_KNOWLEDGE = RunbookKnowledge([])


_DEFAULT_RUNBOOK_FILES = (
    "MARKET_DATA_RUNBOOK.md",
    "MARKET_DATA.md",
)


def default_knowledge(docs_dir: Path | str) -> RunbookKnowledge:
    """Load the canonical operator runbooks shipped with the repo."""
    base = Path(docs_dir)
    paths = [base / name for name in _DEFAULT_RUNBOOK_FILES]
    return RunbookKnowledge.from_paths([p for p in paths if p.exists()])


def query_text_for_anomaly(
    *,
    category: str,
    title: str,
    facts: Optional[Dict] = None,
    raw_evidence: str = "",
) -> str:
    """Compose a single string the keyword scorer can chew on."""
    parts = [category.replace("_", " "), title]
    if facts:
        for key, value in facts.items():
            parts.append(str(key))
            parts.append(str(value))
    if raw_evidence:
        parts.append(raw_evidence[:500])
    return " ".join(parts)
