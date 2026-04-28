"""Fixture: unmitigated ``parents[5]`` at import time (should fail the guard)."""

from pathlib import Path

BAD = Path(__file__).resolve().parents[5]
