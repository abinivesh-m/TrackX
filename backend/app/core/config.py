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

from pathlib import Path
from typing import List, Optional, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv
import os
import warnings

# Repo root is three levels up from this file (backend/app/core/config.py).
_REPO_ROOT = Path(__file__).resolve().parents[3]

# SIH26127 real-camera integration (2026-09-14): pydantic-settings' own
# `env_file=".env"` below (Settings.model_config) reads backend/.env
# ONLY into ITS OWN declared fields - it never mutates the real process
# os.environ. network/rtsp_camera.py is a separate module that reads
# TRACKX_RTSP_<CAM_ID>_* directly via os.environ.get(...) (see its
# _env_for() helper), same as every deployment platform's real env vars
# work - so without an explicit load_dotenv() call somewhere, those vars
# were NEVER actually visible to it no matter what backend/.env contained.
# This was a real, confirmed bug: adding TRACKX_RTSP_CAM_01_* to
# backend/.env and restarting the backend still left CAM_01 resolving to
# its simulated fallback, because os.environ genuinely never had the
# values. load_dotenv() (python-dotenv, already a declared dependency -
# see backend/requirements.txt) actually populates os.environ, so both
# Settings() AND rtsp_camera.py's direct os.environ reads see the same
# backend/.env. Called here (not main.py) because this config module is
# the first real import in the app's startup chain (backend/app/main.py
# -> app.core.database -> app.core.config), so this runs before anything
# else in the app could read os.environ for a camera var. Explicit path
# (not the bare load_dotenv() default) so this works regardless of the
# working directory uvicorn/pytest was launched from - it does not
# override a var already set in the real shell environment (override
# defaults to False), so a real, deployed env var still wins over this
# file, exactly as intended.
load_dotenv(_REPO_ROOT / "backend" / ".env")


def _resolve_vehicle_weights() -> str:
    """
    SIH26127 (2026-09-15): VEHICLE_WEIGHTS used to be hardcoded to the
    stock COCO 'yolov8n.pt' (generic, untrained-for-this-task, 80 classes)
    even though a real, custom-trained vehicle detector already existed on
    disk at models/best_vehicle.pt - it was just never wired in anywhere
    (this setting wasn't even read by the caller that actually constructs
    the detector; see backend/app/api/v1/observations.py). Verified by
    loading its checkpoint directly: a genuine YOLOv11n
    (yolo11n.yaml/C3k2/C2PSA architecture) trained for 100 epochs on a real
    'vehicle_detection' dataset, 5 classes (vehicle/truck/bus/motorcycle/
    bicycle), reporting mAP50=0.972 / mAP50-95=0.733 / precision=0.977 /
    recall=0.937 in its own saved train_metrics (from that training run's
    own held-out val split - not independently re-measured against a
    separate benchmark set in this checkout, so treat it as a real,
    reported number rather than an independently-audited one). Prefer it
    the same way _resolve_plate_weights() below prefers a real checkpoint
    over the generic fallback: only fall back to the stock 'yolov8n.pt' if
    best_vehicle.pt isn't actually present on disk (e.g. a fresh checkout
    that hasn't received the out-of-band weight file yet - models/*.pt is
    gitignored, same as the plate detector).
    detection/vehicle_detector.py's class-id filter/label map is NOT
    hardcoded to COCO ids - it's built at runtime from whichever
    checkpoint's own model.names is actually loaded, so it stays correct
    for either this custom 5-class model or the COCO fallback.
    """
    # SIH26127 (2026-09-16) bug found immediately after the .env fix above
    # actually let this function's result take effect for the first time:
    # it returned a path relative to _REPO_ROOT (e.g. "models/best_vehicle.pt"),
    # which ultralytics.YOLO() resolves against the PROCESS'S CURRENT WORKING
    # DIRECTORY, not the repo root - and this project's own documented run
    # command (RUNNING.md) is `cd backend && uvicorn app.main:app`, so that
    # relative path pointed at backend/models/best_vehicle.pt, which doesn't
    # exist -> FileNotFoundError -> vehicle detector permanently UNAVAILABLE
    # (confirmed live on http://localhost:3000/admin's System Health panel
    # and every /process-camera call returning 503 right after the .env fix
    # was deployed). Never hit before because the .env override this same
    # 2026-09-15 fix removed was masking this function's return value
    # entirely - "yolov8n.pt" is a bare model alias ultralytics resolves
    # through its own hub cache regardless of CWD, so the CWD-relative bug
    # was latent the whole time. Return an ABSOLUTE path instead - same fix
    # already applied successfully in demo/visual_pipeline.py's
    # find_plate_weights() (uses PROJECT_ROOT, always absolute) for the
    # exact same class of problem.
    candidates = [
        _REPO_ROOT / "models" / "best_vehicle.pt",
        _REPO_ROOT / "models" / "vehicle_detector.pt",
    ]
    for c in candidates:
        if c.is_file():
            return str(c)
    return "yolov8n.pt"


