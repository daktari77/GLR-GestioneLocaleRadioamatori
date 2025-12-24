# -*- coding: utf-8 -*-
"""
Logger configuration for GLR Gestione Locale Radioamatori
"""

import os
import logging
from logging.handlers import RotatingFileHandler

def setup_logger(app_log_path: str, app_version: str) -> logging.Logger:
    """
    Configure and return the application logger.
    
    Args:
        app_log_path: Path to the log file
        app_version: Application version string
    
    Returns:
        Configured logger instance
    """
    os.makedirs(os.path.dirname(app_log_path), exist_ok=True)
    
    logger = logging.getLogger("librosoci")
    logger.setLevel(logging.DEBUG)
    
    # File handler
    file_handler = RotatingFileHandler(
        app_log_path, maxBytes=1_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(
        logging.Formatter("%(levelname)s: %(message)s")
    )
    
    # Reset handlers to avoid duplicates on reload
    logger.handlers.clear()
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    logger.debug("=== Avvio applicazione ===")
    logger.debug("Versione applicazione: %s", app_version)
    
    return logger
