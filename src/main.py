# -*- coding: utf-8 -*-
"""
GLR - Gestione Locale Radioamatori v4.2a - Main Entry Point
Modular architecture with separated concerns
"""

# Initialize all module configurations before importing the main App class
import os
import sys

# Import configuration
from config import (
    APP_NAME, APP_VERSION, AUTHOR, BUILD_ID, BUILD_DATE,
    BASE_DIR, DATA_DIR, BACKUP_DIR, DOCS_BASE, TRASH_DIR, SEC_DOCS, LOG_DIR,
    DB_NAME, CONFIG_JSON, PRESETS_JSON, CAUSALI_JSON, APP_LOG,
    SEC_CATEGORIES, DEFAULT_CONFIG
)

# Setup logger
from logger import setup_logger
logger = setup_logger(APP_LOG, APP_VERSION)

# Setup module dependencies
from database import set_db_path, init_db
from causali import set_causali_path
from config_manager import set_config_paths
from utils import set_docs_base
from backup import backup_on_startup

# Configure all modules
set_db_path(DB_NAME)
set_causali_path(CAUSALI_JSON)
set_config_paths(CONFIG_JSON, SEC_DOCS, DEFAULT_CONFIG, list(SEC_CATEGORIES))
set_docs_base(DOCS_BASE)

logger.debug(f"App Version: {APP_VERSION}")
logger.debug(f"Build ID: {BUILD_ID} ({BUILD_DATE})")
logger.debug(f"Base Directory: {BASE_DIR}")

# Initialize database
init_db()
logger.debug("Database initialized")

# Perform startup backup
backup_on_startup(DB_NAME, BACKUP_DIR)

# Import the main App class and loading splash
from v4_ui.main_window import App
from v4_ui.loading_window import LoadingWindow
from startup_checks import collect_startup_issues

if __name__ == "__main__":
    logger.info("Starting application...")
    loading = LoadingWindow(
        app_name=APP_NAME,
        version=APP_VERSION,
        author=AUTHOR,
        min_duration=5.0,
        activity_logger=logger,
    )
    try:
        loading.show()
        loading.set_status("Verifica ambiente...")
        startup_issues = collect_startup_issues()
    finally:
        loading.close()
    app = App(startup_issues=startup_issues)