def _resolve_plate_weights() -> str:
    """
    PLATE_WEIGHTS used to hard-default to 'models/best_plate_detector.pt',
    which is NOT present on disk (it's .gitignore'd, like all *.pt/*.pth
    weights, and was never actually committed/shared to this checkout - see
    docs/CLAUDE_PHASE0_AUDIT.md). That silently broke plate detection: the
    file never existed, so PlateDetector() would fail to construct.

    'models/best.onnx' IS present and IS a real single-class
    'license_plate' detector (verified by loading it with
    ultralytics.YOLO(..., task='detect') - reports names={0: 'license_plate'}).
    ultralytics.YOLO can run inference directly from an .onnx file, so
    prefer whichever weight file actually exists, .pt first (fine-tunable,
    usually the more current artifact) then .onnx, instead of hard-coding a
    path that may not exist in a given checkout.
    """
    # SIH26127 (2026-09-16): same CWD-relative-path bug as
    # _resolve_vehicle_weights() above - return an absolute path so this
    # resolves correctly regardless of whether uvicorn was launched from the
    # repo root or from backend/ (this project's own documented command,
    # see RUNNING.md, launches from backend/). Not currently exercised live
    # (observations.py's plate detector goes through demo/visual_pipeline.py's
    # own find_plate_weights(), which was already absolute-path-safe) but
    # fixed here too so settings.PLATE_WEIGHTS is correct if anything reads
    # it directly.
    candidates = [
        _REPO_ROOT / "models" / "best_plate_detector.pt",
        _REPO_ROOT / "models" / "plate_detector.pt",
        _REPO_ROOT / "detection" / "runs" / "detect" / "plate_train" / "weights" / "best.pt",
        _REPO_ROOT / "models" / "best.onnx",
    ]
    for c in candidates:
        if c.is_file():
            return str(c)
    # nothing found - keep the documented/expected absolute path as the
    # default so the error a caller gets points at the right thing to go
    # add, rather than silently pointing at a made-up relative path.
    return str(_REPO_ROOT / "models" / "best_plate_detector.pt")


class Settings(BaseSettings):
    # extra="ignore": TRACKX_RTSP_<CAM_ID>_* vars live in this same .env
    # file (see network/rtsp_camera.py) but are intentionally NOT modeled
    # as Settings fields here - they're per-camera and read directly via
    # os.environ by rtsp_camera.py, not through this shared Settings
    # object. Without extra="ignore", pydantic-settings' default
    # extra="forbid" makes Settings() raise ValidationError the moment
    # ANY env var it doesn't recognize exists in .env - which is exactly
    # what broke backend startup the first time a real camera was
    # configured (2026-09-14). This does not change validation for any
    # field actually declared below - only tolerates unrelated vars.
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")
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

    # Optional full DB URL; when set it overrides the parts above
    # (read directly by app.core.database before building the engine).
    DATABASE_URL: Optional[str] = None

    # Redis (for queue/caching)
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    # Camera Configuration (from your sheet)
    CAMERA_COUNT: int = 7
    DEFAULT_FRAME_SAMPLE: int = 10  # Process every 10th frame
    MAX_FRAME_PROCESSING: int = 1000  # Max frames per video processing

    # AI Pipeline
    VEHICLE_WEIGHTS: str = _resolve_vehicle_weights()
    PLATE_WEIGHTS: str = _resolve_plate_weights()
    # lprnet_indian.pth is NOT present on this checkout and has no public
    # download (see docs/CLAUDE_PHASE0_AUDIT.md) - LPRNet stays disabled
    # until it's trained on a real Indian-plate OCR dataset or a checkpoint
    # is supplied. recognition/ocr_reader.py falls back to PaddleOCR when
    # this path doesn't exist, rather than faking a loaded model.
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
