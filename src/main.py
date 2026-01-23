
# --- First Run Wizard import ---
import tkinter as tk
from pathlib import Path
import json

# ...existing code...

import shutil

# --- Robust environment setup ---
def verify_and_prepare_environment():
    """
    Verifica e crea le cartelle necessarie, controlla la presenza di Thunderbird.
    Logga ogni azione e segnala errori bloccanti.
    """
    required_dirs = [DATA_DIR, BACKUP_DIR, DOCS_BASE, TRASH_DIR, LOG_DIR]
    for d in required_dirs:
        try:
            os.makedirs(d, exist_ok=True)
            if not os.access(d, os.W_OK):
                logger.error(f"Directory non scrivibile: {d}")
                raise PermissionError(f"Directory non scrivibile: {d}")
        except Exception as exc:
            logger.error(f"Errore nella creazione/verifica directory {d}: {exc}")
            raise

    # Verifica presenza Thunderbird
    thunderbird_paths = [
        os.path.join(os.environ.get('ProgramFiles', ''), 'Mozilla Thunderbird', 'thunderbird.exe'),
        os.path.join(os.environ.get('ProgramFiles(x86)', ''), 'Mozilla Thunderbird', 'thunderbird.exe'),
        shutil.which('thunderbird'),
    ]
    thunderbird_found = any(p and os.path.isfile(p) for p in thunderbird_paths)
    if not thunderbird_found:
        logger.warning("Thunderbird non trovato nei percorsi standard. Alcune funzioni potrebbero non essere disponibili.")
    else:
        logger.info("Thunderbird trovato.")

# -*- coding: utf-8 -*-
"""
GLR - Gestione Locale Radioamatori - Main Entry Point
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
    SEC_CATEGORIES, DEFAULT_CONFIG,
    get_backup_dir,
)

# Setup logger
from logger import setup_logger
logger = setup_logger(APP_LOG, APP_VERSION)

# Ensure a stable working directory so legacy relative paths keep working
try:
    os.chdir(BASE_DIR)
except Exception as exc:  # pragma: no cover
    logger.warning("Impossibile impostare la cartella di lavoro su BASE_DIR (%s): %s", BASE_DIR, exc)


# Setup module dependencies
from database import set_db_path, init_db
from causali import set_causali_path
from config_manager import set_config_paths
from utils import set_docs_base
from backup import backup_on_startup

verify_and_prepare_environment()

# Configure all modules
set_db_path(DB_NAME)
set_causali_path(CAUSALI_JSON)
set_config_paths(CONFIG_JSON, SEC_DOCS, DEFAULT_CONFIG, list(SEC_CATEGORIES))
set_docs_base(DOCS_BASE)

logger.debug(f"App Version: {APP_VERSION}")
logger.debug(f"Build ID: {BUILD_ID} ({BUILD_DATE})")
logger.debug(f"Base Directory: {BASE_DIR}")

# Check if this is first run (database doesn't exist)
is_first_run = not os.path.exists(DB_NAME)

if is_first_run:
    logger.info("Primo avvio rilevato - avvio wizard di configurazione...")
    from tkinter_wizard import run_wizard
    
    # Create a mutable flag to track wizard completion
    wizard_done = [False]
    
    def on_wizard_complete(state):
        wizard_done[0] = True
        logger.info("Wizard completato con successo")
    
    # Run wizard with callback
    run_wizard(mode="FIRST_RUN", on_complete=on_wizard_complete)
    
    # Wait for wizard completion or timeout (30 seconds)
    import time
    start_time = time.time()
    while not wizard_done[0] and (time.time() - start_time) < 30:
        time.sleep(0.1)
    
    if not wizard_done[0]:
        logger.warning("Wizard timeout - chiusura automatica")
    
    # Reload config after wizard
    try:
        with open(CONFIG_JSON, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except:
        pass

# Parallelize database initialization and backup
import threading

def _init_db_thread():
    init_db()
    logger.debug("Database initialized")

def _backup_thread():
    backup_on_startup(DB_NAME, get_backup_dir())

db_thread = threading.Thread(target=_init_db_thread, name="InitDB")
backup_thread = threading.Thread(target=_backup_thread, name="BackupStartup")
db_thread.start()
backup_thread.start()
db_thread.join()
backup_thread.join()

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

    # ImportWizard: bind Ctrl+I to open import wizard (use app.root, not app)
    try:
        from import_wizard import ImportWizard
        ImportWizard.bind_import_shortcut(app.root, lambda: ImportWizard(app.root))
        logger.info("Scorciatoia Ctrl+I per import wizard attivata.")
    except Exception as e:
        logger.warning(f"Impossibile attivare scorciatoia import wizard: {e}")
