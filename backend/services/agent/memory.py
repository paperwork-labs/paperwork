"""Agent memory system for long-term learning.

Stores observations, decisions, and outcomes to enable learning from experience.

medallion: ops
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, Integer, String, JSON, DateTime, Float, Index, Text
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from backend.config import settings
from backend.models import Base

logger = logging.getLogger(__name__)


class MemoryType(str, Enum):
    """Types of memories stored."""
    OBSERVATION = "observation"  # Market conditions observed
    DECISION = "decision"  # Trading decisions made
    OUTCOME = "outcome"  # Results of decisions
    INSIGHT = "insight"  # Derived patterns/learnings
    CONTEXT = "context"  # Market/portfolio context


@dataclass
class Memory:
    """A single memory entry."""
    id: Optional[int]
    memory_type: MemoryType
    content: str
    embedding: Optional[List[float]]
    metadata: Dict[str, Any]
    created_at: datetime
    relevance_score: float = 0.0
    tags: List[str] = field(default_factory=list)


class AgentMemory(Base):
    """Database model for agent memories."""
    
    __tablename__ = "agent_memories"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    memory_type = Column(String(50), nullable=False, index=True)
    content = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False, index=True)  # For deduplication
    embedding = Column(JSON, nullable=True)  # Vector embedding
    metadata = Column(JSON, nullable=True)
    tags = Column(JSON, nullable=True)
    relevance_score = Column(Float, default=0.0)
    access_count = Column(Integer, default=0)
    last_accessed = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        Index("idx_memory_user_type", "user_id", "memory_type"),
        Index("idx_memory_created", "created_at"),
        Index("idx_memory_hash", "content_hash"),
    )


class MemoryService:
    """Manages agent long-term memory.
    
    Features:
    - Store observations, decisions, outcomes
    - Semantic search via embeddings
    - Find similar past situations
    - Learn from outcomes to improve decisions
    """
    
    MAX_CONTENT_LENGTH = 10000
    
    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self._embedder = None
    
    def store(
        self,
        memory_type: MemoryType,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> Memory:
        """Store a new memory.
        
        Args:
            memory_type: Type of memory
            content: Text content to store
            metadata: Additional structured data
            tags: Tags for categorization
            
        Returns:
            Created Memory object
        """
        content = content[:self.MAX_CONTENT_LENGTH]
        content_hash = self._hash_content(content)
        
        # Check for duplicate
        existing = (
            self.db.query(AgentMemory)
            .filter(
                AgentMemory.user_id == self.user_id,
                AgentMemory.content_hash == content_hash,
            )
            .first()
        )
        
        if existing:
            # Update access count
            existing.access_count += 1
            existing.last_accessed = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(existing)
            
            return Memory(
                id=existing.id,
                memory_type=MemoryType(existing.memory_type),
                content=existing.content,
                embedding=existing.embedding,
                metadata=existing.metadata or {},
                created_at=existing.created_at,
                tags=existing.tags or [],
            )
        
        # Generate embedding if possible
        embedding = self._generate_embedding(content)
        
        memory = AgentMemory(
            user_id=self.user_id,
            memory_type=memory_type.value,
            content=content,
            content_hash=content_hash,
            embedding=embedding,
            metadata=metadata or {},
            tags=tags or [],
        )
        
        self.db.add(memory)
        self.db.commit()
        self.db.refresh(memory)
        
        logger.info(
            "Stored %s memory for user %s: %s",
            memory_type.value,
            self.user_id,
            content[:50],
        )
        
        return Memory(
            id=memory.id,
            memory_type=memory_type,
            content=memory.content,
            embedding=memory.embedding,
            metadata=memory.metadata or {},
            created_at=memory.created_at,
            tags=memory.tags or [],
        )
    
    def search(
        self,
        query: str,
        memory_type: Optional[MemoryType] = None,
        tags: Optional[List[str]] = None,
        limit: int = 10,
        days: Optional[int] = None,
    ) -> List[Memory]:
        """Search memories semantically.
        
        Args:
            query: Search query text
            memory_type: Filter by type
            tags: Filter by tags
            limit: Max results
            days: Limit to recent days
            
        Returns:
            List of relevant memories
        """
        q = self.db.query(AgentMemory).filter(AgentMemory.user_id == self.user_id)
        
        if memory_type:
            q = q.filter(AgentMemory.memory_type == memory_type.value)
        
        if days:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            q = q.filter(AgentMemory.created_at >= cutoff)
        
        # Get all candidates
        candidates = q.order_by(AgentMemory.created_at.desc()).limit(limit * 5).all()
        
        if not candidates:
            return []
        
        # If we have embeddings, do semantic search
        query_embedding = self._generate_embedding(query)
        
        # Calculate scores for ranking
        scored_candidates: List[tuple] = []  # (mem, score)
        
        if query_embedding:
            # Score by cosine similarity
            for mem in candidates:
                if mem.embedding:
                    score = self._cosine_similarity(query_embedding, mem.embedding)
                else:
                    score = self._keyword_score(query, mem.content)
                scored_candidates.append((mem, score))
        else:
            # Keyword-based search
            query_lower = query.lower()
            for mem in candidates:
                if query_lower in mem.content.lower():
                    score = self._keyword_score(query, mem.content)
                else:
                    score = 0.0
                scored_candidates.append((mem, score))
        
        # Sort by score descending
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        scored_candidates = scored_candidates[:limit]
        
        # Filter by tags if specified
        if tags:
            tag_set = set(tags)
            scored_candidates = [
                (m, s) for m, s in scored_candidates
                if m.tags and tag_set.intersection(m.tags)
            ]
        
        # Update access counts
        for mem, _ in scored_candidates:
            mem.access_count += 1
            mem.last_accessed = datetime.now(timezone.utc)
        self.db.commit()
        
        return [
            Memory(
                id=m.id,
                memory_type=MemoryType(m.memory_type),
                content=m.content,
                embedding=m.embedding,
                metadata=m.metadata or {},
                created_at=m.created_at,
                tags=m.tags or [],
                relevance_score=score,  # Properly pass the computed score
            )
            for m, score in scored_candidates
        ]
    
    def find_similar_situations(
        self,
        current_context: Dict[str, Any],
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Find similar past situations and their outcomes.
        
        Args:
            current_context: Current market/portfolio context
            limit: Max results
            
        Returns:
            List of similar situations with outcomes
        """
        # Build search query from context
        context_parts = []
        
        if "regime" in current_context:
            context_parts.append(f"regime {current_context['regime']}")
        if "symbol" in current_context:
            context_parts.append(f"symbol {current_context['symbol']}")
        if "stage" in current_context:
            context_parts.append(f"stage {current_context['stage']}")
        if "action" in current_context:
            context_parts.append(f"action {current_context['action']}")
        
        query = " ".join(context_parts) or "trading decision"
        
        # Find relevant decisions
        decisions = self.search(
            query=query,
            memory_type=MemoryType.DECISION,
            limit=limit * 2,
        )
        
        results = []
        for decision in decisions[:limit]:
            # Find associated outcome
            outcome = self._find_outcome_for_decision(decision)
            
            results.append({
                "decision": {
                    "id": decision.id,
                    "content": decision.content,
                    "metadata": decision.metadata,
                    "created_at": decision.created_at.isoformat(),
                },
                "outcome": {
                    "content": outcome.content if outcome else None,
                    "metadata": outcome.metadata if outcome else None,
                } if outcome else None,
                "similarity": decision.relevance_score,
            })
        
        return results
    
    def store_decision_outcome(
        self,
        decision_content: str,
        outcome_content: str,
        success: bool,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Store a decision and its outcome together.
        
        Used for learning from results.
        """
        decision_id = self._hash_content(decision_content)[:16]
        
        # Store decision
        self.store(
            memory_type=MemoryType.DECISION,
            content=decision_content,
            metadata={
                **(metadata or {}),
                "decision_id": decision_id,
            },
        )
        
        # Store outcome
        self.store(
            memory_type=MemoryType.OUTCOME,
            content=outcome_content,
            metadata={
                **(metadata or {}),
                "decision_id": decision_id,
                "success": success,
            },
        )
    
    def get_recent(
        self,
        memory_type: Optional[MemoryType] = None,
        limit: int = 10,
    ) -> List[Memory]:
        """Get recent memories."""
        q = self.db.query(AgentMemory).filter(AgentMemory.user_id == self.user_id)
        
        if memory_type:
            q = q.filter(AgentMemory.memory_type == memory_type.value)
        
        memories = q.order_by(AgentMemory.created_at.desc()).limit(limit).all()
        
        return [
            Memory(
                id=m.id,
                memory_type=MemoryType(m.memory_type),
                content=m.content,
                embedding=m.embedding,
                metadata=m.metadata or {},
                created_at=m.created_at,
                tags=m.tags or [],
            )
            for m in memories
        ]
    
    def summarize_learnings(self, days: int = 30) -> Dict[str, Any]:
        """Summarize key learnings from recent memories."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Get recent outcomes
        outcomes = (
            self.db.query(AgentMemory)
            .filter(
                AgentMemory.user_id == self.user_id,
                AgentMemory.memory_type == MemoryType.OUTCOME.value,
                AgentMemory.created_at >= cutoff,
            )
            .all()
        )
        
        successes = [o for o in outcomes if o.metadata and o.metadata.get("success")]
        failures = [o for o in outcomes if o.metadata and not o.metadata.get("success")]
        
        return {
            "period_days": days,
            "total_decisions": len(outcomes),
            "successful_decisions": len(successes),
            "failed_decisions": len(failures),
            "success_rate": len(successes) / len(outcomes) if outcomes else 0.0,
            "recent_successes": [s.content[:100] for s in successes[:3]],
            "recent_failures": [f.content[:100] for f in failures[:3]],
        }
    
    def _find_outcome_for_decision(self, decision: Memory) -> Optional[Memory]:
        """Find the outcome associated with a decision."""
        decision_id = (decision.metadata or {}).get("decision_id")
        if not decision_id:
            return None
        
        outcome = (
            self.db.query(AgentMemory)
            .filter(
                AgentMemory.user_id == self.user_id,
                AgentMemory.memory_type == MemoryType.OUTCOME.value,
            )
            .all()
        )
        
        for o in outcome:
            if o.metadata and o.metadata.get("decision_id") == decision_id:
                return Memory(
                    id=o.id,
                    memory_type=MemoryType.OUTCOME,
                    content=o.content,
                    embedding=o.embedding,
                    metadata=o.metadata or {},
                    created_at=o.created_at,
                    tags=o.tags or [],
                )
        
        return None
    
    def _hash_content(self, content: str) -> str:
        """Generate hash for content deduplication."""
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding for text.
        
        Uses OpenAI embeddings if available, falls back to None.
        """
        api_key = getattr(settings, "OPENAI_API_KEY", None)
        if not api_key:
            return None
        
        try:
            import openai
            
            client = openai.OpenAI(api_key=api_key)
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=text[:8000],  # Limit input length
            )
            return response.data[0].embedding
            
        except Exception as e:
            logger.debug("Failed to generate embedding: %s", e)
            return None
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        import math
        
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot / (norm_a * norm_b)
    
    def _keyword_score(self, query: str, content: str) -> float:
        """Simple keyword matching score."""
        query_words = set(query.lower().split())
        content_words = set(content.lower().split())
        
        if not query_words:
            return 0.0
        
        overlap = len(query_words.intersection(content_words))
        return overlap / len(query_words)
