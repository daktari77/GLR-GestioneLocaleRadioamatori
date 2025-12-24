# -*- coding: utf-8 -*-
"""Data access helpers for ponti (radio repeaters)."""

from __future__ import annotations

import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from database import (
    add_calendar_event,
    delete_calendar_event,
    fetch_all,
    fetch_one,
    get_connection,
    update_calendar_event,
)
from utils import ddmmyyyy_to_iso, now_iso
from file_archiver import unique_hex_filename

DEFAULT_REMINDER_DAYS = 60
EVENT_TYPE = "ponte_autorizzazione"
DEFAULT_PONTI_DOCS_BASE = Path("data/documents/ponti")
PONTI_DOCS_BASE = DEFAULT_PONTI_DOCS_BASE
_SAFE_TOKEN_RE = re.compile(r"[^A-Z0-9]+")

__all__ = [
    "create_ponte",
    "update_ponte",
    "delete_ponte",
    "get_ponte",
    "list_ponti",
    "list_authorizations",
    "save_authorization",
    "delete_authorization",
    "set_ponti_docs_base",
    "add_ponte_document",
    "list_ponte_documents",
    "update_ponte_document",
    "delete_ponte_document",
]


def set_ponti_docs_base(base_path: str | Path):
    """Override the base folder used to store ponti documents."""
    global PONTI_DOCS_BASE
    PONTI_DOCS_BASE = Path(base_path)


def _normalize_text(value: Any | None) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _require_non_empty(value: Any, field_name: str) -> str:
    text = _normalize_text(value)
    if not text:
        raise ValueError(f"Il campo '{field_name}' è obbligatorio")
    return text


def _sanitize_token(value: str | None, fallback: str) -> str:
    text = (value or "").strip().upper()
    text = _SAFE_TOKEN_RE.sub("_", text).strip("_")
    return text or fallback


def _ensure_docs_root() -> Path:
    base = PONTI_DOCS_BASE or DEFAULT_PONTI_DOCS_BASE
    base.mkdir(parents=True, exist_ok=True)
    return base


def _resolve_ponte_dir(ponte: dict) -> Path:
    base = _ensure_docs_root()
    label = ponte.get("nome") or ponte.get("nominativo") or ponte.get("qth") or f"PONTE_{ponte['id']}"
    token = _sanitize_token(label, fallback=f"PONTE_{ponte['id']}")
    folder_name = f"{int(ponte['id']):04d}_{token}"
    target = base / folder_name
    target.mkdir(parents=True, exist_ok=True)
    return target


def _copy_into_managed_dir(ponte: dict, source_path: str, tipo: str | None) -> str:
    source = Path(source_path).expanduser()
    if not source.exists():
        raise FileNotFoundError(f"File non trovato: {source}")
    target_dir = _resolve_ponte_dir(ponte)
    tipo_label = _sanitize_token(tipo, "DOCUMENTI") if tipo else "DOCUMENTI"
    final_dir = target_dir / tipo_label
    final_dir.mkdir(parents=True, exist_ok=True)
    filename = unique_hex_filename(final_dir, source.suffix.lower())
    destination = final_dir / filename
    shutil.copy2(source, destination)
    return str(destination)


def _maybe_remove_file(path: str | None):
    if not path:
        return
    try:
        target = Path(path)
        if target.exists() and target.is_file():
            target.unlink()
    except Exception:
        pass


def _normalize_date(value: Any | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        iso = ddmmyyyy_to_iso(text)
    except ValueError as exc:  # Re-raise with context
        raise ValueError(f"Data non valida ('{value}')") from exc
    if iso is None:
        return None
    return iso


def _date_to_ts(date_iso: str) -> str:
    try:
        datetime.strptime(date_iso, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"Data non valida ('{date_iso}')") from exc
    return f"{date_iso}T09:00:00"


def _fetch_ponte_identity(ponte_id: int) -> dict:
    row = fetch_one("SELECT id, nome, nominativo, qth FROM ponti WHERE id = ?", (ponte_id,))
    if row is None:
        raise ValueError(f"Ponte #{ponte_id} inesistente")
    return dict(row)


def _row_to_dict(row) -> dict:
    return dict(row) if row is not None else {}


def create_ponte(*, nome: str, nominativo: str | None = None, localita: str | None = None,
                 stato: str | None = None, note: str | None = None) -> int:
    """Create a new ponte record and return its ID."""
    nome_norm = _require_non_empty(nome, "nome")
    now = now_iso()
    payload = (
        nome_norm,
        _normalize_text(nominativo),
        _normalize_text(localita),
        _normalize_text(note),
        (_normalize_text(stato) or "ATTIVO").upper(),
        now,
        now,
    )
    sql = (
        "INSERT INTO ponti (nome, nominativo, qth, note_tecniche, stato_corrente, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)"
    )
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, payload)
        ponte_id = cur.lastrowid
    if ponte_id is None:
        raise RuntimeError("Impossibile determinare l'ID del nuovo ponte")
    return int(ponte_id)


