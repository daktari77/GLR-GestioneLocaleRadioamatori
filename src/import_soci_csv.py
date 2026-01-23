# -*- coding: utf-8 -*-
"""
Import soci da CSV per wizard primo avvio GLR
"""
from typing import Dict, Any
from csv_import import read_csv_file, auto_detect_mapping, apply_mapping

def import_soci_csv(path: str) -> Dict[str, Any]:
    """
    Importa soci da file CSV, auto-mappa colonne e restituisce dict con soci, contatori e errori.
    Args:
        path: percorso file CSV
    Returns:
        dict: {
            'imported': int,
            'errors': int,
            'duplicates': int,
            'soci': list[dict]
        }
    """
    headers, rows = read_csv_file(path)
    if not headers or not rows:
        return {'imported': 0, 'errors': 1, 'duplicates': 0, 'soci': []}
    mapping = auto_detect_mapping(headers)
    soci = apply_mapping(rows, mapping)
    imported = len(soci)
    # Duplicati: matricola ripetuta
    seen = set()
    duplicates = 0
    soci_unique = []
    for s in soci:
        m = s.get('matricola')
        if m and m in seen:
            duplicates += 1
            continue
        if m:
            seen.add(m)
        soci_unique.append(s)
    return {
        'imported': len(soci_unique),
        'errors': 0,
        'duplicates': duplicates,
        'soci': soci_unique
    }
