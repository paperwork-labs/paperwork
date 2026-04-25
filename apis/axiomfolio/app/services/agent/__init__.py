"""
Agent Services
==============

LLM-powered trading agent for AxiomFolio.

Track M.5: the class was renamed ``AgentBrain`` → ``TradingAgent`` to
end the semantic overload with Paperwork Brain. ``AgentBrain`` is kept
as a deprecation alias so existing imports stay green; new code should
import ``TradingAgent``.

medallion: ops
"""

from .brain import AgentBrain, TradingAgent
from .tools import AGENT_TOOLS
from .taxonomy import RiskLevel, classify_action_risk

__all__ = [
    "TradingAgent",
    "AgentBrain",
    "AGENT_TOOLS",
    "RiskLevel",
    "classify_action_risk",
]
