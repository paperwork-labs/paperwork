"""Concrete candidate generators.

Importing this package registers every generator with the
``CandidateGenerator`` registry via ``__init_subclass__``. Adding a
new generator: drop a module here and import it below.

medallion: gold
"""

from . import (
    stage2a_rs_strong,
    stage2a_rs_strong_kell,
)

__all__ = ["stage2a_rs_strong", "stage2a_rs_strong_kell"]
