# -*- coding: utf-8 -*-
"""
CSV Import functionality for GLR Gestione Locale Radioamatori v4.2a
"""

import os
import csv
import json
import logging
from typing import Dict, Optional, Iterable, Tuple

logger = logging.getLogger("librosoci")

# Target import fields with labels
TARGET_FIELDS = [
    ("matricola", "Matricola"),
    ("nominativo", "Nominativo (callsign)"),
    ("nominativo2", "Nominativo 2"),
    ("nome", "Nome"),
    ("cognome", "Cognome"),
    ("codicefiscale", "Codice fiscale"),
    ("data_nascita", "Data nascita"),
    ("luogo_nascita", "Luogo nascita"),
    ("indirizzo", "Indirizzo"),
    ("cap", "CAP"),
    ("citta", "Città"),
    ("provincia", "Provincia"),
    ("email", "Email"),
    ("telefono", "Telefono"),
    ("note", "Note"),
    ("attivo", "Attivo (Sì/No)"),
    ("voto", "Voto (1/0, Sì/No)"),
    ("familiare", "Familiare (matricola)"),
    ("socio", "Tipo socio (HAM/RCL/THR)"),
    ("q0", "Q0 (causale anno corrente)"),
    ("q1", "Q1 (causale anno -1)"),
    ("q2", "Q2 (causale anno -2)"),
]

# Auto-detection patterns for column mapping
AUTO_GUESS = {
    "matricola": {"matricola", "id", "member_id"},
    "nominativo": {"nominativo", "callsign", "call", "call-sign"},
    "nominativo2": {"nominativo2", "callsign2", "call2", "altro nominativo", "alias"},
    "nome": {"nome", "first", "first_name", "given"},
    "cognome": {"cognome", "last", "last_name", "surname"},
    "codicefiscale": {"cf", "codicefiscale", "fiscal_code", "taxcode"},
    "data_nascita": {"nascita", "data_nascita", "dob", "birth", "birthdate", "data di nascita"},
    "luogo_nascita": {"luogo_nascita", "birthplace", "luogo di nascita"},
    "indirizzo": {"indirizzo", "address", "via"},
    "cap": {"cap", "zip", "zipcode", "postal"},
    "citta": {"citta", "città", "city", "comune"},
    "provincia": {"provincia", "prov", "province", "state"},
    "email": {"email", "mail"},
    "telefono": {"telefono", "tel", "phone", "mobile", "cell", "cellulare"},
    "note": {"note", "notes", "osservazioni"},
    "attivo": {"attivo", "elegibile?", "eligible", "active", "stato", "status"},
    "voto": {"voto", "vote", "voter", "votante"},
    "familiare": {"familiare", "family", "relative", "parentela", "famiglia"},
    "socio": {"socio", "tipo socio", "member_type", "membership", "flag"},
    "q0": {"q0", "quota_corrente", "causale_corrente", "causale0"},
    "q1": {"q1", "quota_anno1", "causale_anno1", "causale1"},
    "q2": {"q2", "quota_anno2", "causale_anno2", "causale2"},
}

# Module configuration
_presets_json = None

def set_presets_path(presets_json: str):
    """Set the path to the presets JSON file."""
    global _presets_json
    _presets_json = presets_json

def sniff_delimiter(path: str) -> str:
    """Auto-detect CSV delimiter (;, , or tab)."""
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            sample = f.read(4096)
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
        return dialect.delimiter or ";"
    except Exception:
        return ";"

def load_presets() -> Dict[str, Dict[str, str]]:
    """Load column mapping presets from JSON."""
    if _presets_json is None:
        logger.warning("Presets path not set")
        return {}
    if not os.path.exists(_presets_json):
        return {}
    try:
        with open(_presets_json, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Failed to load presets: %s", e)
        return {}

def save_presets(data: Dict[str, Dict[str, str]]):
    """Save column mapping presets to JSON."""
    if _presets_json is None:
        logger.warning("Presets path not set")
        return
    os.makedirs(os.path.dirname(_presets_json), exist_ok=True)
    try:
        with open(_presets_json, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("Failed to save presets: %s", e)

def auto_detect_mapping(csv_headers: Iterable[str]) -> Dict[str, Optional[str]]:
    """
    Auto-detect column mapping based on header names.
    
    Args:
        csv_headers: List of CSV column headers
    
    Returns:
        Dictionary mapping target fields to CSV column indices or None
    """
    mapping = {}
    headers_lower = {h.lower().strip() for h in csv_headers}
    
    for target_field, _ in TARGET_FIELDS:
        patterns = AUTO_GUESS.get(target_field, set())
        for pattern in patterns:
            if pattern in headers_lower:
                # Find original header
                for orig_header in csv_headers:
                    if orig_header.lower().strip() == pattern:
                        mapping[target_field] = orig_header
                        break
                break
        if target_field not in mapping:
            mapping[target_field] = None
    
    return mapping

def read_csv_file(path: str, delimiter: str = None, encoding: str = "utf-8-sig") -> Tuple[list, list]:
    """
    Read CSV file and return headers and rows.
    
    Args:
        path: Path to CSV file
        delimiter: CSV delimiter (auto-detect if None)
        encoding: File encoding
    
    Returns:
        Tuple of (headers, rows)
    """
    if delimiter is None:
        delimiter = sniff_delimiter(path)
    
    try:
        with open(path, "r", encoding=encoding) as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            if reader.fieldnames is None:
                return [], []
            headers = list(reader.fieldnames)
            rows = list(reader)
        return headers, rows
    except Exception as e:
        logger.error("Failed to read CSV file: %s", e)
        return [], []

def apply_mapping(rows: list, mapping: Dict[str, Optional[str]]) -> list:
    """
    Apply column mapping to CSV rows.
    
    Args:
        rows: List of CSV row dictionaries
        mapping: Mapping from target fields to CSV column names
    
    Returns:
        List of mapped row dictionaries
    """
    def _normalize_bool_value(val: Optional[str]) -> Optional[str]:
        """Normalize various boolean-like CSV values to '1' or '0'.

        Returns '1' for truthy values, '0' for falsy values, or None for empty/unknown.
        """
        if val is None:
            return None
        v = str(val).strip()
        if v == "":
            return None
        v_lower = v.lower()
        truthy = {"1", "true", "t", "si", "sì", "yes", "y", "v", "vero"}
        falsy = {"0", "false", "f", "no", "n", "non", "falso"}
        # Accept numeric 1/0 possibly with surrounding spaces
        if v_lower in truthy:
            return "1"
        if v_lower in falsy:
            return "0"
        # Try to parse as integer if it's numeric-like
        try:
            iv = int(v)
            if iv == 1:
                return "1"
            if iv == 0:
                return "0"
        except Exception:
            pass
        # Unknown value: return original trimmed string (caller may handle)
        return v

    mapped_rows = []
    for row in rows:
        mapped_row = {}
        for target_field, csv_column in mapping.items():
            if csv_column and csv_column in row:
                value = row[csv_column].strip()
                if target_field in ("attivo", "voto"):
                    mapped_row[target_field] = _normalize_bool_value(value)
                else:
                    mapped_row[target_field] = value if value != "" else None
            else:
                mapped_row[target_field] = None
        mapped_rows.append(mapped_row)
    return mapped_rows
