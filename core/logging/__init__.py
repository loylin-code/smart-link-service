"""
Core logging module - structured JSON logging with dual output
"""
import logging
import sys
import os
from logging.handlers import RotatingFileHandler
from typing import Optional

from core.config import settings
from core.logging.formatter import StructuredFormatter


def get_logger(
    name: str,
    file_name: Optional[str] = None,
    level: Optional[str] = None
) -> logging.Logger:
    """
    Get configured logger with structured JSON format.
    
    Args:
        name: Logger name (e.g., 'gateway.middleware.logging')
        file_name: Optional separate file name (e.g., 'audit.log')
        level: Optional log level override
    
    Returns:
        Configured logger instance with stdout and file handlers
    """
    
    logger = logging.getLogger(name)
    
    # Set level
    log_level = level or getattr(settings, 'LOG_LEVEL', 'INFO')
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # Clear existing handlers (avoid duplicate logs)
    logger.handlers.clear()
    
    # Create formatter
    formatter = StructuredFormatter()
    
    # Stdout handler (for container log collection)
    if getattr(settings, 'LOG_STDOUT', True):
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setFormatter(formatter)
        stdout_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        logger.addHandler(stdout_handler)
    
    # File handler (for local debugging and audit)
    if getattr(settings, 'LOG_FILE', True):
        log_dir = getattr(settings, 'LOG_DIR', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        file = file_name or 'app.log'
        file_path = os.path.join(log_dir, file)
        
        max_bytes = getattr(settings, 'LOG_MAX_SIZE', 10 * 1024 * 1024)  # 10MB
        backup_count = getattr(settings, 'LOG_BACKUP_COUNT', 5)
        
        file_handler = RotatingFileHandler(
            file_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        logger.addHandler(file_handler)
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    return logger