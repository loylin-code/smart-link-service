"""
LLM Cache entry model for storing cached LLM responses
"""
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Integer, DateTime
import uuid

from db.session import Base


def generate_uuid() -> str:
    """Generate a UUID string"""
    return str(uuid.uuid4())


class LLMCacheEntry(Base):
    """
    SQLite model for LLM response cache entries.
    
    Cache key is SHA-256 hash of (system_prompt + user_message + model).
    Lazy expiration: entries deleted when expires_at <= now on read.
    """
    
    __tablename__ = "llm_cache_entries"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    cache_key = Column(String(64), unique=True, index=True, nullable=False)
    system_prompt = Column(Text, nullable=False)
    user_message = Column(Text, nullable=False)
    response = Column(Text, nullable=False)  # JSON response
    model = Column(String(50), nullable=False)
    provider = Column(String(50), nullable=False)
    tokens_used = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=False)
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "cache_key": self.cache_key,
            "system_prompt": self.system_prompt,
            "user_message": self.user_message,
            "response": self.response,
            "model": self.model,
            "provider": self.provider,
            "tokens_used": self.tokens_used,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }