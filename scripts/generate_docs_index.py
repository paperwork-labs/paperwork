#!/usr/bin/env python3
"""Auto-maintain `docs/_index.yaml` from on-disk frontmatter.

The studio docs hub used to rely on a hand-curated `docs/_index.yaml`.
That file held titles, summaries, owners, and category for every doc;
adding or renaming a markdown file required a second commit to keep the
index in sync. After the docs streamline + trackers sprint we have
enough frontmatter on every doc that the index can be derived from
disk: this script does the derivation and treats the existing
`docs/_index.yaml` as an *override registry* (keep your handcrafted
titles, summaries, tags, owners, slug pins; let the generator handle
discovery, archival, and removal).

Three modes:

    python3 scripts/generate_docs_index.py --check    # CI: fail on drift
    python3 scripts/generate_docs_index.py --write    # rewrite _index.yaml
    python3 scripts/generate_docs_index.py --diff     # human-readable diff

Behaviour:

  * Walks `docs/**/*.md` minus `EXCLUDED_SUBDIRS` and `EXCLUDED_FILES`
    (shared with `check_docs_index.py` so the two scripts agree).
  * For each doc that already has an entry by `path`, keeps the human
    overrides (title, summary, tags, owners, slug, category).
  * For each new doc, derives:
        slug      — kebab from filename
        title     — first H1 in the file (falls back to filename)
        summary   — `summary:` frontmatter, else first prose paragraph
                    after H1, trimmed to ~140 chars
        tags      — `tags:` frontmatter (list), else [domain, doc_kind]
        owners    — `owner:` frontmatter (single → list), else [strategy]
        category  — frontmatter `category:`, else mapped from `doc_kind`
                    via DOC_KIND_TO_CATEGORY, else `reference`.
  * Drops entries whose `path` no longer exists.
  * Emits sorted-by-(category order, then title) so the file diff is
    deterministic.

The `categories:` block at the top of `docs/_index.yaml` is treated as
hand-maintained metadata and copied through unchanged.
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from collections import OrderedDict
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX = REPO_ROOT / "docs" / "_index.yaml"
DOCS_DIR = REPO_ROOT / "docs"

# Keep these in lock-step with check_docs_index.py.
EXCLUDED_SUBDIRS = {
    "archive",
    "templates",
    "handoffs",
    "axiomfolio",
}
EXCLUDED_FILES = {
    "docs/SLACK_SPRINT_TEMPLATE.md",
    "docs/PHASE2-COMPOSER-HANDOFFS.md",
    "docs/NEXTJS_MIGRATION_2026Q3.md",
    "docs/AXIOMFOLIO_INTEGRATION.generated.md",
    "docs/sprints/README.md",
}

DOC_KIND_TO_CATEGORY = {
    "philosophy": "philosophy",
    "spec": "philosophy",
    "architecture": "architecture",
    "design": "architecture",
    "runbook": "runbooks",
    "checklist": "runbooks",
    "plan": "plans",
    "reference": "reference",
    "rotation": "reference",
    "generated": "generated",
}

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
H1_RE = re.compile(r"^# (.+)$", re.MULTILINE)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body_after_frontmatter).

    Tolerates files without frontmatter (returns empty dict, full body).
    """
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    try:
        data = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        data = {}
    return data, text[match.end() :]


def first_h1(body: str, fallback: str) -> str:
    match = H1_RE.search(body)
    if match:
        title = match.group(1).strip()
        # Drop trailing markdown link suffixes like " — see X" if very long.
        return title
    return fallback


def first_prose_paragraph(body: str) -> str:
    """Return the first non-empty, non-heading, non-blockquote paragraph."""
    after_h1 = body.split("\n", 1)
    body_after = after_h1[1] if len(after_h1) > 1 else body
    paragraph: list[str] = []
    for line in body_after.splitlines():
        stripped = line.strip()
        if not stripped:
            if paragraph:
                break
            continue
        if stripped.startswith(("#", ">", "|", "```", "- ", "* ", "1.")):
            if paragraph:
                break
            continue
        paragraph.append(stripped)
    text = " ".join(paragraph).strip()
    if len(text) > 200:
        text = text[:197].rsplit(" ", 1)[0] + "…"
    return text


def slugify(stem: str) -> str:
    s = stem.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s or "doc"


def derive_category(frontmatter: dict, rel_path: str) -> str:
    explicit = frontmatter.get("category")
    if isinstance(explicit, str) and explicit:
        return explicit
    if rel_path.startswith("docs/sprints/"):
        return "sprints"
    if rel_path.startswith("docs/generated/"):
        return "generated"
    if rel_path.startswith("docs/philosophy/"):
        return "philosophy"
    kind = (frontmatter.get("doc_kind") or "").strip().lower()
    return DOC_KIND_TO_CATEGORY.get(kind, "reference")


