# -*- coding: utf-8 -*-
"""Helpers for importing inventory (magazzino) data from CSV or Excel sources."""

from __future__ import annotations

import csv
import logging
from pathlib import Path
import re
from typing import Iterable, List, Sequence, Tuple

logger = logging.getLogger("librosoci")

INVENTORY_FIELDS = [
    {"key": "numero_inventario", "label": "Numero inventario", "required": True},
    # "marca" is stored as NOT NULL in DB, but sources may not have it.
    # We allow importing without mapping it and let the UI provide a default.
    {"key": "marca", "label": "Marca", "required": False},
    {"key": "modello", "label": "Modello", "required": False},
    {"key": "descrizione", "label": "Descrizione", "required": False},
    {"key": "note", "label": "Note", "required": False},
    {"key": "quantita", "label": "Qtà", "required": False},
    {"key": "ubicazione", "label": "Ubicazione", "required": False},
    {"key": "matricola", "label": "Matricola", "required": False},
    {"key": "doc_fisc_prov", "label": "Doc fisc/prov.", "required": False},
    {"key": "valore_acq_eur", "label": "Valore acq €", "required": False},
    {"key": "scheda_tecnica", "label": "Scheda tecnica", "required": False},
    {"key": "provenienza", "label": "Provenienza", "required": False},
    {"key": "altre_notizie", "label": "Altre notizie", "required": False},
]

AUTO_GUESS = {
    "numero_inventario": {
        "numero",
        "inventario",
        "numero inventario",
        "n. inv",
        "n inv",
        "serial",
        "asset",
        "inventory",
    },
    "marca": {"marca", "brand", "manufacturer", "vendor", "produttore"},
    "modello": {"modello", "model", "product", "sku"},
    "descrizione": {
        "descrizione",
        "descrizione breve",
        "descrizione articoli",
        "descr",
        "description",
        "details",
        "articolo",
        "articoli",
    },
    "note": {
        "note",
        "notes",
        "commenti",
        "comments",
        "osservazioni",
        "altre notizie",
        "altre note",
        "annotazioni",
    },
    "quantita": {"qtà", "qta", "quantita", "quantità", "qty", "quant."},
    "ubicazione": {"ubicazione", "posizione", "location", "scaffale"},
    "matricola": {"matricola", "serial", "s/n", "sn"},
    "doc_fisc_prov": {"doc fisc/prov", "doc fisc/prov.", "doc fisc", "documento"},
    "valore_acq_eur": {"valore acq €", "valore acq", "valore", "costo", "importo"},
    "scheda_tecnica": {"scheda tecnica", "datasheet", "scheda"},
    "provenienza": {"provenienza", "origine", "fornitore"},
    "altre_notizie": {"altre notizie", "altre note", "note extra", "extra"},
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
            dialect = csv.Sniffer().sniff(sample, delimiters=";,.\t|")
            return dialect.delimiter or ";"
    except Exception as exc:
        logger.debug("Delimiter sniff failed for %s: %s", path, exc)
        return ";"


_HEADER_HINTS = {
    "n inv",
    "n. inv",
    "numero inventario",
    "inventario",
    "qtà",
    "qta",
    "descrizione",
    "descrizione articoli",
    "ubicazione",
    "matricola",
    "altre notizie",
    "note",
}


def _canon_header_cell(value: str | None) -> str:
    text = (value or "").strip().lower()
    if not text:
        return ""
    # normalize punctuation/spacing so that "N. INV" and "N INV" match.
    text = re.sub(r"[\s\u00a0]+", " ", text)
    text = re.sub(r"[^\w\sàèéìòù°.]", "", text)
    text = text.replace(".", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _score_header_row(cells: Sequence[str]) -> int:
    score = 0
    for cell in cells:
        canon = _canon_header_cell(cell)
        if not canon:
            continue
        if canon in _HEADER_HINTS:
            score += 3
            continue
        # partial matches for typical column names
        for hint in _HEADER_HINTS:
            if hint and hint in canon:
                score += 1
                break
    return score


def _detect_header_index(rows: Sequence[Sequence[str]]) -> int | None:
    best_idx: int | None = None
    best_score = 0
    # Look at the first N lines; inventory exports are usually small.
    max_scan = min(len(rows), 50)
    for idx in range(max_scan):
        cells = rows[idx]
        if not cells:
            continue
        # Ignore rows that are mostly empty.
        non_empty = sum(1 for c in cells if (c or "").strip())
        if non_empty < 2:
            continue
        score = _score_header_row(cells)
        if score > best_score:
            best_score = score
            best_idx = idx
    # Require at least a couple of hints to avoid picking a title/preamble row.
    if best_score >= 4:
        return best_idx
    return None


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
            reader = csv.reader(handle, delimiter=delim)
            raw_rows = list(reader)

        if not raw_rows:
            raise InventoryImportError("Il file CSV è vuoto.")

        header_idx = _detect_header_index(raw_rows)
        if header_idx is None:
            # Fall back to the first row as header (previous behavior)
            header_idx = 0

        raw_headers = raw_rows[header_idx]
        if not raw_headers or not any((h or "").strip() for h in raw_headers):
            raise InventoryImportError("Il file CSV non contiene intestazioni valide.")

        headers = _ensure_headers(raw_headers)
        rows: list[dict] = []
        for raw_row in raw_rows[header_idx + 1 :]:
            if not raw_row or not any((c or "").strip() for c in raw_row):
                continue
            row: dict[str, str | None] = {}
            for idx, header in enumerate(headers):
                value = raw_row[idx] if idx < len(raw_row) else None
                row[header] = _normalize_value(value)
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
    # Use canonicalized lookup so we can match e.g. "N. INV" and "N INV".
    header_lookup = {_canon_header_cell(header): header for header in headers}
    for field in INVENTORY_FIELDS:
        targets = AUTO_GUESS.get(field["key"], set())
        for candidate in targets:
            canon = _canon_header_cell(candidate)
            if canon in header_lookup:
                mapping[field["key"]] = header_lookup[canon]
                break
        # Helpful fallback for common exports: map "note" to location if notes are missing.
        if field["key"] == "note" and mapping.get("note") is None:
            for alt in ("ubicazione", "posizione", "location"):
                canon_alt = _canon_header_cell(alt)
                if canon_alt in header_lookup:
                    mapping["note"] = header_lookup[canon_alt]
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
