"""
Logging infrastructure for the RAG application.

Provides structured logging with:
- Console output (stdout/stderr)
- File output with rotation
- Standard format across all modules
- Debug-friendly traceback preservation
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler


def setup_logging(log_level: str = "INFO") -> None:
    """
    Initialize application-wide logging with console and file handlers.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Configuration:
        - Console: All logs to stdout with color support
        - File: logs/app.log with 10MB rotation, 5 backups
        - Format: [timestamp] [LEVEL] [module:function:line] message
    """
    
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Remove any existing handlers to avoid duplicates
    root_logger.handlers.clear()
    
    # Define log format
    log_format = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] [%(name)s:%(funcName)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(log_format)
    root_logger.addHandler(console_handler)
    
    # File handler with rotation (10MB max, 5 backups)
    file_handler = RotatingFileHandler(
        filename=log_dir / "app.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(log_format)
    root_logger.addHandler(file_handler)
    
    # Log initialization
    root_logger.info("Logging initialized successfully")
    root_logger.info(f"Log level: {log_level.upper()}")
    root_logger.info(f"Log file: {log_dir / 'app.log'}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.
    
    Args:
        name: Logger name (typically __name__ of the module)
    
    Returns:
        Configured logger instance
    
    Usage:
        logger = get_logger(__name__)
        logger.info("Processing started")
        logger.error("An error occurred", exc_info=True)
    """
    return logging.getLogger(name)
