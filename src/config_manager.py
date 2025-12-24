# -*- coding: utf-8 -*-
"""
Configuration management for GLR Gestione Locale Radioamatori
"""

import os
import json
import shutil
import logging
from typing import Dict, Optional

logger = logging.getLogger("librosoci")

_config_json = None
_sec_docs = None
_default_config = None
_sec_categories = None

def set_config_paths(config_json: str, sec_docs: str, default_config: Dict, sec_categories: list):
    """Set configuration paths and defaults."""
    global _config_json, _sec_docs, _default_config, _sec_categories
    _config_json = config_json
    _sec_docs = sec_docs
    _default_config = default_config
    _sec_categories = sec_categories

def load_config() -> dict:
    """Load configuration from JSON file."""
    if _config_json is None:
        raise RuntimeError("Config paths not set. Call set_config_paths() first.")
    if not os.path.exists(_config_json):
        return _default_config.copy() if _default_config else {}
    try:
        with open(_config_json, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {**(_default_config or {}), **data}
    except Exception as e:
        logger.warning("Failed to load config: %s", e)
        return _default_config.copy() if _default_config else {}

def save_config(cfg: dict):
    """Save configuration to JSON file."""
    if _config_json is None:
        raise RuntimeError("Config paths not set. Call set_config_paths() first.")
    os.makedirs(os.path.dirname(_config_json), exist_ok=True)
    with open(_config_json, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def ensure_sec_category_dirs():
    """Ensure all section category directories exist."""
    if _sec_docs is None or _sec_categories is None:
        raise RuntimeError("Config paths not set. Call set_config_paths() first.")
    for cat in _sec_categories:
        os.makedirs(os.path.join(_sec_docs, cat), exist_ok=True)

def copy_into_section(category: str, source: str) -> str:
    """Copy a file into the section documents folder."""
    if _sec_docs is None:
        raise RuntimeError("Config paths not set. Call set_config_paths() first.")
    ensure_sec_category_dirs()
    dst_dir = os.path.join(_sec_docs, category)
    os.makedirs(dst_dir, exist_ok=True)
    base = os.path.basename(source)
    name, ext = os.path.splitext(base)
    dest = os.path.join(dst_dir, base)
    i = 1
    while os.path.exists(dest):
        dest = os.path.join(dst_dir, f"{name}_{i}{ext}")
        i += 1
    shutil.copy2(source, dest)
    return dest
