# -*- coding: utf-8 -*-
"""
Configuration and constants for Libro Soci
"""

import os
import sys
from datetime import datetime

# --------------------------
# Versione / Build
# --------------------------
APP_NAME = "Libro Soci"
APP_VERSION = "0.4.2b"
__version__ = APP_VERSION
AUTHOR = "Michele Martino - IU2GLR"

def _calc_build_from_file() -> tuple[str, str]:
    """Calculate build ID and date from file modification time."""
    try:
        path = os.path.abspath(__file__)
        ts = os.path.getmtime(path)
        dt = datetime.fromtimestamp(ts)
        return dt.strftime("%Y%m%d.%H%M"), dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        now = datetime.now()
        return now.strftime("%Y%m%d.%H%M"), now.strftime("%Y-%m-%d %H:%M")

BUILD_ID, BUILD_DATE = _calc_build_from_file()

# --------------------------
# Base directories
# --------------------------
def _base_dir():
    """Get the base directory for the application."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return os.path.dirname(sys.executable)
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        return os.getcwd()

BASE_DIR = _base_dir()
DATA_DIR = os.path.join(BASE_DIR, "data")
BACKUP_DIR = os.path.join(BASE_DIR, "backup")
DOCS_BASE = os.path.join(DATA_DIR, "docs")
TRASH_DIR = os.path.join(DATA_DIR, ".trash")
SEC_DOCS = os.path.join(DATA_DIR, "section_docs")
LOG_DIR = os.path.join(DATA_DIR, "logs")

# Create directories if they don't exist
for p in (DATA_DIR, BACKUP_DIR, DOCS_BASE, TRASH_DIR, SEC_DOCS, LOG_DIR):
    os.makedirs(p, exist_ok=True)

# --------------------------
# File paths
# --------------------------
DB_NAME = os.path.join(DATA_DIR, "soci.db")
DB_BACKUP = os.path.join(BACKUP_DIR, "soci_backup.db")
CONFIG_JSON = os.path.join(DATA_DIR, "section_config.json")
PRESETS_JSON = os.path.join(DATA_DIR, "import_presets.json")
CAUSALI_JSON = os.path.join(DATA_DIR, "causali_codes.json")
APP_LOG = os.path.join(LOG_DIR, "app.log")
THUNDERBIRD_EXE = os.path.join(DATA_DIR, "tools", "thunderbird", "thunderbird.exe")

# --------------------------
# Section categories
# --------------------------
SEC_CATEGORIES = ("Statuto", "Regolamento", "Verbali", "Delibere", "Altro")

# --------------------------
# Regular expressions
# --------------------------
CAUSALI_CODE_RE = __import__("re").compile(r"^[A-Z0-9]{2,3}$")

# --------------------------
# Default configuration
# --------------------------
DEFAULT_CONFIG = {
    "nome_sezione": "",
    "codice_sezione": "",
    "sede_operativa": "",
    "sede_legale": "",
    "indirizzo_postale": "",
    "telefono": "",
    "email": "",
    "sito_web": "",
    "coordinate_bancarie": "",
    "recapiti": "",
    "cd_componenti": "",
    "privacy_validita_anni": 2,
    "thunderbird_path": "",

    # Cartella backup locale (globale). Se vuoto usa BACKUP_DIR (default).
    "backup_dir": "",

    # Repository secondario per backup (es. cartella su drive cloud)
    # Se valorizzato, i backup creati localmente verranno copiati anche qui.
    "backup_repo_dir": "",
}


def _resolve_dir(value: str) -> str:
    """Expand/normalize a directory path."""
    return os.path.abspath(os.path.expanduser(os.path.expandvars(value)))


def get_backup_dir() -> str:
    """Return the configured local backup directory.

    Reads config key 'backup_dir' (Preferences) if available, otherwise returns
    the default BACKUP_DIR.
    """
    configured: str = ""
    try:
        from config_manager import load_config

        cfg = load_config()
        if isinstance(cfg, dict):
            configured = (cfg.get("backup_dir") or "").strip()
    except Exception:
        configured = ""

    path = _resolve_dir(configured) if configured else BACKUP_DIR
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        # Fallback to default if the configured path is invalid/unwritable.
        path = BACKUP_DIR
        os.makedirs(path, exist_ok=True)
    return path
