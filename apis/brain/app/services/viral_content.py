"""Viral content engine for social platforms.

medallion: social
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Platform = Literal[
    "twitter",
    "linkedin",
    "instagram",
    "tiktok",
    "youtube",
]


@dataclass
class ViralGenre:
    """A genre archetype for viral content."""

    genre_id: str
    name: str
    description: str
    platforms: list[Platform] = field(default_factory=list)
    tone_anchors: list[str] = field(default_factory=list)


@dataclass
class ContentIdea:
    """A single content idea scored for virality."""

    genre: ViralGenre
    hook: str
    format: str
    estimated_engagement: float = 0.0


class ViralContentEngine:
    """Generate, rank, and adapt viral content ideas.

    medallion: social
    """

    def __init__(self) -> None:
        self._genres: list[ViralGenre] = []
        self._ideas: list[ContentIdea] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_ideas(
        self,
        genre: ViralGenre,
        count: int = 5,
    ) -> list[ContentIdea]:
        """Generate content ideas for a given genre.

        Parameters
        ----------
        genre:
            The viral genre to generate ideas for.
        count:
            Number of ideas to produce.

        Returns
        -------
        list[ContentIdea]
            Generated content ideas (unranked).
        """
        ideas: list[ContentIdea] = []
        for _ in range(count):
            idea = ContentIdea(
                genre=genre,
                hook="",
                format="short-form",
                estimated_engagement=0.0,
            )
            ideas.append(idea)
        self._ideas.extend(ideas)
        return ideas

    def rank_by_virality(
        self,
        ideas: list[ContentIdea],
    ) -> list[ContentIdea]:
        """Rank ideas by estimated virality score.

        Parameters
        ----------
        ideas:
            Content ideas to rank.

        Returns
        -------
        list[ContentIdea]
            Ideas sorted descending by engagement.
        """
        return sorted(
            ideas,
            key=lambda i: i.estimated_engagement,
            reverse=True,
        )

    def adapt_for_platform(
        self,
        idea: ContentIdea,
        platform: Platform,
    ) -> ContentIdea:
        """Adapt a content idea for a specific platform.

        Parameters
        ----------
        idea:
            The base content idea.
        platform:
            Target platform to adapt for.

        Returns
        -------
        ContentIdea
            A new idea tailored to the platform.
        """
        adapted_genre = ViralGenre(
            genre_id=idea.genre.genre_id,
            name=idea.genre.name,
            description=idea.genre.description,
            platforms=[platform],
            tone_anchors=idea.genre.tone_anchors,
        )
        return ContentIdea(
            genre=adapted_genre,
            hook=idea.hook,
            format=idea.format,
            estimated_engagement=idea.estimated_engagement,
        )
