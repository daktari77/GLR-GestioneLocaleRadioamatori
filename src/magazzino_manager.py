# -*- coding: utf-8 -*-
"""Inventory (magazzino) management helpers."""

from __future__ import annotations

from typing import Any

from database import fetch_all, fetch_one, get_connection
from utils import ddmmyyyy_to_iso, now_iso, today_iso

__all__ = [
    "create_item",
    "update_item",
    "delete_item",
    "list_items",
    "get_item",
    "list_loans",
    "create_loan",
    "register_return",
    "get_active_loan",
]


def _normalize_text(value: Any | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _require(value: Any, field_name: str) -> str:
    text = _normalize_text(value)
    if not text:
        raise ValueError(f"Il campo '{field_name}' è obbligatorio")
    return text


def _normalize_date(value: Any | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    iso = ddmmyyyy_to_iso(text)
    return iso


def _ensure_item(item_id: int) -> dict:
    row = fetch_one("SELECT * FROM magazzino_items WHERE id = ?", (item_id,))
    if row is None:
        raise ValueError(f"Oggetto magazzino #{item_id} inesistente")
    return dict(row)


def create_item(*, marca: str, modello: str | None = None, descrizione: str | None = None,
                numero_inventario: str, note: str | None = None) -> int:
    """Create a new inventory item and return its ID."""
    timestamp = now_iso()
    payload = (
        _require(numero_inventario, "numero inventario"),
        _require(marca, "marca"),
        _normalize_text(modello),
        _normalize_text(descrizione),
        _normalize_text(note),
        timestamp,
        timestamp,
    )
    sql = (
        "INSERT INTO magazzino_items (numero_inventario, marca, modello, descrizione, note, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)"
    )
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, payload)
        new_id = cur.lastrowid
    if new_id is None:
        raise RuntimeError("Impossibile determinare l'ID del nuovo oggetto")
    return int(new_id)


def update_item(item_id: int, *, marca: str | None = None, modello: str | None = None,
                descrizione: str | None = None, numero_inventario: str | None = None,
                note: str | None = None) -> bool:
    """Update an inventory item."""
    fields: list[str] = []
    params: list[Any] = []
    if numero_inventario is not None:
        fields.append("numero_inventario = ?")
        params.append(_require(numero_inventario, "numero inventario"))
    if marca is not None:
        fields.append("marca = ?")
        params.append(_require(marca, "marca"))
    if modello is not None:
        fields.append("modello = ?")
        params.append(_normalize_text(modello))
    if descrizione is not None:
        fields.append("descrizione = ?")
        params.append(_normalize_text(descrizione))
    if note is not None:
        fields.append("note = ?")
        params.append(_normalize_text(note))
    if not fields:
        return False
    fields.append("updated_at = ?")
    params.append(now_iso())
    params.append(item_id)
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE magazzino_items SET {', '.join(fields)} WHERE id = ?", params)
        return cur.rowcount > 0


def delete_item(item_id: int) -> bool:
    """Delete an inventory item (loans are removed via cascade)."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM magazzino_items WHERE id = ?", (item_id,))
        return cur.rowcount > 0


def list_items() -> list[dict]:
    """List all inventory items with active loan summary."""
    sql = """
    SELECT i.*,
           al.id AS active_loan_id,
           al.socio_id AS active_socio_id,
           al.data_prestito AS active_data_prestito,
           s.nome AS active_socio_nome,
           s.cognome AS active_socio_cognome,
           s.matricola AS active_socio_matricola
      FROM magazzino_items i
      LEFT JOIN (
           SELECT * FROM (
               SELECT ml.*, ROW_NUMBER() OVER (PARTITION BY ml.item_id ORDER BY ml.data_prestito ASC, ml.id ASC) AS rn
                 FROM magazzino_loans ml
                WHERE ml.data_reso IS NULL
           ) WHERE rn = 1
      ) al ON al.item_id = i.id
      LEFT JOIN soci s ON s.id = al.socio_id
     ORDER BY i.numero_inventario COLLATE NOCASE, i.id ASC
    """
    rows = fetch_all(sql)
    return [dict(row) for row in rows]


def get_item(item_id: int) -> dict | None:
    row = fetch_one("SELECT * FROM magazzino_items WHERE id = ?", (item_id,))
    if row is None:
        return None
    data = dict(row)
    data["active_loan"] = get_active_loan(item_id)
    return data


def list_loans(item_id: int) -> list[dict]:
    sql = """
    SELECT ml.*, s.nome, s.cognome, s.matricola
      FROM magazzino_loans ml
      LEFT JOIN soci s ON s.id = ml.socio_id
     WHERE ml.item_id = ?
     ORDER BY ml.data_prestito DESC, ml.id DESC
    """
    rows = fetch_all(sql, (item_id,))
    return [dict(row) for row in rows]


def get_active_loan(item_id: int) -> dict | None:
    row = fetch_one(
        "SELECT ml.*, s.nome, s.cognome, s.matricola"
        "  FROM magazzino_loans ml"
        "  LEFT JOIN soci s ON s.id = ml.socio_id"
        " WHERE ml.item_id = ? AND ml.data_reso IS NULL"
        " ORDER BY ml.data_prestito ASC, ml.id ASC"
        " LIMIT 1",
        (item_id,),
    )
    return dict(row) if row else None


def _ensure_no_active_loan(item_id: int):
    if get_active_loan(item_id):
        raise ValueError("L'oggetto risulta già in prestito")


def create_loan(item_id: int, *, socio_id: int, data_prestito: str | None = None,
                note: str | None = None) -> int:
    """Register a new loan for an item."""
    _ensure_item(item_id)
    if socio_id is None:
        raise ValueError("Selezionare un socio valido")
    _ensure_no_active_loan(item_id)
    iso_date = _normalize_date(data_prestito) or today_iso()
    timestamp = now_iso()
    payload = (
        item_id,
        int(socio_id),
        iso_date,
        _normalize_text(note),
        timestamp,
        timestamp,
    )
    sql = (
        "INSERT INTO magazzino_loans (item_id, socio_id, data_prestito, note, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)"
    )
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, payload)
        new_id = cur.lastrowid
    if new_id is None:
        raise RuntimeError("Impossibile determinare l'ID del prestito")
    return int(new_id)


def register_return(loan_id: int, *, data_reso: str | None = None) -> bool:
    """Mark a loan as returned."""
    row = fetch_one("SELECT id, data_reso FROM magazzino_loans WHERE id = ?", (loan_id,))
    if row is None:
        raise ValueError("Prestito inesistente")
    if row["data_reso"]:
        return False
    iso_date = _normalize_date(data_reso) or today_iso()
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE magazzino_loans SET data_reso = ?, updated_at = ? WHERE id = ?",
            (iso_date, now_iso(), loan_id),
        )
        return cur.rowcount > 0
