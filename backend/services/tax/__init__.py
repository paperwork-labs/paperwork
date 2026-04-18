"""
Tax services
============

Houses tax-export and tax-reporting logic that is shared across HTTP routes,
Celery tasks, and admin tooling.

Today this package only exposes the FileFree.ai exporter, but it is the
single landing zone for any future:

* IRS Form 8949 / Schedule D generators
* 1099-B reconciliation tools
* Per-broker tax-lot importers (IBKR, Schwab, etc.)

Design rules (do not violate without bumping a schema_version):

* Every public exporter must return a Pydantic model with an explicit
  ``schema_version`` field. Downstream products (FileFree.ai, accounting
  spreadsheets, audit log) depend on a stable contract.
* All monetary values are ``Decimal``. Never ``float``. Never re-cast to
  ``float`` on the way out unless the consumer explicitly requires it
  (CSV serialization is OK because it stringifies anyway).
* Database access lives in the exporter layer; pure transforms live in
  the mapper layer. This keeps the mapper unit-testable without a DB.
"""

from .schemas import (
    SCHEMA_VERSION,
    DataQuality,
    FileFreeAccount,
    FileFreeLot,
    FileFreePackage,
    FileFreeSummary,
    LotTerm,
)

__all__ = [
    "SCHEMA_VERSION",
    "DataQuality",
    "FileFreeAccount",
    "FileFreeLot",
    "FileFreePackage",
    "FileFreeSummary",
    "LotTerm",
]
