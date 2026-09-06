"""Enterprise logging configuration with rotation."""

import logging
import logging.handlers
import json
from datetime import datetime
from pathlib import Path
import os

# Ensure logs directory exists
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)

class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging."""
    
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, 'user_id'):
            log_data["user_id"] = record.user_id
        if hasattr(record, 'request_id'):
            log_data["request_id"] = record.request_id
        if hasattr(record, 'duration_ms'):
            log_data["duration_ms"] = record.duration_ms
            
        return json.dumps(log_data)


def setup_logging(app_name="trackx", log_level=None):
    """Setup enterprise logging with file rotation."""
    
    if log_level is None:
        log_level = os.getenv("LOG_LEVEL", "INFO")
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler (JSON output)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_formatter = JSONFormatter()
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler with rotation (JSON output)
    file_path = LOGS_DIR / f"{app_name}.log"
    file_handler = logging.handlers.RotatingFileHandler(
        file_path,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=10  # Keep 10 rotated files
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(console_formatter)
    root_logger.addHandler(file_handler)
    
    # Error file handler (all errors to separate file)
    error_file_path = LOGS_DIR / f"{app_name}_errors.log"
    error_handler = logging.handlers.RotatingFileHandler(
        error_file_path,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(console_formatter)
    root_logger.addHandler(error_handler)
    
    return root_logger


def get_logger(name):
    """Get a logger instance."""
    return logging.getLogger(name)
