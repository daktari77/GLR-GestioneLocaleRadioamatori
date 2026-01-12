# -*- coding: utf-8 -*-
"""
CD Meetings management for GLR Gestione Locale Radioamatori
Handles registration of CD meetings and related documents (verbali in .doc/.pdf format)
"""

import sqlite3
import logging
import os
import json
from typing import List, Tuple, Optional, Dict
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("librosoci")

_UNSET = object()


def _odg_text_to_json(odg_text: str | None) -> str | None:
    if not odg_text:
        return None
    lines = [ln.strip() for ln in odg_text.splitlines() if ln.strip()]
    if not lines:
        return None

    items: list[dict] = []
    for ln in lines:
        raw = ln.strip()
        up = raw.upper()
        requires = False
        for prefix in ("[D]", "[DEL]", "DEL:", "D:", "!"):
            if up.startswith(prefix):
                requires = True
                raw = raw[len(prefix):].strip()
                break
        if not raw:
            continue
        items.append({"title": raw, "requires_delibera": requires})
    if not items:
        return None
    payload = {
        "version": 1,
        "items": items,
    }
    return json.dumps(payload, ensure_ascii=False)


def _odg_json_to_text(odg_json: str | None) -> str | None:
    if not odg_json:
        return None
    try:
        payload = json.loads(odg_json)
        items = payload.get("items")
        if not isinstance(items, list):
            return None
        titles: list[str] = []
        for item in items:
            if isinstance(item, dict):
                title = str(item.get("title") or "").strip()
                if title:
                    if bool(item.get("requires_delibera")):
                        titles.append(f"[D] {title}")
                    else:
                        titles.append(title)
        return "\n".join(titles) if titles else None
    except Exception:
        return None


def _archive_cd_meeting_verbale(meeting_id: int, source_path: str) -> str:
    """Copy verbale into managed filesystem folder and return new absolute path."""
    from file_archiver import archive_file

    target_dir = Path("data/documents/cd/riunioni") / f"{int(meeting_id):04d}" / "verbale"
    dest_path, _stored = archive_file(source_path=source_path, target_dir=target_dir)
    return dest_path


def _maybe_archive_if_external(meeting_id: int, verbale_path: str | None) -> str | None:
    if not verbale_path:
        return None
    try:
        if not os.path.exists(verbale_path):
            return verbale_path
    except Exception:
        return verbale_path

    target_root = (Path("data/documents/cd/riunioni") / f"{int(meeting_id):04d}").resolve()
    try:
        current = Path(verbale_path).resolve()
        if str(current).lower().startswith(str(target_root).lower()):
            return verbale_path
    except Exception:
        pass
    return _archive_cd_meeting_verbale(meeting_id, verbale_path)


def _resolve_section_document_path(row: dict) -> str | None:
    """Resolve a section_documents row into an absolute path (portable-safe)."""
    try:
        from config import SEC_DOCS

        root = Path(SEC_DOCS).resolve()
    except Exception:
        root = Path("data/section_docs").resolve()

    rel = str(row.get("relative_path") or "").strip()
    abs_db = str(row.get("percorso") or "").strip()

    # Prefer relative path under SEC_DOCS to avoid stale absolute dev paths.
    if rel:
        try:
            rel_path = Path(rel)
            candidate = rel_path if rel_path.is_absolute() else (root / rel_path)
            return str(candidate.resolve())
        except Exception:
            pass

    return abs_db or None


def resolve_meeting_verbale_path(meeting: dict) -> str | None:
    """Return an absolute path to the meeting verbale, preferring section docs linkage."""
    if not isinstance(meeting, dict):
        return None

    sid = meeting.get("verbale_section_doc_id")
    try:
        section_id = int(sid) if sid is not None else None
    except Exception:
        section_id = None

    if section_id:
        try:
            from database import get_section_document_by_id

            row = get_section_document_by_id(section_id)
        except Exception:
            row = None
        if isinstance(row, dict):
            resolved = _resolve_section_document_path(row)
            if resolved:
                return resolved

    legacy = str(meeting.get("verbale_path") or "").strip()
    return legacy or None

