"""
Serialization helpers for FileFree.ai exports.

The JSON path is just ``package.model_dump_json()`` (Pydantic v2 handles it),
so this module focuses on the CSV path -- a flat one-row-per-lot rendering
that mirrors the existing Schedule D CSV in
``backend/api/routes/portfolio/stocks.py`` but with a few extra columns
the FileFree.ai pipeline expects.

Keeping CSV column headers in one place means the contract is reviewable in
isolation; bumping it requires a corresponding ``schema_version`` change.

medallion: silver
"""

from __future__ import annotations

import csv
import io
from typing import List

from .schemas import FileFreePackage

# Column order is part of the wire contract -- do not reorder without a
# schema_version bump.
CSV_COLUMNS: List[str] = [
    "lot_id",
    "account_ref",
    "symbol",
    "description",
    "instrument_type",
    "quantity",
    "date_acquired",
    "date_sold",
    "proceeds",
    "cost_basis",
    "realized_gain",
    "term",
    "is_wash_sale",
    "wash_sale_disallowed_loss",
    "adjustment_code",
    "data_quality",
    "source",
]


def package_to_csv(package: FileFreePackage) -> str:
    """Render a :class:`FileFreePackage` as a CSV blob (one row per lot).

    The summary, accounts, and warnings are NOT rendered into the CSV --
    they're available via the JSON endpoint. CSV is intended for
    spreadsheet / Form-8949 ingestion only.
    """
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for lot in package.lots:
        writer.writerow(
            [
                lot.lot_id,
                lot.account_ref,
                lot.symbol,
                lot.description,
                lot.instrument_type.value,
                f"{lot.quantity:f}",
                lot.date_acquired.isoformat() if lot.date_acquired else "VARIOUS",
                lot.date_sold.isoformat(),
                f"{lot.proceeds:.2f}",
                f"{lot.cost_basis:.2f}",
                f"{lot.realized_gain:.2f}",
                lot.term.value,
                "true" if lot.is_wash_sale else "false",
                f"{lot.wash_sale_disallowed_loss:.2f}"
                if lot.wash_sale_disallowed_loss is not None
                else "",
                lot.adjustment_code or "",
                lot.data_quality.value,
                lot.source,
            ]
        )
    return buf.getvalue()
