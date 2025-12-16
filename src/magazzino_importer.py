# -*- coding: utf-8 -*-
"""Helpers for importing inventory (magazzino) data from CSV or Excel sources."""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

logger = logging.getLogger("librosoci")

INVENTORY_FIELDS = [
    {"key": "numero_inventario", "label": "Numero inventario", "required": True},
    {"key": "marca", "label": "Marca", "required": True},
    {"key": "modello", "label": "Modello", "required": False},
    {"key": "descrizione", "label": "Descrizione", "required": False},
    {"key": "note", "label": "Note", "required": False},
]

AUTO_GUESS = {
    "numero_inventario": {"numero", "inventario", "serial", "asset", "inventory"},
    "marca": {"marca", "brand", "manufacturer", "vendor"},
    "modello": {"modello", "model", "product", "sku"},
    "descrizione": {"descrizione", "descrizione breve", "descr", "description", "details"},
    "note": {"note", "notes", "commenti", "comments", "osservazioni"},
}

SUPPORTED_FORMATS = {
    ".csv": "csv",
    ".txt": "csv",
    ".tsv": "csv",
    ".xlsx": "excel",
    ".xlsm": "excel",
}


class InventoryImportError(Exception):
    """Raised when the inventory import process cannot continue."""


def detect_format(path: str) -> str | None:
    """Return the logical format for the given path or None if unsupported."""
    ext = Path(path).suffix.lower()
    return SUPPORTED_FORMATS.get(ext)


def sniff_delimiter(path: str) -> str:
    """Detect CSV delimiter from file contents."""
    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            sample = handle.read(4096)
            handle.seek(0)
            if not sample:
                return ";"
            dialect = csv.Sniffer().sniff(sample, delimiters=";,	|")
            return dialect.delimiter or ";"
    except Exception as exc:
        logger.debug("Delimiter sniff failed for %s: %s", path, exc)
        return ";"


def _normalize_value(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_inventory_code(value: str | None) -> str | None:
    """Normalize an inventory code for duplicate detection (trim + uppercase)."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text.upper()


def _ensure_headers(headers: Sequence[str]) -> List[str]:
    """Ensure headers are non-empty and unique."""
    normalized: List[str] = []
    counters: dict[str, int] = {}
    for idx, header in enumerate(headers):
        base = (header or "").strip() or f"Colonna {idx + 1}"
        count = counters.get(base, 0)
        if count:
            name = f"{base}_{count + 1}"
        else:
            name = base
        counters[base] = count + 1
        normalized.append(name)
    return normalized


def _read_csv_file(path: str, delimiter: str | None = None) -> Tuple[List[str], List[dict]]:
    delim = delimiter or sniff_delimiter(path)
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, delimiter=delim)
            headers = reader.fieldnames or []
            if not headers:
                raise InventoryImportError("Il file CSV non contiene intestazioni valide.")
            headers = _ensure_headers(headers)
            rows: list[dict] = []
            for raw_row in reader:
                row = {header: _normalize_value(raw_row.get(header)) for header in headers}
                if any(row.values()):
                    rows.append(row)
        return headers, rows
    except InventoryImportError:
        raise
    except Exception as exc:
        raise InventoryImportError(f"Errore lettura CSV: {exc}") from exc


def _read_excel_file(path: str) -> Tuple[List[str], List[dict]]:
    try:
        import openpyxl
    except ImportError as exc:
        raise InventoryImportError(
            "Per importare file Excel (.xlsx) è necessario installare 'openpyxl'."
        ) from exc

    try:
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
        sheet = workbook.active
        if sheet is None:
            raise InventoryImportError("Il file Excel non ha un foglio attivo selezionato.")
        headers: list[str] | None = None
        rows: list[dict] = []
        for raw_row in sheet.iter_rows(values_only=True):
            values = [_normalize_value(cell) for cell in raw_row]
            if headers is None:
                if not any(values):
                    continue
                headers = _ensure_headers([val or "" for val in values])
                continue
            if not headers:
                continue
            row: dict[str, str | None] = {}
            empty = True
            for idx, header in enumerate(headers):
                value = values[idx] if idx < len(values) else None
                norm = _normalize_value(value)
                if norm is not None:
                    empty = False
                row[header] = norm
            if not empty:
                rows.append(row)
        if headers is None:
            raise InventoryImportError("Impossibile individuare l'intestazione del foglio Excel.")
        return headers, rows
    except InventoryImportError:
        raise
    except Exception as exc:
        raise InventoryImportError(f"Errore lettura Excel: {exc}") from exc


def read_source_file(path: str, *, delimiter: str | None = None) -> Tuple[List[str], List[dict]]:
    """Return headers and rows extracted from a CSV or Excel file."""
    fmt = detect_format(path)
    if fmt == "csv":
        return _read_csv_file(path, delimiter)
    if fmt == "excel":
        return _read_excel_file(path)
    raise InventoryImportError("Formato file non supportato. Usa CSV oppure Excel (.xlsx).")


def auto_detect_mapping(headers: Iterable[str]) -> dict[str, str | None]:
    mapping: dict[str, str | None] = {field["key"]: None for field in INVENTORY_FIELDS}
    header_lookup = {header.lower().strip(): header for header in headers}
    for field in INVENTORY_FIELDS:
        targets = AUTO_GUESS.get(field["key"], set())
        for candidate in targets:
            if candidate in header_lookup:
                mapping[field["key"]] = header_lookup[candidate]
                break
    return mapping


def apply_mapping(rows: List[dict], mapping: dict[str, str | None]) -> List[dict[str, str | None]]:
    """Return normalized dictionaries with keys from INVENTORY_FIELDS."""
    mapped_rows: list[dict[str, str | None]] = []
    for source in rows:
        mapped: dict[str, str | None] = {}
        for field in INVENTORY_FIELDS:
            key = field["key"]
            header = mapping.get(key)
            mapped[key] = _normalize_value(source.get(header)) if header else None
        mapped_rows.append(mapped)
    return mapped_rows


__all__ = [
    "INVENTORY_FIELDS",
    "InventoryImportError",
    "apply_mapping",
    "auto_detect_mapping",
    "detect_format",
    "normalize_inventory_code",
    "read_source_file",
]