def update_ponte(ponte_id: int, *, nome: str | None = None, nominativo: str | None = None,
                 localita: str | None = None, stato: str | None = None, note: str | None = None) -> bool:
    """Update ponte fields. Returns True if a row was updated."""
    fields: list[str] = []
    params: list[Any] = []
    if nome is not None:
        fields.append("nome = ?")
        params.append(_require_non_empty(nome, "nome"))
    if nominativo is not None:
        fields.append("nominativo = ?")
        params.append(_normalize_text(nominativo))
    if localita is not None:
        fields.append("qth = ?")
        params.append(_normalize_text(localita))
    if note is not None:
        fields.append("note_tecniche = ?")
        params.append(_normalize_text(note))
    if stato is not None:
        stato_val = _normalize_text(stato)
        fields.append("stato_corrente = ?")
        params.append((stato_val or "ATTIVO").upper())
    if not fields:
        return False
    fields.append("updated_at = ?")
    params.append(now_iso())
    params.append(ponte_id)
    sql = f"UPDATE ponti SET {', '.join(fields)} WHERE id = ?"
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur.rowcount > 0


def delete_ponte(ponte_id: int) -> bool:
    """Delete a ponte and let cascading rules remove related rows."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM ponti WHERE id = ?", (ponte_id,))
        return cur.rowcount > 0


def get_ponte(ponte_id: int) -> dict | None:
    row = fetch_one("SELECT * FROM ponti WHERE id = ?", (ponte_id,))
    if row is None:
        return None
    data = dict(row)
    latest = fetch_one(
        "SELECT data_scadenza FROM ponti_authorizations WHERE ponte_id = ? AND data_scadenza IS NOT NULL "
        "ORDER BY data_scadenza DESC LIMIT 1",
        (ponte_id,),
    )
    data["next_scadenza"] = latest["data_scadenza"] if latest else None
    return data


def list_ponti(*, stato: str | None = None) -> list[dict]:
    """Return all ponti optionally filtered by status."""
    sql = (
        "SELECT p.*, ("
        "SELECT data_scadenza FROM ponti_authorizations pa WHERE pa.ponte_id = p.id AND pa.data_scadenza IS NOT NULL "
        "ORDER BY pa.data_scadenza DESC LIMIT 1"
        ") AS next_scadenza FROM ponti p"
    )
    params: list[Any] = []
    if stato:
        sql += " WHERE p.stato_corrente = ?"
        params.append(stato.upper())
    sql += " ORDER BY p.nome COLLATE NOCASE"
    rows = fetch_all(sql, tuple(params)) if params else fetch_all(sql)
    return [dict(row) for row in rows]


def list_authorizations(ponte_id: int) -> list[dict]:
    rows = fetch_all(
        """
        SELECT pa.*, ce.reminder_days
          FROM ponti_authorizations pa
          LEFT JOIN calendar_events ce ON ce.id = pa.calendar_event_id
         WHERE pa.ponte_id = ?
         ORDER BY COALESCE(pa.data_scadenza, '') DESC, pa.id DESC
        """,
        (ponte_id,),
    )
    return [dict(r) for r in rows]


def delete_authorization(authorization_id: int) -> bool:
    row = fetch_one(
        "SELECT calendar_event_id FROM ponti_authorizations WHERE id = ?",
        (authorization_id,),
    )
    if row is None:
        return False
    row_dict = dict(row)
    event_id = row_dict.get("calendar_event_id")
    if event_id:
        delete_calendar_event(event_id)
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM ponti_authorizations WHERE id = ?", (authorization_id,))
        return cur.rowcount > 0


def _sync_authorization_event(
    *,
    ponte: dict,
    authorization_id: int,
    scadenza_iso: str | None,
    existing_event_id: int | None,
    promoter_note: str | None,
    reminder_days: int,
    enable_reminder: bool,
) -> int | None:
    if not enable_reminder or not scadenza_iso:
        if existing_event_id:
            delete_calendar_event(existing_event_id)
        return None
    titolo = ponte.get("nome") or ponte.get("nominativo") or f"Ponte #{ponte['id']}"
    event_title = f"Scadenza autorizzazione {titolo}"
    descrizione = promoter_note or "Promemoria scadenza autorizzazione ponte"
    start_ts = _date_to_ts(scadenza_iso)
    if existing_event_id:
        update_calendar_event(
            existing_event_id,
            titolo=event_title,
            descrizione=descrizione,
            start_ts=start_ts,
            reminder_days=reminder_days,
        )
        return existing_event_id
    return add_calendar_event(
        tipo=EVENT_TYPE,
        titolo=event_title,
        descrizione=descrizione,
        start_ts=start_ts,
        reminder_days=reminder_days,
        origin=f"ponte:{ponte['id']}#autorizzazione:{authorization_id}",
    )


def save_authorization(
    ponte_id: int,
    *,
    tipo: str,
    ente: str | None = None,
    numero: str | None = None,
    data_rilascio: str | None = None,
    data_scadenza: str | None = None,
    documento_path: str | None = None,
    note: str | None = None,
    authorization_id: int | None = None,
    reminder_days: int = DEFAULT_REMINDER_DAYS,
    enable_reminder: bool = True,
) -> int:
    """Insert or update an authorization and keep reminder in sync."""
    ponte = _fetch_ponte_identity(ponte_id)
    tipo_norm = _require_non_empty(tipo, "tipo")
    rilascio_iso = _normalize_date(data_rilascio)
    scadenza_iso = _normalize_date(data_scadenza)
    payload = (
        tipo_norm,
        _normalize_text(ente),
        _normalize_text(numero),
        rilascio_iso,
        scadenza_iso,
        _normalize_text(documento_path),
        _normalize_text(note),
    )
    if authorization_id is not None:
        existing = fetch_one(
            "SELECT id, calendar_event_id FROM ponti_authorizations WHERE id = ? AND ponte_id = ?",
            (authorization_id, ponte_id),
        )
        if existing is None:
            raise ValueError("Autorizzazione non trovata per il ponte indicato")
        with get_connection() as conn:
            conn.execute(
                """UPDATE ponti_authorizations
                    SET tipo = ?, ente = ?, numero = ?, data_rilascio = ?, data_scadenza = ?,
                        documento_path = ?, note = ?
                  WHERE id = ? AND ponte_id = ?""",
                payload + (authorization_id, ponte_id),
            )
        event_id = existing["calendar_event_id"]
    else:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO ponti_authorizations
                    (ponte_id, tipo, ente, numero, data_rilascio, data_scadenza, documento_path, note, calendar_event_id)
                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)""",
                (ponte_id,) + payload,
            )
            authorization_id = cur.lastrowid
        if authorization_id is None:
            raise RuntimeError("Impossibile determinare l'ID dell'autorizzazione")
        event_id = None
    new_event_id = _sync_authorization_event(
        ponte=ponte,
        authorization_id=int(authorization_id),
        scadenza_iso=scadenza_iso,
        existing_event_id=event_id,
        promoter_note=payload[-1],
        reminder_days=reminder_days,
        enable_reminder=enable_reminder,
    )
    with get_connection() as conn:
        conn.execute(
            "UPDATE ponti_authorizations SET calendar_event_id = ? WHERE id = ?",
            (new_event_id, authorization_id),
        )
    return int(authorization_id)


