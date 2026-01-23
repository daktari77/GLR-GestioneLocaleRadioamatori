import logging
import os
from paths import get_log_dir

def _get_logger(name, filename):
    log_dir = get_log_dir()
    os.makedirs(log_dir, exist_ok=True)
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.FileHandler(os.path.join(log_dir, filename), encoding='utf-8')
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger

def get_bootstrap_logger():
    return _get_logger("bootstrap", "bootstrap.log")

def get_migration_logger():
    return _get_logger("migration", "migration.log")

def get_runtime_logger():
    return _get_logger("runtime", "runtime.log")