def get_all_meetings() -> List[Dict]:
    """
    Get all CD meetings ordered by date (most recent first).
    
    Returns:
        List of meeting dictionaries with keys: id, numero_cd, data, titolo, verbale_path, created_at
    """
    from database import fetch_all
    try:
        sql = (
            "SELECT id, numero_cd, data, titolo, mandato_id, meta_json, verbale_section_doc_id, verbale_path, created_at "
            "FROM cd_riunioni ORDER BY data DESC"
        )
        rows = fetch_all(sql)
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error("Failed to get meetings: %s", e)
        return []

def get_meeting_by_id(meeting_id: int) -> Optional[Dict]:
    """
    Get a specific meeting by ID.
    
    Args:
        meeting_id: Meeting ID
    
    Returns:
        Meeting dictionary or None if not found
    """
    from database import fetch_one
    try:
        sql = """
            SELECT id, numero_cd, data, titolo, mandato_id, note, tipo_riunione, odg_json, meta_json, presenze_json, verbale_section_doc_id, verbale_path, created_at
            FROM cd_riunioni
            WHERE id=?
        """
        row = fetch_one(sql, (meeting_id,))
        if not row:
            return None
        meeting = dict(row)
        odg_text = (meeting.get("note") or "").strip() if meeting.get("note") else ""
        if not odg_text:
            odg_text = _odg_json_to_text(meeting.get("odg_json")) or ""
        meeting["odg"] = odg_text
        return meeting
    except Exception as e:
        logger.error("Failed to get meeting %s: %s", meeting_id, e)
        return None


