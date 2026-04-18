"""Celery tasks for the picks pipeline."""

from . import generate_candidates  # noqa: F401

__all__ = ["generate_candidates"]
