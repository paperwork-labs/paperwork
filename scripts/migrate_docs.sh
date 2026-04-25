#!/usr/bin/env bash
# scripts/migrate_docs.sh
#
# Phase 1 execution of docs/DOCS_STREAMLINE_2026Q2.md:
#   1. Retire 17 stale docs into docs/archive/ (git mv)
#   2. Rename docs/axiomfolio/KNOWLEDGE.md -> DECISIONS.md (collision)
#   3. Inject standard frontmatter on every retained doc
#
# Idempotent: re-running after a partial run skips already-moved files.
# Source-of-truth: docs/generated/docs-streamline-2026q2-decisions.json
set -euo pipefail

cd "$(dirname "$0")/.."

ARCHIVE=docs/archive
mkdir -p "$ARCHIVE"

mv_safe() {
  local src="$1"
  local dest="$2"
  if [[ ! -e "$src" ]]; then
    echo "  - already moved or missing: $src"
    return 0
  fi
  if [[ -e "$dest" ]]; then
    echo "  ! destination exists, skipping: $dest"
    return 0
  fi
  git mv "$src" "$dest"
  echo "  + $src -> $dest"
}

echo "==> Phase 1a: retire 17 stale docs to $ARCHIVE/"

# Root-level retirements
mv_safe docs/AXIOMFOLIO_HANDOFF.md         "$ARCHIVE/AXIOMFOLIO_HANDOFF.md"
mv_safe docs/AXIOMFOLIO_INTEGRATION.md     "$ARCHIVE/AXIOMFOLIO_INTEGRATION.md"
mv_safe docs/PHASE2-COMPOSER-HANDOFFS.md   "$ARCHIVE/PHASE2-COMPOSER-HANDOFFS.md"

# AxiomFolio retirements
mv_safe docs/axiomfolio/RENDER_INVENTORY.md   "$ARCHIVE/axiomfolio-RENDER_INVENTORY.md"
mv_safe docs/axiomfolio/PAPERWORK_HANDOFF.md  "$ARCHIVE/axiomfolio-PAPERWORK_HANDOFF.md"

# AxiomFolio plans / agent-automation (migration is done)
mv_safe docs/axiomfolio/plans/agent-automation/00-repo-move.md                 "$ARCHIVE/agent-automation-00-repo-move.md"
mv_safe docs/axiomfolio/plans/agent-automation/00-repo-move-preflight-snapshot.md "$ARCHIVE/agent-automation-00-repo-move-preflight-snapshot.md"
mv_safe docs/axiomfolio/plans/agent-automation/01-axiomfolio-side.md           "$ARCHIVE/agent-automation-01-axiomfolio-side.md"
mv_safe docs/axiomfolio/plans/agent-automation/02-paperwork-brain-side.md      "$ARCHIVE/agent-automation-02-paperwork-brain-side.md"
mv_safe docs/axiomfolio/plans/agent-automation/HANDOFF.md                      "$ARCHIVE/agent-automation-HANDOFF.md"
mv_safe docs/axiomfolio/plans/agent-automation/preflight-data/README.md        "$ARCHIVE/agent-automation-preflight-data-README.md"

# AxiomFolio handoffs (4) — point-in-time
mv_safe docs/axiomfolio/handoffs/2026-04-20-midnight-merge-storm.md     "$ARCHIVE/handoff-2026-04-20-midnight-merge-storm.md"
mv_safe docs/axiomfolio/handoffs/2026-04-21-g22-shipped-next-g23.md     "$ARCHIVE/handoff-2026-04-21-g22-shipped-next-g23.md"
mv_safe docs/axiomfolio/handoffs/2026-04-21-plan-reality-check.md       "$ARCHIVE/handoff-2026-04-21-plan-reality-check.md"
mv_safe docs/axiomfolio/handoffs/STAGE_QUALITY_DIAGNOSIS_2026Q2.md      "$ARCHIVE/handoff-STAGE_QUALITY_DIAGNOSIS_2026Q2.md"

# Design system retirement (page renamed in code)
mv_safe docs/axiomfolio/design-system/pages/intelligence.md "$ARCHIVE/axiomfolio-design-pages-intelligence.md"

echo
echo "==> Phase 1b: collision rename (axiomfolio/KNOWLEDGE.md -> DECISIONS.md)"
mv_safe docs/axiomfolio/KNOWLEDGE.md docs/axiomfolio/DECISIONS.md

# Clean up empty subdirs
rmdir docs/axiomfolio/plans/agent-automation/preflight-data 2>/dev/null || true

echo
echo "==> Phase 1c: inject standard frontmatter on retained docs"
python3 scripts/inject_doc_frontmatter.py

echo
echo "==> Done. Verify with:"
echo "    git status --short"
echo "    python scripts/check_docs_index.py"
echo "    python scripts/check_doc_code_refs.py"
