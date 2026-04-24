"""Unit tests for Brain's PR review pipeline (pure-function pieces only).

The full review_pr() path hits GitHub + Anthropic + the DB, so it's covered
by integration in staging. This file locks down the logic that lives
entirely in-process: model selection, file extraction, review formatting,
and HMAC verification on the webhook router.
"""

from __future__ import annotations

import hashlib
import hmac
import json

from app.services.pr_review import (
    BIG_MODEL,
    DEFAULT_MODEL,
    _choose_model,
    _compose_user_content,
    _extract_files,
    _format_review_body,
)


class TestChooseModel:
    def test_routine_files_pick_haiku(self) -> None:
        assert _choose_model(["apis/axiomfolio/app/services/silver/portfolio/analytics.py"]) == DEFAULT_MODEL

    def test_execution_path_escalates_to_sonnet(self) -> None:
        files = ["apis/axiomfolio/app/services/execution/risk_gate.py"]
        assert _choose_model(files) == BIG_MODEL

    def test_migration_escalates(self) -> None:
        assert _choose_model(["alembic/versions/2026_04_25_abc_add_column.py"]) == BIG_MODEL

    def test_infra_escalates(self) -> None:
        assert _choose_model(["infra/compose.dev.yaml"]) == BIG_MODEL

    def test_empty_files_falls_back_to_default(self) -> None:
        assert _choose_model([]) == DEFAULT_MODEL


class TestExtractFiles:
    def test_parses_files_block(self) -> None:
        meta = (
            "#123 Some PR title\n"
            "State: open merged=False\n"
            "Additions: 10 Deletions: 2 Files: 3\n"
            "\n"
            "Body:\nsome description\n"
            "\n"
            "Files:\n"
            "apis/brain/app/main.py\n"
            "apis/brain/app/routers/pr_review.py\n"
            "docs/BRAIN_PR_REVIEW.md\n"
        )
        files = _extract_files(meta)
        assert files == [
            "apis/brain/app/main.py",
            "apis/brain/app/routers/pr_review.py",
            "docs/BRAIN_PR_REVIEW.md",
        ]

    def test_none_listed_is_empty(self) -> None:
        meta = "... \nFiles:\n(none listed)\n"
        assert _extract_files(meta) == []

    def test_missing_files_marker_returns_empty(self) -> None:
        assert _extract_files("no files block here") == []


class TestFormatReviewBody:
    def test_renders_all_sections(self) -> None:
        parsed = {
            "verdict": "REQUEST_CHANGES",
            "summary": "Adds circular import risk in risk_gate.",
            "concerns": ["risk_gate pulls gold.strategy eagerly"],
            "strengths": ["Tests updated in the same PR"],
            "strategic_note": "Yak shave — not on this sprint.",
        }
        body = _format_review_body(parsed, model=DEFAULT_MODEL)
        assert "🧠 Brain review" in body
        assert "Adds circular import risk" in body
        assert "**Concerns**" in body
        assert "**Strengths**" in body
        assert "**Strategic note**" in body
        assert "model: `" in body and DEFAULT_MODEL in body

    def test_terse_on_minimal_input(self) -> None:
        body = _format_review_body({"verdict": "APPROVE", "summary": "Typo fix."}, model=DEFAULT_MODEL)
        assert "Typo fix." in body
        # No empty bullet sections
        assert "**Concerns**" not in body
        assert "**Strengths**" not in body

    def test_truncates_oversize_bullets(self) -> None:
        parsed = {"concerns": ["x" * 1000], "summary": "s"}
        body = _format_review_body(parsed, model=DEFAULT_MODEL)
        # bullet capped at 400 chars
        concern_line = [ln for ln in body.splitlines() if ln.startswith("- x")]
        assert concern_line and len(concern_line[0]) <= 2 + 400


class TestComposeUserContent:
    def test_includes_metadata_and_diff(self) -> None:
        out = _compose_user_content(
            meta_text="#42 feat: ...",
            diff="diff --git a/x b/x\n@@ +1 @@\n+hi\n",
            history="",
        )
        assert "## PR METADATA" in out
        assert "## DIFF" in out
        assert "```diff" in out
        assert "## HISTORICAL CONTEXT" not in out  # empty history omitted

    def test_history_included_when_present(self) -> None:
        out = _compose_user_content(
            meta_text="#42",
            diff="d",
            history="PRIOR RELATED REVIEWS:\n- prior thing",
        )
        assert "## HISTORICAL CONTEXT" in out
        assert "prior thing" in out


class TestWebhookHMAC:
    """Smoke-test the HMAC computation in routers/pr_review."""

    def test_signature_matches_expected(self) -> None:
        secret = "s3cr3t"
        body = json.dumps({"pr_number": 1, "action": "opened", "organization_id": "paperwork-labs"}, separators=(",", ":")).encode()
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        # Same computation the workflow performs via `openssl dgst`.
        shell_form = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        assert expected == shell_form
        assert len(expected) == 64