def derive_owners(frontmatter: dict, default: str) -> list[str]:
    owner = frontmatter.get("owner")
    owners = frontmatter.get("owners")
    if isinstance(owners, list) and owners:
        return [str(o) for o in owners]
    if isinstance(owner, str) and owner:
        return [owner]
    return [default]


def derive_tags(frontmatter: dict, fallback: list[str]) -> list[str]:
    tags = frontmatter.get("tags")
    if isinstance(tags, list) and tags:
        return [str(t) for t in tags]
    return [t for t in fallback if t]


def discover_docs(allowed_extras: set[str] | None = None) -> list[Path]:
    """Walk docs/ for *.md, filtering excluded subdirs/files.

    `allowed_extras` is the set of paths that should be admitted even if
    they would normally be filtered (e.g. the existing _index.yaml may
    surface a handful of axiomfolio/ entries explicitly even though the
    bulk subtree is excluded).
    """
    extras = allowed_extras or set()
    found: list[Path] = []
    for p in DOCS_DIR.rglob("*.md"):
        if any(part.startswith(".") for part in p.relative_to(REPO_ROOT).parts):
            continue
        rel = p.relative_to(REPO_ROOT).as_posix()
        if rel in extras:
            found.append(p)
            continue
        if any(rel.startswith(f"docs/{excl}/") for excl in EXCLUDED_SUBDIRS):
            continue
        if rel in EXCLUDED_FILES:
            continue
        found.append(p)
    return sorted(found)


def load_existing_overrides() -> dict[str, dict]:
    """Existing _index.yaml entries keyed by path — these are overrides."""
    if not INDEX.is_file():
        return {}
    data = yaml.safe_load(INDEX.read_text(encoding="utf-8")) or {}
    return {entry["path"]: entry for entry in data.get("docs") or [] if entry.get("path")}


def load_categories_block() -> dict:
    if not INDEX.is_file():
        return {}
    data = yaml.safe_load(INDEX.read_text(encoding="utf-8")) or {}
    return data.get("categories") or {}


def build_entry(path: Path, override: dict | None) -> dict:
    rel = path.relative_to(REPO_ROOT).as_posix()
    text = path.read_text(encoding="utf-8")
    frontmatter, body = parse_frontmatter(text)

    title_default = first_h1(body, path.stem.replace("_", " "))
    summary_default = (
        frontmatter.get("summary") or first_prose_paragraph(body) or title_default
    )
    category = derive_category(frontmatter, rel)
    owner_default = "infra-ops" if category == "runbooks" else "strategy"
    owners_default = derive_owners(frontmatter, owner_default)
    tags_default = derive_tags(
        frontmatter,
        [
            (frontmatter.get("domain") or "").strip().lower() or None,
            (frontmatter.get("doc_kind") or "").strip().lower() or None,
        ],
    )

    entry = OrderedDict()
    entry["slug"] = slugify(path.stem) if not override else override.get(
        "slug", slugify(path.stem)
    )
    entry["path"] = rel
    entry["title"] = (override or {}).get("title") or title_default
    entry["summary"] = (override or {}).get("summary") or summary_default
    entry["tags"] = (override or {}).get("tags") or tags_default
    entry["owners"] = (override or {}).get("owners") or owners_default
    entry["category"] = (override or {}).get("category") or category
    return entry


