"""
Agent Message Model
====================

Stores conversation messages for agent chat sessions.
Messages were previously stored in Redis with a TTL, but are now
persisted to PostgreSQL for indefinite retention.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, DateTime, Integer, String, Text, JSON, func

from . import Base


class AgentMessage(Base):
    """A single message in an agent conversation."""

    __tablename__ = "agent_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(50), nullable=False, index=True)
    message_index = Column(Integer, nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=True)
    tool_calls = Column(JSON, nullable=True)
    tool_call_id = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<AgentMessage {self.id}: session={self.session_id} role={self.role}>"

    def to_openai_format(self) -> Dict[str, Any]:
        """Convert to OpenAI message format for API replay."""
        msg: Dict[str, Any] = {"role": self.role}

        if self.content is not None:
            msg["content"] = self.content

        if self.tool_calls:
            msg["tool_calls"] = self.tool_calls

        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id

        return msg

    @classmethod
    def from_openai_format(
        cls,
        session_id: str,
        message_index: int,
        msg: Dict[str, Any],
    ) -> "AgentMessage":
        """Create an AgentMessage from OpenAI message format."""
        return cls(
            session_id=session_id,
            message_index=message_index,
            role=msg.get("role", "unknown"),
            content=msg.get("content"),
            tool_calls=msg.get("tool_calls"),
            tool_call_id=msg.get("tool_call_id"),
        )


def load_conversation_from_db(
    db,
    session_id: str,
) -> Optional[List[Dict[str, Any]]]:
    """Load conversation messages from the database.

    Returns:
        List of messages in OpenAI format, or None if not found.
    """
    messages = (
        db.query(AgentMessage)
        .filter(AgentMessage.session_id == session_id)
        .order_by(AgentMessage.message_index)
        .all()
    )

    if not messages:
        return None

    return [m.to_openai_format() for m in messages]


def save_conversation_to_db(
    db,
    session_id: str,
    conversation: List[Dict[str, Any]],
) -> bool:
    """Save conversation messages to the database.

    Replaces existing messages for the session with the new conversation.

    Returns:
        True on success, False on failure.
    """
    try:
        db.query(AgentMessage).filter(
            AgentMessage.session_id == session_id
        ).delete()

        for idx, msg in enumerate(conversation):
            agent_msg = AgentMessage.from_openai_format(session_id, idx, msg)
            db.add(agent_msg)

        db.commit()
        return True
    except Exception:
        db.rollback()
        logging.getLogger(__name__).exception(
            "save_conversation_to_db failed for session %s", session_id,
        )
        return False
