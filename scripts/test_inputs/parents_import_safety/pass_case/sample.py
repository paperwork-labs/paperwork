"""Fixture: shallow ``parents[2]`` only (safe for this guard)."""

from pathlib import Path

SAFE = Path(__file__).resolve().parents[2]
