# backend/app/core/config.py
"""
TrackX Backend Configuration.

⚠️ SECURITY WARNING: 
This configuration file contains default values for development and testing.
For production deployment:
1. NEVER use default SECRET_KEY, database credentials, or admin passwords
2. Always use environment variables (.env file) for sensitive values
3. Generate a strong random SECRET_KEY (at least 64 characters)
4. Change all default passwords immediately
5. Use strong database passwords with proper access controls
6. Set ENVIRONMENT to "production" and review all security settings
7. Implement proper credential rotation policies
8. Use HTTPS/TLS for all production communications

Environment-based configuration. Copy .env.example to .env and adjust values.
"""

from typing import List, Optional, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import os
import warnings


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)
    # Project
    PROJECT_NAME: str = "TrackX"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"  # development, testing, production

    # Security
    SECRET_KEY: str = "CHANGE_THIS_TO_A_RANDOM_64_CHARACTER_STRING"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    JWT_ALGORITHM: str = "HS256"

    # CORS
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    # Database
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "trackx"
    POSTGRES_PASSWORD: str = "trackx_password"
    POSTGRES_DB: str = "trackx"
    
    # SQLite fallback (for development when PostgreSQL is not available)
    USE_SQLITE: bool = True
    SQLITE_DB_PATH: str = "backend/trackx.db"

    # Redis (for queue/caching)
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    # Camera Configuration (from your sheet)
    CAMERA_COUNT: int = 7
    DEFAULT_FRAME_SAMPLE: int = 10  # Process every 10th frame
    MAX_FRAME_PROCESSING: int = 1000  # Max frames per video processing

    # AI Pipeline
    VEHICLE_WEIGHTS: str = "yolov8n.pt"
    PLATE_WEIGHTS: str = "models/best_plate_detector.pt"
    OCR_MODEL_PATH: str = "models/lprnet_indian.pth"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/trackx.log"

    # Test Configuration - SECURITY: Change these defaults in production!
    FIRST_SUPERUSER: str = "admin@trackx.com"
    FIRST_SUPERUSER_PASSWORD: str = "admin123"

    @field_validator("BACKEND_CORS_ORIGINS", mode='before')
    @classmethod
    def assemble_cors_origins(cls, v):
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def SYNC_DATABASE_URI(self) -> str:
        """For migrations and sync operations."""
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


# Security validation on initialization
def _validate_security_settings():
    """Validate security settings and warn about unsafe configurations."""
    settings = Settings()
    
    security_warnings = []
    
    # Check for default secret key
    if settings.SECRET_KEY == "CHANGE_THIS_TO_A_RANDOM_64_CHARACTER_STRING":
        security_warnings.append("WARNING: Using default SECRET_KEY. Generate a strong random key for production!")
    
    # Check for default admin credentials
    if settings.FIRST_SUPERUSER_PASSWORD == "admin123":
        security_warnings.append("WARNING: Using default admin password. Change immediately for production!")
    
    # Check for default database credentials
    if settings.POSTGRES_PASSWORD == "trackx_password":
        security_warnings.append("WARNING: Using default database password. Change for production!")
    
    # Check if running in production with default values
    if settings.ENVIRONMENT == "production" and security_warnings:
        security_warnings.append("CRITICAL: Running in PRODUCTION with insecure default values!")
    
    # Print warnings if any (with encoding safety)
    if security_warnings:
        try:
            print("\n" + "="*70)
            print("SECURITY CONFIGURATION WARNINGS:")
            print("="*70)
            for warning in security_warnings:
                print(warning)
            print("="*70)
            print("Please review your .env file and environment variables.\n")
        except UnicodeEncodeError:
            # Fallback for systems with limited console encoding
            print("\n" + "="*70)
            print("SECURITY CONFIGURATION WARNINGS:")
            print("="*70)
            for warning in security_warnings:
                print(warning.encode('ascii', 'ignore').decode('ascii'))
            print("="*70)
            print("Please review your .env file and environment variables.\n")
        
        if settings.ENVIRONMENT == "production":
            warnings.warn(
                "Production environment detected with insecure default credentials. "
                "This is a critical security risk. Deployment should be halted until "
                "security settings are properly configured.",
                RuntimeWarning
            )


# Run security validation on module import
_validate_security_settings()

settings = Settings()
