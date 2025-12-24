# -*- coding: utf-8 -*-
"""
Causali (quotas) management for Libro Soci
"""

import os
import json
import logging
from typing import List, Iterable

logger = logging.getLogger("librosoci")

_causali_json = None

def set_causali_path(causali_json: str):
    """Set the path to the causali codes JSON file."""
    global _causali_json
    _causali_json = causali_json

def load_causali_codes() -> List[str]:
    """Load causali codes from JSON file."""
    if _causali_json is None:
        raise RuntimeError("Causali path not set. Call set_causali_path() first.")
    try:
        if os.path.exists(_causali_json):
            with open(_causali_json, "r", encoding="utf-8") as f:
                data = json.load(f)
                items = [str(x).strip().upper() for x in data if str(x).strip()]
                from utils import CAUSALI_CODE_RE
                items = [x[:3] for x in items if CAUSALI_CODE_RE.match(x[:3])]
                return sorted(set(items))
    except Exception as e:
        logger.warning("load_causali_codes failed: %s", e)
    return []

def save_causali_codes(codes: Iterable[str]):
    """Save causali codes to JSON file."""
    if _causali_json is None:
        raise RuntimeError("Causali path not set. Call set_causali_path() first.")
    from utils import normalize_q, CAUSALI_CODE_RE
    items = []
    for x in codes:
        s = normalize_q(str(x))
        if s and CAUSALI_CODE_RE.match(s):
            items.append(s)
    items = sorted(set(items))
    os.makedirs(os.path.dirname(_causali_json), exist_ok=True)
    with open(_causali_json, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
