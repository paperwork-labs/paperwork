from __future__ import annotations

"""medallion: silver"""
from typing import Iterable


def compute_stage_run_lengths(
    stage_labels: Iterable[str | None],
) -> list[dict[str, int | str | None]]:
    """Compute run-length metadata for a stage series.

    For each label in order, returns:
    - current_stage_days: number of consecutive trading days in the current stage
    - previous_stage_label: the prior distinct stage label
    - previous_stage_days: number of consecutive trading days in the prior stage
    """

    results: list[dict[str, int | str | None]] = []
    current_label: str | None = None
    current_len = 0
    prev_label: str | None = None
    prev_len: int | None = None

    for raw in stage_labels:
        label = (
            raw
            if isinstance(raw, str)
            and raw.strip()
            and raw.strip().upper() != "UNKNOWN"
            else None
        )
        if label is None:
            current_label = None
            current_len = 0
            prev_label = None
            prev_len = None
            results.append(
                {
                    "current_stage_days": None,
                    "previous_stage_label": None,
                    "previous_stage_days": None,
                }
            )
            continue

        if label == current_label:
            current_len += 1
        else:
            if current_label is not None:
                prev_label = current_label
                prev_len = current_len
            else:
                prev_label = None
                prev_len = None
            current_label = label
            current_len = 1

        results.append(
            {
                "current_stage_days": current_len,
                "previous_stage_label": prev_label,
                "previous_stage_days": prev_len,
            }
        )

    return results