def add_ponte_document(ponte_id: int, document_path: str, *, tipo: str | None = None,
                       note: str | None = None) -> int:
    """Attach a document to a ponte copying it inside the managed archive."""
    ponte = _fetch_ponte_identity(ponte_id)
    source = _require_non_empty(document_path, "documento")
    managed_path = _copy_into_managed_dir(ponte, source, tipo)
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO ponti_documents (ponte_id, document_path, tipo, note) VALUES (?, ?, ?, ?)",
            (ponte_id, managed_path, _normalize_text(tipo), _normalize_text(note)),
        )
        doc_id = cur.lastrowid
    if doc_id is None:
        raise RuntimeError("Impossibile determinare l'ID del documento")
    return int(doc_id)


def list_ponte_documents(ponte_id: int) -> list[dict]:
    rows = fetch_all(
        "SELECT * FROM ponti_documents WHERE ponte_id = ? ORDER BY id DESC",
        (ponte_id,),
    )
    return [dict(r) for r in rows]


def update_ponte_document(document_id: int, *, tipo: str | None = None, note: str | None = None) -> bool:
    fields: list[str] = []
    params: list[Any] = []
    if tipo is not None:
        fields.append("tipo = ?")
        params.append(_normalize_text(tipo))
    if note is not None:
        fields.append("note = ?")
        params.append(_normalize_text(note))
    if not fields:
        return False
    params.append(document_id)
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE ponti_documents SET {', '.join(fields)} WHERE id = ?", params)
        return cur.rowcount > 0


def delete_ponte_document(document_id: int) -> bool:
    row = fetch_one("SELECT document_path FROM ponti_documents WHERE id = ?", (document_id,))
    if row is None:
        return False
    row_dict = dict(row)
    _maybe_remove_file(row_dict.get("document_path"))
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM ponti_documents WHERE id = ?", (document_id,))
        return cur.rowcount > 0