def add_meeting(
    data: str,
    numero_cd: str | None = None,
    titolo: str | None = None,
    odg: str | None = None,
    mandato_id: int | None = None,
    tipo_riunione: str | None = None,
    verbale_path: str | None = None,
    verbale_section_doc_id: int | None = None,
    meta_json: str | dict | None = None,
    presenze_json: str | dict | None = None,
) -> int:
    """
    Add a new CD meeting.
    
    Args:
        data: Meeting date (ISO format YYYY-MM-DD)
        numero_cd: Optional CD meeting number (two digits)
        titolo: Optional meeting title
        odg: Optional meeting agenda (order of the day)
        verbale_path: Optional path to verbale document (.doc or .pdf)
    
    Returns:
        ID of inserted meeting or -1 on error
    """
    from database import get_connection
    from utils import now_iso
    
    try:
        original_verbale = verbale_path
        odg_json = _odg_text_to_json(odg)
        if isinstance(meta_json, dict):
            meta_json = json.dumps(meta_json, ensure_ascii=False)
        if isinstance(presenze_json, dict):
            presenze_json = json.dumps(presenze_json, ensure_ascii=False)
        # Insert first to obtain meeting_id; we may import/link the file afterward.
        with get_connection() as conn:
            cursor = conn.cursor()
            sql = """
                INSERT INTO cd_riunioni (numero_cd, data, titolo, mandato_id, note, tipo_riunione, meta_json, odg_json, presenze_json, verbale_section_doc_id, verbale_path, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            cursor.execute(
                sql,
                (
                    numero_cd,
                    data,
                    titolo,
                    int(mandato_id) if mandato_id else None,
                    odg,
                    tipo_riunione,
                    meta_json,
                    odg_json,
                    presenze_json,
                    int(verbale_section_doc_id) if verbale_section_doc_id else None,
                    None,
                    now_iso(),
                ),
            )
            meeting_id = cursor.lastrowid
            conn.commit()
        
        if meeting_id is None:
            logger.error("Failed to get meeting ID after insert")
            return -1
        
        if meeting_id is None:
            logger.error("Failed to get meeting ID after insert")
            return -1

        # Canonical storage: section documents.
        # If caller provided a legacy path, import it into section docs and link it.
        if original_verbale and not verbale_section_doc_id:
            try:
                from section_documents import add_section_document
                from database import get_section_document_by_relative_path

                dest_abs = add_section_document(original_verbale, "Verbali CD")
                row = get_section_document_by_relative_path(dest_abs)
                if row and row.get("id") is not None:
                    with get_connection() as conn:
                        conn.execute(
                            "UPDATE cd_riunioni SET verbale_section_doc_id = ?, verbale_path = NULL WHERE id = ?",
                            (int(row["id"]), int(meeting_id)),
                        )
            except Exception as exc:
                logger.warning("Impossibile importare/linkare verbale CD in documenti sezione: %s", exc)

        logger.info(f"Added meeting on {data} (ID: {meeting_id})")
        return meeting_id
    except Exception as e:
        logger.error("Failed to add meeting: %s", e)
        return -1


def update_meeting(
    meeting_id: int,
    numero_cd: str | None = None,
    data: str | None = None,
    titolo: str | None = None,
    odg: str | None = None,
    mandato_id: int | None | object = _UNSET,
    tipo_riunione: str | None = None,
    verbale_path: str | None = None,
    verbale_section_doc_id: int | None = None,
    meta_json: str | dict | None = None,
    presenze_json: str | dict | None = None,
) -> bool:
    """
    Update an existing meeting.
    
    Args:
        meeting_id: Meeting ID
        numero_cd: New CD meeting number (optional)
        data: New meeting date (optional)
        titolo: New meeting title (optional)
        odg: New meeting agenda (optional)
        verbale_path: New verbale path (optional)
    
    Returns:
        True if update was successful, False otherwise
    """
    from database import get_connection
    
    try:
        updates = []
        values = []
        
        if numero_cd is not None:
            updates.append("numero_cd=?")
            values.append(numero_cd)
        if data is not None:
            updates.append("data=?")
            values.append(data)
        if titolo is not None:
            updates.append("titolo=?")
            values.append(titolo)
        if mandato_id is not _UNSET:
            updates.append("mandato_id=?")
            values.append(int(mandato_id) if mandato_id else None)
        if tipo_riunione is not None:
            updates.append("tipo_riunione=?")
            values.append(tipo_riunione)
        if odg is not None:
            updates.append("note=?")
            values.append(odg)
            updates.append("odg_json=?")
            values.append(_odg_text_to_json(odg))
        if meta_json is not None:
            updates.append("meta_json=?")
            if isinstance(meta_json, dict):
                values.append(json.dumps(meta_json, ensure_ascii=False))
            else:
                values.append(meta_json)
        if presenze_json is not None:
            updates.append("presenze_json=?")
            if isinstance(presenze_json, dict):
                values.append(json.dumps(presenze_json, ensure_ascii=False))
            else:
                values.append(presenze_json)
        if verbale_section_doc_id is not None:
            updates.append("verbale_section_doc_id=?")
            values.append(int(verbale_section_doc_id) if verbale_section_doc_id else None)
            # Clear legacy path when linking
            updates.append("verbale_path=NULL")
        elif verbale_path is not None:
            # Legacy: if a path is provided, import into section docs and link.
            try:
                from section_documents import add_section_document
                from database import get_section_document_by_relative_path

                dest_abs = add_section_document(verbale_path, "Verbali CD")
                row = get_section_document_by_relative_path(dest_abs)
                if row and row.get("id") is not None:
                    updates.append("verbale_section_doc_id=?")
                    values.append(int(row["id"]))
                    updates.append("verbale_path=NULL")
                else:
                    verbale_path = _maybe_archive_if_external(int(meeting_id), verbale_path)
                    updates.append("verbale_path=?")
                    values.append(verbale_path)
            except Exception:
                verbale_path = _maybe_archive_if_external(int(meeting_id), verbale_path)
                updates.append("verbale_path=?")
                values.append(verbale_path)
        
        if not updates:
            logger.warning("No fields to update for meeting %s", meeting_id)
            return False
        
        values.append(meeting_id)
        sql = f"UPDATE cd_riunioni SET {', '.join(updates)} WHERE id=?"
        
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, values)
            conn.commit()
        
        logger.info(f"Updated meeting {meeting_id}")
        return True
    except Exception as e:
        logger.error("Failed to update meeting %s: %s", meeting_id, e)
        return False

def delete_meeting(meeting_id: int, delete_verbale: bool = False) -> bool:
    """
    Delete a meeting (and optionally its verbale file).
    
    Args:
        meeting_id: Meeting ID
        delete_verbale: If True, delete the associated verbale file
    
    Returns:
        True if deletion was successful, False otherwise
    """
    from database import exec_query, fetch_one
    
    try:
        # Get verbale path/link before deletion
        if delete_verbale:
            meeting = get_meeting_by_id(meeting_id)
            if meeting:
                try:
                    sid = meeting.get("verbale_section_doc_id")
                    section_id = int(sid) if sid is not None else None
                except Exception:
                    section_id = None

                if section_id:
                    try:
                        from database import get_section_document_by_id
                        from section_documents import delete_section_document

                        row = get_section_document_by_id(section_id)
                        if row:
                            abs_path = _resolve_section_document_path(row)
                            if abs_path:
                                delete_section_document(abs_path)
                    except Exception as e:
                        logger.warning(f"Could not delete linked section verbale: {e}")
                else:
                    verbale_path = str(meeting.get('verbale_path') or "").strip()
                    if verbale_path:
                        try:
                            if os.path.exists(verbale_path):
                                os.remove(verbale_path)
                                logger.info(f"Deleted verbale file: {verbale_path}")
                        except Exception as e:
                            logger.warning(f"Could not delete verbale file: {e}")
        
        # Delete from database
        exec_query("DELETE FROM cd_riunioni WHERE id=?", (meeting_id,))
        logger.info(f"Deleted meeting {meeting_id}")
        return True
    except Exception as e:
        logger.error("Failed to delete meeting %s: %s", meeting_id, e)
        return False

def validate_verbale_file(file_path: str) -> Tuple[bool, str]:
    """
    Validate that a file is a valid verbale document (.doc or .pdf).
    
    Args:
        file_path: Path to file
    
    Returns:
        Tuple of (is_valid, message)
    """
    if not os.path.exists(file_path):
        return False, "File non trovato"
    
    valid_extensions = {'.doc', '.docx', '.pdf'}
    _, ext = os.path.splitext(file_path)
    
    if ext.lower() not in valid_extensions:
        return False, f"Formato non supportato: {ext}. Usa .doc, .docx o .pdf"
    
    return True, "OK"

def get_verbale_info(meeting_id: int) -> Optional[Dict]:
    """
    Get information about a meeting's verbale.
    
    Args:
        meeting_id: Meeting ID
    
    Returns:
        Dictionary with verbale info or None if no verbale
    """
    meeting = get_meeting_by_id(meeting_id)
    verbale_path = resolve_meeting_verbale_path(meeting or {})
    if not meeting or not verbale_path:
        return None

    try:
        if os.path.exists(verbale_path):
            size = os.path.getsize(verbale_path)
            mtime = os.path.getmtime(verbale_path)
            return {
                'path': verbale_path,
                'name': os.path.basename(verbale_path),
                'size': size,
                'size_formatted': f"{size / 1024:.1f} KB" if size < 1024*1024 else f"{size / (1024*1024):.1f} MB",
                'modified': datetime.fromtimestamp(mtime).isoformat()
            }
        else:
            logger.warning(f"Verbale file not found: {verbale_path}")
            return None
    except Exception as e:
        logger.error(f"Error getting verbale info for meeting {meeting_id}: {e}")
        return None
