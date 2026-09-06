#!/usr/bin/env python
"""Test backend configuration loading"""
import sys
sys.path.insert(0, 'backend')

try:
    from app.core.config import settings
    print("Backend config loaded successfully")
    print(f"Environment: {settings.ENVIRONMENT}")
    print(f"Database type: {'PostgreSQL' if not settings.USE_SQLITE else 'SQLite'}")
    print(f"Project: {settings.PROJECT_NAME}")
    print(f"API Version: {settings.VERSION}")
    print("Backend configuration test: PASSED")
except Exception as e:
    print(f"Backend configuration test: FAILED - {e}")
    sys.exit(1)