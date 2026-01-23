import os
import json
from paths import get_data_dir, get_db_path, get_sentinel_path, get_app_state_path

class AppState:
    FIRST_INSTALL = "FIRST_INSTALL"
    PARTIAL_INSTALL = "PARTIAL_INSTALL"
    UPGRADE = "UPGRADE"
    NORMAL_RUN = "NORMAL_RUN"
    INCOMPATIBLE = "INCOMPATIBLE"

def read_schema_version(db_path):
    import sqlite3
    if not os.path.exists(db_path):
        return None
    try:
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute("PRAGMA user_version;")
            row = cur.fetchone()
            return row[0] if row else None
    except Exception:
        return None

def detect_state(expected_schema_version):
    data_dir = get_data_dir()
    db_path = get_db_path()
    sentinel = get_sentinel_path()
    app_state_path = get_app_state_path()

    # Stato: FIRST_INSTALL
    if not os.path.exists(data_dir) or not os.path.exists(db_path) or not os.path.exists(sentinel):
        return AppState.FIRST_INSTALL

    # Stato: PARTIAL_INSTALL
    if not os.path.exists(db_path) or not os.path.exists(sentinel):
        return AppState.PARTIAL_INSTALL

    # Stato: INCOMPATIBLE
    schema_version = read_schema_version(db_path)
    if schema_version is None:
        return AppState.PARTIAL_INSTALL
    if schema_version > expected_schema_version:
        return AppState.INCOMPATIBLE

    # Stato: UPGRADE
    if schema_version < expected_schema_version:
        return AppState.UPGRADE

    # Stato: NORMAL_RUN
    return AppState.NORMAL_RUN

def read_app_state():
    path = get_app_state_path()
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def write_app_state(state_dict):
    path = get_app_state_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state_dict, f, indent=2)
