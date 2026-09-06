# backend/tests/test_auth.py

import pytest
from fastapi import HTTPException
from app.core.security import (
    create_access_token, create_refresh_token,
    decode_token, verify_password, get_password_hash
)


def test_password_hashing():
    """Test password hashing."""
    password = "test_password_123"
    hashed = get_password_hash(password)
    
    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("wrong_password", hashed)


def test_token_creation():
    """Test JWT token creation and decoding."""
    user_id = 1
    access_token = create_access_token(user_id)
    
    payload = decode_token(access_token)
    
    assert payload["sub"] == str(user_id)
    assert payload["type"] == "access"


def test_refresh_token_type():
    """Test refresh token type."""
    user_id = 1
    refresh_token = create_refresh_token(user_id)
    
    payload = decode_token(refresh_token)
    
    assert payload["sub"] == str(user_id)
    assert payload["type"] == "refresh"


def test_invalid_token():
    """Test invalid token raises error."""
    invalid_token = "invalid.token.here"
    
    with pytest.raises(HTTPException):
        decode_token(invalid_token)
