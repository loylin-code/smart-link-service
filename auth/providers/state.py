"""OAuth State Persistence Manager"""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import Column, String, DateTime
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import Base


class OAuthState(Base):
    """
    OAuth State model for CSRF protection.
    
    Stores OAuth state parameters to prevent CSRF attacks during
    the OAuth2 authorization flow.
    """
    __tablename__ = "oauth_states"
    
    id = Column(String, primary_key=True, default=lambda: secrets.token_urlsafe(16))
    state = Column(String, unique=True, nullable=False, index=True)
    provider = Column(String, nullable=False)
    redirect_uri = Column(String, nullable=False)
    tenant_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    
    def __repr__(self) -> str:
        return f"<OAuthState(state={self.state}, provider={self.provider})>"


class StateManager:
    """
    Manages OAuth state persistence and validation.
    
    Provides CRUD operations for OAuth state records with automatic
    expiration handling and one-time-use validation.
    """
    
    EXPIRY_MINUTES = 10
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
    
    async def create_state(
        self,
        provider: str,
        redirect_uri: str,
        tenant_id: Optional[str] = None
    ) -> OAuthState:
        """
        Create a new OAuth state record.
        
        Args:
            provider: OAuth provider name (e.g., 'google', 'github')
            redirect_uri: Callback URI for OAuth completion
            tenant_id: Optional tenant identifier for multi-tenant setups
            
        Returns:
            Created OAuthState record
        """
        state_value = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        expires_at = now + timedelta(minutes=self.EXPIRY_MINUTES)
        
        state_record = OAuthState(
            state=state_value,
            provider=provider,
            redirect_uri=redirect_uri,
            tenant_id=tenant_id,
            created_at=now,
            expires_at=expires_at
        )
        
        self.db.add(state_record)
        await self.db.commit()
        await self.db.refresh(state_record)
        
        return state_record
    
    async def validate_state(self, state: str) -> Optional[OAuthState]:
        """
        Validate and consume an OAuth state.
        
        This is a one-time-use validation: if successful, the state
        record is deleted to prevent replay attacks.
        
        Args:
            state: The OAuth state parameter to validate
            
        Returns:
            OAuthState record if valid, None if invalid/expired/not found
        """
        from sqlalchemy import select
        
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        
        # Query for the state
        query = select(OAuthState).where(
            OAuthState.state == state,
            OAuthState.expires_at > now
        )
        result = await self.db.execute(query)
        state_record = result.scalar_one_or_none()
        
        if state_record is None:
            return None
        
        # Valid state - delete it (one-time use)
        await self.db.delete(state_record)
        await self.db.commit()
        
        return state_record
    
    async def cleanup_expired(self) -> int:
        """
        Remove expired state records from the database.
        
        Returns:
            Number of records deleted
        """
        from sqlalchemy import select, delete
        
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        
        # Delete expired states
        query = delete(OAuthState).where(
            OAuthState.expires_at <= now
        )
        result = await self.db.execute(query)
        await self.db.commit()
        
        return result.rowcount or 0
