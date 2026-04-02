"""
Agent Action Model
==================

Tracks all actions proposed or taken by the auto-ops agent.
Supports approval workflow for risky actions.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON, Boolean, Float, func
from sqlalchemy.orm import relationship

from . import Base


class AgentAction(Base):
    """Record of an action proposed or executed by the auto-ops agent."""
    
    __tablename__ = "agent_actions"

    id = Column(Integer, primary_key=True, index=True)
    
    # Action details
    action_type = Column(String(100), nullable=False, index=True)
    action_name = Column(String(255), nullable=False)
    payload = Column(JSON, nullable=True)
    
    # Risk classification
    risk_level = Column(String(20), nullable=False, index=True)  # safe, moderate, risky, critical
    
    # Status tracking
    status = Column(String(20), nullable=False, default="pending", server_default="pending", index=True)
    # pending -> approved/rejected -> executing -> completed/failed
    
    # LLM reasoning
    reasoning = Column(Text, nullable=True)
    context_summary = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)  # LLM's self-assessed confidence (0.0-1.0)
    
    # Execution details
    task_id = Column(String(100), nullable=True)  # Celery task ID if dispatched
    result = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, server_default=func.now(), nullable=False)
    approved_at = Column(DateTime, nullable=True)
    executed_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Approval tracking
    approved_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by = relationship("User", foreign_keys=[approved_by_id])
    auto_approved = Column(Boolean, default=False)
    
    # Session tracking (for conversation memory)
    session_id = Column(String(50), nullable=True, index=True)
    
    def __repr__(self):
        return f"<AgentAction {self.id}: {self.action_type} [{self.status}]>"
    
    @property
    def is_auto_executable(self) -> bool:
        """Check if this action can be auto-executed based on risk level."""
        return self.risk_level in ("safe", "moderate")
    
    @property
    def requires_approval(self) -> bool:
        """Check if this action requires human approval."""
        return self.risk_level in ("risky", "critical")
    
    @property
    def duration_ms(self) -> Optional[int]:
        """Execution duration in milliseconds."""
        if self.executed_at and self.completed_at:
            delta = self.completed_at - self.executed_at
            return int(delta.total_seconds() * 1000)
        return None
