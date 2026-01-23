import os
import sys

def get_base_data_dir():
    # Usa %APPDATA%/GLR o ~/.glr
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        return os.path.join(base, "GLR")
    else:
        return os.path.join(os.path.expanduser("~"), ".glr")

def get_data_dir():
    return get_base_data_dir()

def get_log_dir():
    return os.path.join(get_data_dir(), "logs")

def get_backup_dir():
    return os.path.join(get_data_dir(), "backup")

def get_db_path():
    return os.path.join(get_data_dir(), "glr.db")

def get_config_path():
    return os.path.join(get_data_dir(), "config.json")

def get_app_state_path():
    return os.path.join(get_data_dir(), "app_state.json")

def get_sentinel_path():
    return os.path.join(get_data_dir(), ".initialized")
