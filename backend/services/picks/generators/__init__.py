"""Concrete candidate generators.

Importing this package registers every generator with the
``CandidateGenerator`` registry via ``__init_subclass__``. Adding a
new generator: drop a module here and import it below.
"""

from . import stage2a_rs_strong  # noqa: F401  (registers via __init_subclass__)

__all__ = ["stage2a_rs_strong"]
