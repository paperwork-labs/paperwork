"""Brain (Paperwork) integration: webhooks and related clients.

medallion: ops
"""

from app.services.brain.webhook_client import BrainWebhookClient, brain_webhook

__all__ = ["BrainWebhookClient", "brain_webhook"]
