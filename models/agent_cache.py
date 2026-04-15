"""
Agent cache entry model for caching agent configurations
"""
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime
import uuid

from db.session import Base


def generate_uuid() -> str:
    """Generate a UUID string"""
    return str(uuid.uuid4())


class AgentCacheEntry(Base):
    """
    SQLite model for agent configuration cache entries.
    
    Uses agent_id as unique key for lookups.
    Lazy expiration: entries deleted when expires_at <= now on read.
    """
    
    __tablename__ = "agent_cache_entries"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    agent_id = Column(String(36), unique=True, index=True, nullable=False)
    config_json = Column(Text, nullable=False)  # Full agent config as JSON
    model = Column(String(50), nullable=True)  # Model name for metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "config_json": self.config_json,
            "model": self.model,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }