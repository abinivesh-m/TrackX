"""Security hardening utilities."""

from fastapi import HTTPException, status
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

# Rate limiting (in-memory, Redis-backed in production)
_rate_limits = {}

class RateLimiter:
    """Simple rate limiter."""
    
    @staticmethod
    def check_rate_limit(key: str, max_requests: int = 100, window_seconds: int = 60) -> bool:
        """Check if request is within rate limit."""
        now = datetime.utcnow()
        
        if key not in _rate_limits:
            _rate_limits[key] = []
        
        # Remove old requests outside window
        cutoff = now - timedelta(seconds=window_seconds)
        _rate_limits[key] = [ts for ts in _rate_limits[key] if ts > cutoff]
        
        if len(_rate_limits[key]) >= max_requests:
            return False
        
        _rate_limits[key].append(now)
        return True

def rate_limit(max_requests: int = 100, window_seconds: int = 60):
    """Rate limit decorator."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Get client IP from request context
            request = kwargs.get("request")
            if request:
                client_ip = request.client.host
                if not RateLimiter.check_rate_limit(client_ip, max_requests, window_seconds):
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Rate limit exceeded"
                    )
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def generate_secure_token(length: int = 32) -> str:
    """Generate secure random token."""
    return secrets.token_urlsafe(length)

def hash_password(password: str) -> str:
    """Hash password with salt."""
    salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return f"{salt}${hashed.hex()}"

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash."""
    try:
        salt, stored_hash = hashed.split('$')
        hashed_check = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return hashed_check.hex() == stored_hash
    except:
        return False


# Alias used by auth/admin/seed code paths (kept in sync with hash_password)
get_password_hash = hash_password


def create_access_token(subject_or_data=None, data=None, expires_minutes: Optional[int] = None) -> str:
    """
    Create a signed JWT access token.

    Accepts either a payload dict (``create_access_token(data={"sub": ...})``)
    or a raw subject (``create_access_token(user_id)``). The token carries
    ``sub`` and ``type: "access"`` claims used by the auth dependency.
    """
    subject = None
    if isinstance(data, dict) and "sub" in data:
        subject = data["sub"]
    elif isinstance(subject_or_data, dict) and "sub" in subject_or_data:
        subject = subject_or_data["sub"]
    else:
        subject = subject_or_data
    if subject is None:
        raise ValueError("create_access_token requires a subject (sub) claim")
    from app.core.config import settings
    from datetime import datetime, timedelta, timezone
    import jwt as _jwt
    expire_minutes = expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    payload = {
        "sub": str(subject),
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=expire_minutes),
        "iat": datetime.now(timezone.utc),
    }
    return _jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(subject_or_data=None, data=None) -> str:
    """Create a signed JWT refresh token (longer-lived than access tokens)."""
    subject = None
    if isinstance(data, dict) and "sub" in data:
        subject = data["sub"]
    elif isinstance(subject_or_data, dict) and "sub" in subject_or_data:
        subject = subject_or_data["sub"]
    else:
        subject = subject_or_data
    if subject is None:
        raise ValueError("create_refresh_token requires a subject (sub) claim")
    from app.core.config import settings
    from datetime import datetime, timedelta, timezone
    import jwt as _jwt
    payload = {
        "sub": str(subject),
        "type": "refresh",
        "exp": datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return _jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT. Raises HTTP 401 on invalid/expired tokens."""
    from app.core.config import settings
    import jwt as _jwt
    try:
        payload = _jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except _jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload

# SQL Injection prevention
DANGEROUS_SQL_KEYWORDS = ['DROP', 'DELETE', 'TRUNCATE', 'INSERT', 'UPDATE', '--', ';', '/*', '*/']

def validate_sql_safe(query: str) -> bool:
    """Basic SQL injection detection."""
    query_upper = query.upper()
    return not any(keyword in query_upper for keyword in DANGEROUS_SQL_KEYWORDS)

# CORS hardening
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8501",
    "http://localhost:8000",
]

def get_allowed_origins():
    """Get CORS allowed origins from config."""
    import os
    origins_str = os.getenv("CORS_ORIGINS", ",".join(ALLOWED_ORIGINS))
    return [o.strip() for o in origins_str.split(",")]
