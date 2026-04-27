"""Unit tests for the Dependabot bump classifier.

The classifier is the replacement for the title/label heuristics in the old
dependabot-auto-approve.yaml. Behaviour must match byte-for-byte: anything
misclassified here will auto-merge a risky bump or block a trivial one.
"""

from __future__ import annotations

from app.services.dependabot_classifier import classify_pr


class TestAuthorGate:
    def test_non_dependabot_is_ignored(self) -> None:
        c = classify_pr(author_login="paras", title="bump lodash from 1.0.0 to 2.0.0")
        assert c.decision == "ignore"

    def test_renovate_is_ignored(self) -> None:
        c = classify_pr(
            author_login="renovate[bot]",
            title="chore(deps): bump zod from 3.25 to 4.0",
        )
        assert c.decision == "ignore"


class TestDependabotMetadata:
    def test_semver_patch_is_safe(self) -> None:
        c = classify_pr(
            author_login="dependabot[bot]",
            title="chore(deps): bump lodash from 4.17.20 to 4.17.21",
            dependabot_update_type="version-update:semver-patch",
        )
        assert c.decision == "safe"
        assert c.bump_kind == "patch"

    def test_semver_minor_is_safe(self) -> None:
        c = classify_pr(
            author_login="dependabot[bot]",
            title="chore(deps): bump typescript from 5.9.3 to 5.10.0",
            dependabot_update_type="version-update:semver-minor",
        )
        assert c.decision == "safe"
        assert c.bump_kind == "minor"

    def test_semver_major_is_major(self) -> None:
        c = classify_pr(
            author_login="dependabot[bot]",
            title="chore(deps): bump zod from 3.25 to 4.0",
            dependabot_update_type="version-update:semver-major",
        )
        assert c.decision == "major"


class TestTitleHeuristics:
    def test_patch_bump_title(self) -> None:
        c = classify_pr(
            author_login="dependabot[bot]",
            title="chore(deps): bump lodash from 4.17.20 to 4.17.21",
        )
        assert c.decision == "safe"
        assert c.bump_kind == "patch"

    def test_minor_bump_title(self) -> None:
        c = classify_pr(
            author_login="dependabot[bot]",
            title="chore(deps): bump redis from 5.2.0 to 5.3.0",
        )
        assert c.decision == "safe"
        assert c.bump_kind == "minor"

    def test_major_bump_title(self) -> None:
        c = classify_pr(
            author_login="dependabot[bot]",
            title="chore(deps): bump zod from 3.25.0 to 4.3.0",
        )
        assert c.decision == "major"
        assert c.from_version == "3.25.0"
        assert c.to_version == "4.3.0"

    def test_requirement_style_title(self) -> None:
        # This is the shape fetch-metadata can't classify — our heuristic must.
        c = classify_pr(
            author_login="dependabot[bot]",
            title=(
                "chore(deps): update google-cloud-storage requirement from "
                ">=2.18.0 to >=3.10.1 in /apis/filefree"
            ),
        )
        assert c.decision == "major"
        assert c.from_version == "2.18.0"
        assert c.to_version == "3.10.1"

    def test_actions_major_bump(self) -> None:
        c = classify_pr(
            author_login="dependabot[bot]",
            title="chore(deps): bump actions/github-script from 7 to 9",
        )
        assert c.decision == "major"
        assert c.from_version == "7"
        assert c.to_version == "9"

    def test_unrecognized_title_returns_unknown(self) -> None:
        c = classify_pr(
            author_login="dependabot[bot]",
            title="chore(deps): update group of things",
        )
        assert c.decision == "unknown"


class TestLabelOverrides:
    def test_needs_human_review_short_circuits(self) -> None:
        c = classify_pr(
            author_login="dependabot[bot]",
            title="chore(deps): bump x from 1.0.0 to 1.0.1",
            labels=["needs-human-review"],
        )
        assert c.decision == "unknown"
