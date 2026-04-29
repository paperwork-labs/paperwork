"""One-shot backfill: import legacy founder_actions.yaml into the Conversations store.

Usage:
    cd apis/brain
    python scripts/backfill_founder_actions_to_conversations.py [--path PATH]

The script is idempotent — already-imported items are skipped (matched by
parent_action_id).  Keep founder_actions.yaml in place for now; PR J will
delete it once all consumers migrate.

# LEGACY: founder_actions.yaml is the source for this backfill.
# Use GET /api/v1/admin/conversations?filter=needs-action going forward.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running from the apis/brain directory without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.conversations import backfill_from_founder_actions_yaml


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill founder_actions.yaml → Conversations")
    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Path to founder_actions.yaml (default: apis/brain/data/founder_actions.yaml)",
    )
    args = parser.parse_args()

    created = backfill_from_founder_actions_yaml(path=args.path)
    import sys

    sys.stdout.write(f"Backfill complete: {created} conversations created.\n")


if __name__ == "__main__":
    main()