def render_yaml(categories: dict, docs: list[dict]) -> str:
    """Stable YAML output that preserves the file's existing shape."""
    out: list[str] = []
    out.append("# Studio docs hub taxonomy.")
    out.append("#")
    out.append("# Auto-maintained by scripts/generate_docs_index.py.")
    out.append("#")
    out.append("# - Discovery, removal, and ordering happen automatically.")
    out.append("# - To override the auto-derived title / summary / tags /")
    out.append("#   owners / slug / category for a doc, edit this file —")
    out.append("#   the generator preserves overrides keyed by `path`.")
    out.append("# - To exclude a doc, add it to EXCLUDED_FILES /")
    out.append("#   EXCLUDED_SUBDIRS in the generator (and check_docs_index).")
    out.append("# - The `categories:` block below is hand-maintained.")
    out.append("")

    out.append("categories:")
    for slug, cfg in sorted(
        categories.items(), key=lambda kv: kv[1].get("order", 999)
    ):
        out.append(f"  {slug}:")
        for key, value in cfg.items():
            if isinstance(value, str):
                out.append(f"    {key}: {yaml_scalar(value)}")
            else:
                out.append(f"    {key}: {value}")
    out.append("")

    out.append("docs:")
    grouped: dict[str, list[dict]] = {}
    for entry in docs:
        grouped.setdefault(entry["category"], []).append(entry)
    category_order = [
        slug
        for slug, _ in sorted(
            categories.items(), key=lambda kv: kv[1].get("order", 999)
        )
    ]
    label_for = {slug: cfg.get("label", slug) for slug, cfg in categories.items()}

    for cat in category_order:
        items = grouped.get(cat) or []
        if not items:
            continue
        out.append(f"  # ── {label_for.get(cat, cat.title())} ─" + "─" * 40)
        for item in sorted(items, key=lambda i: (i["title"].lower(), i["path"])):
            out.append(f"  - slug: {item['slug']}")
            out.append(f"    path: {item['path']}")
            out.append(f"    title: {yaml_scalar(item['title'])}")
            out.append(f"    summary: {yaml_scalar(item['summary'])}")
            out.append(f"    tags: [{', '.join(item['tags'])}]")
            out.append(f"    owners: [{', '.join(item['owners'])}]")
            out.append(f"    category: {item['category']}")

    # Categories not represented in `categories:` (shouldn't happen unless
    # we add a new doc_kind without updating the block).
    extra = [c for c in grouped if c not in category_order]
    for cat in extra:
        out.append(f"  # ── {cat.title()} (uncategorised) ─" + "─" * 30)
        for item in sorted(grouped[cat], key=lambda i: (i["title"].lower(), i["path"])):
            out.append(f"  - slug: {item['slug']}")
            out.append(f"    path: {item['path']}")
            out.append(f"    title: {yaml_scalar(item['title'])}")
            out.append(f"    summary: {yaml_scalar(item['summary'])}")
            out.append(f"    tags: [{', '.join(item['tags'])}]")
            out.append(f"    owners: [{', '.join(item['owners'])}]")
            out.append(f"    category: {item['category']}")

    out.append("")
    return "\n".join(out)


def yaml_scalar(value: str) -> str:
    """Render a string as a single-line YAML scalar.

    PyYAML's safe_dump folds long strings across lines which breaks the
    line-by-line generator output. Force single-line by quoting any
    string that contains YAML-special characters or that would otherwise
    line-break, and otherwise emit it bare.
    """
    if not value:
        return "''"
    needs_quote = any(c in value for c in (":", "#", "[", "]", "{", "}", ",", "'", '"', "\n"))
    if value.strip() != value:
        needs_quote = True
    if needs_quote:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def main() -> int:
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="exit 1 if file would change")
    mode.add_argument("--write", action="store_true", help="rewrite docs/_index.yaml")
    mode.add_argument("--diff", action="store_true", help="print unified diff")
    args = ap.parse_args()

    overrides = load_existing_overrides()
    categories = load_categories_block()
    if not categories:
        print("error: docs/_index.yaml is missing the `categories:` block; aborting", file=sys.stderr)
        return 2

    docs: list[dict] = []
    seen_paths: set[str] = set()
    for path in discover_docs(allowed_extras=set(overrides)):
        rel = path.relative_to(REPO_ROOT).as_posix()
        seen_paths.add(rel)
        docs.append(build_entry(path, overrides.get(rel)))

    removed = sorted(set(overrides) - seen_paths)
    if removed and (args.check or args.diff):
        print("Will drop entries (paths no longer on disk):", file=sys.stderr)
        for r in removed:
            print(f"  - {r}", file=sys.stderr)

    new_text = render_yaml(categories, docs)
    current_text = INDEX.read_text(encoding="utf-8") if INDEX.is_file() else ""

    if args.write:
        INDEX.write_text(new_text, encoding="utf-8")
        print(f"✓ wrote {INDEX} ({len(docs)} entries)")
        return 0

    if new_text == current_text:
        print(f"✓ docs/_index.yaml is already in sync ({len(docs)} entries)")
        return 0

    if args.diff:
        diff = difflib.unified_diff(
            current_text.splitlines(keepends=False),
            new_text.splitlines(keepends=False),
            fromfile="docs/_index.yaml (current)",
            tofile="docs/_index.yaml (would-write)",
            lineterm="",
        )
        for line in diff:
            print(line)
        return 0

    # check mode
    print("✗ docs/_index.yaml is out of sync.", file=sys.stderr)
    print(
        "  Run `python3 scripts/generate_docs_index.py --diff` to inspect, then "
        "`--write` to fix.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
