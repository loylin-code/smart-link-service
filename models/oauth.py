"""
OAuth models for SmartLink
"""
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Integer
import uuid

from db.session import Base


def generate_uuid() -> str:
    """Generate a UUID string"""
    return str(uuid.uuid4())


class OAuthClient(Base):
    """
    OAuth 客户端（Client Credentials Flow）
    """
    __tablename__ = "oauth_clients"
    
    id = Column(String(64), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(64), nullable=False, index=True)
    client_id = Column(String(64), unique=True, nullable=False, index=True)
    secret_hash = Column(String(64), nullable=False)  # SHA-256 hash
    name = Column(String(255), nullable=False)  # 客户端名称
    allowed_scopes = Column(String(1024), default="[]")  # JSON 格式
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True)
    total_requests = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f"<OAuthClient(id={self.id}, client_id={self.client_id}, name={self.name})>"
