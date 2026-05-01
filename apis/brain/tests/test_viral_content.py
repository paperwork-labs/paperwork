"""Tests for viral content engine.

medallion: social
"""

from __future__ import annotations

from app.services.viral_content import (
    ContentIdea,
    ViralContentEngine,
    ViralGenre,
)


def _sample_genre() -> ViralGenre:
    return ViralGenre(
        genre_id="edu-thread",
        name="Educational Thread",
        description="Bite-sized educational content",
        platforms=["twitter", "linkedin"],
        tone_anchors=["informative", "punchy"],
    )


class TestViralContentEngine:
    """Unit tests for ViralContentEngine."""

    def test_generate_ideas_returns_requested_count(self) -> None:
        engine = ViralContentEngine()
        ideas = engine.generate_ideas(_sample_genre(), count=3)
        assert len(ideas) == 3

    def test_generate_ideas_assigns_genre(self) -> None:
        engine = ViralContentEngine()
        genre = _sample_genre()
        ideas = engine.generate_ideas(genre, count=1)
        assert ideas[0].genre is genre

    def test_rank_by_virality_sorts_descending(self) -> None:
        engine = ViralContentEngine()
        genre = _sample_genre()
        ideas = [
            ContentIdea(
                genre=genre,
                hook="low",
                format="short-form",
                estimated_engagement=1.0,
            ),
            ContentIdea(
                genre=genre,
                hook="high",
                format="short-form",
                estimated_engagement=9.0,
            ),
            ContentIdea(
                genre=genre,
                hook="mid",
                format="short-form",
                estimated_engagement=5.0,
            ),
        ]
        ranked = engine.rank_by_virality(ideas)
        scores = [i.estimated_engagement for i in ranked]
        assert scores == [9.0, 5.0, 1.0]

    def test_adapt_for_platform_changes_platform(self) -> None:
        engine = ViralContentEngine()
        genre = _sample_genre()
        idea = ContentIdea(
            genre=genre,
            hook="test hook",
            format="carousel",
            estimated_engagement=7.5,
        )
        adapted = engine.adapt_for_platform(idea, "tiktok")
        assert adapted.genre.platforms == ["tiktok"]
        assert adapted.hook == "test hook"
        assert adapted.estimated_engagement == 7.5

    def test_adapt_preserves_tone_anchors(self) -> None:
        engine = ViralContentEngine()
        genre = _sample_genre()
        idea = ContentIdea(
            genre=genre,
            hook="hook",
            format="video",
            estimated_engagement=3.0,
        )
        adapted = engine.adapt_for_platform(idea, "instagram")
        assert adapted.genre.tone_anchors == genre.tone_anchors
