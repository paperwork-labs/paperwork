"""Celery tasks for the corporate-action engine."""

from .daily_apply import daily_corporate_actions

__all__ = ["daily_corporate_actions"]
