"""
Security utilities for authentication and authorization
"""
import secrets
from typing import Optional
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from core.config import settings
from core.exceptions import AuthenticationError

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def generate_api_key() -> str:
    """Generate a secure random API key"""
    return f"sk-{secrets.token_urlsafe(32)}"


def verify_api_key(api_key: str) -> bool:
    """
    Verify API key
    For now, we only check against master API key
    In production, this should check against database
    """
    return api_key == settings.MASTER_API_KEY


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=24)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm="HS256"
    )
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    """Decode and validate JWT access token"""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"]
        )
        return payload
    except JWTError as e:
        raise AuthenticationError(f"Invalid token: {str(e)}")


def generate_session_id() -> str:
    """Generate a unique session ID"""
    return secrets.token_urlsafe(16)