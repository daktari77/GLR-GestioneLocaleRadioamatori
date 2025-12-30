# -*- coding: utf-8 -*-
"""
CD Delibere (Resolutions) management for GLR Gestione Locale Radioamatori
Handles registration of CD meeting resolutions with full tracking
"""

import sqlite3
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from pathlib import Path
import os

logger = logging.getLogger("librosoci")


def _get_cd_delibere_date_select(conn: sqlite3.Connection) -> str:
    """Return a SQL expression selecting the delibera date as `data_votazione`.

    Older databases may miss `data_votazione` or use a legacy `data` column.
    """
    try:
        cols = {str(r["name"]).lower() for r in conn.execute("PRAGMA table_info(cd_delibere)")}
    except Exception:
        cols = set()
    if "data_votazione" in cols:
        return "d.data_votazione AS data_votazione"
    if "data" in cols:
        return "d.data AS data_votazione"
    return "NULL AS data_votazione"


def _archive_cd_delibera_attachment(delibera_id: int, source_path: str) -> str:
    from file_archiver import archive_file

    target_dir = Path("data/documents/cd/delibere") / f"{int(delibera_id):04d}" / "allegati"
    dest_path, _stored = archive_file(source_path=source_path, target_dir=target_dir)
    return dest_path


def _maybe_archive_delibera_attachment(delibera_id: int, allegato_path: str | None) -> str | None:
    if not allegato_path:
        return None
    try:
        if not os.path.exists(allegato_path):
            return allegato_path
    except Exception:
        return allegato_path

    target_root = (Path("data/documents/cd/delibere") / f"{int(delibera_id):04d}").resolve()
    try:
        current = Path(allegato_path).resolve()
        if str(current).lower().startswith(str(target_root).lower()):
            return allegato_path
    except Exception:
        pass
    return _archive_cd_delibera_attachment(delibera_id, allegato_path)

def get_all_delibere(meeting_id: int = None) -> List[Dict]:
    """
    Get all delibere, optionally filtered by meeting.
    
    Args:
        meeting_id: Optional meeting ID to filter by
    
    Returns:
        List of delibere dictionaries
    """
    from database import fetch_all, get_connection
    try:
        # Check if table exists
        try:
            with get_connection() as conn:
                conn.execute("SELECT 1 FROM cd_delibere LIMIT 1")
        except sqlite3.OperationalError:
            # Table doesn't exist, return empty list
            logger.warning("Table cd_delibere doesn't exist yet")
            return []
        
        with get_connection() as conn:
            date_select = _get_cd_delibere_date_select(conn)

        if meeting_id:
            sql = f"""
                SELECT d.id, d.cd_id, d.numero, d.oggetto, d.esito, {date_select},
                       d.favorevoli, d.contrari, d.astenuti, d.allegato_path, d.note, d.created_at
                FROM cd_delibere d
                WHERE d.cd_id = ?
                ORDER BY d.numero DESC
            """
            rows = fetch_all(sql, (meeting_id,))
        else:
            sql = f"""
                SELECT d.id, d.cd_id, d.numero, d.oggetto, d.esito, {date_select},
                       d.favorevoli, d.contrari, d.astenuti, d.allegato_path, d.note, d.created_at
                FROM cd_delibere d
                ORDER BY d.cd_id DESC, d.numero DESC
            """
            rows = fetch_all(sql)
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error("Failed to get delibere: %s", e)
        return []

def get_delibera_by_id(delibera_id: int) -> Optional[Dict]:
    """
    Get a specific delibera by ID.
    
    Args:
        delibera_id: Delibera ID
    
    Returns:
        Delibera dictionary or None if not found
    """
    from database import fetch_one, get_connection
    try:
        with get_connection() as conn:
            date_select = _get_cd_delibere_date_select(conn).replace("d.", "")
        sql = f"""
            SELECT id, cd_id, numero, oggetto, esito, {date_select},
                   favorevoli, contrari, astenuti, allegato_path, note, created_at
            FROM cd_delibere WHERE id = ?
        """
        row = fetch_one(sql, (delibera_id,))
        return dict(row) if row else None
    except Exception as e:
        logger.error("Failed to get delibera %s: %s", delibera_id, e)
        return None

def add_delibera(cd_id: int, numero: str, oggetto: str, esito: str = "APPROVATA",
                 data_votazione: str = None, favorevoli: int = None, contrari: int = None,
                 astenuti: int = None, allegato_path: str = None, note: str = None) -> int:
    """
    Add a new delibera to a CD meeting.
    
    Args:
        cd_id: CD meeting ID
        numero: Resolution number (e.g., "1/2025")
        oggetto: Resolution subject
        esito: Outcome (APPROVATA, RESPINTA, RINVIATA) - default APPROVATA
        data_votazione: Voting date (YYYY-MM-DD)
        favorevoli: Number of votes in favor
        contrari: Number of votes against
        astenuti: Number of abstentions
        allegato_path: Optional path to attached document
        note: Optional notes
    
    Returns:
        ID of inserted delibera or -1 on error
    """
    from database import exec_query, fetch_one
    from utils import now_iso
    
    # Validate esito
    valid_esiti = {'APPROVATA', 'RESPINTA', 'RINVIATA'}
    if esito not in valid_esiti:
        logger.error("Invalid esito: %s", esito)
        return -1
    
    try:
        original_attachment = allegato_path
        sql = """
            INSERT INTO cd_delibere 
            (cd_id, numero, oggetto, esito, data_votazione, favorevoli, contrari, astenuti, allegato_path, note, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        exec_query(sql, (cd_id, numero, oggetto, esito, data_votazione, favorevoli, contrari, astenuti, None, note, now_iso()))
        
        result = fetch_one("SELECT last_insert_rowid() as id")
        delibera_id = result['id'] if result else -1

        if delibera_id != -1 and original_attachment:
            try:
                archived = _archive_cd_delibera_attachment(int(delibera_id), original_attachment)
                exec_query("UPDATE cd_delibere SET allegato_path = ? WHERE id = ?", (archived, int(delibera_id)))
            except Exception as exc:
                logger.warning("Impossibile archiviare allegato delibera: %s", exc)
        
        logger.info(f"Added delibera {numero} to meeting {cd_id} (ID: {delibera_id})")
        return delibera_id
    except Exception as e:
        logger.error("Failed to add delibera: %s", e)
        return -1

def update_delibera(delibera_id: int, numero: str = None, oggetto: str = None, esito: str = None,
                    data_votazione: str = None, favorevoli: int = None, contrari: int = None,
                    astenuti: int = None, allegato_path: str = None, note: str = None) -> bool:
    """
    Update an existing delibera.
    
    Args:
        delibera_id: Delibera ID
        numero: New number (optional)
        oggetto: New subject (optional)
        esito: New outcome (optional)
        data_votazione: New voting date (optional)
        favorevoli: New favorable votes (optional)
        contrari: New contrary votes (optional)
        astenuti: New abstentions (optional)
        allegato_path: New attachment path (optional)
        note: New notes (optional)
    
    Returns:
        True if successful, False otherwise
    """
    from database import exec_query
    
    try:
        updates = []
        values = []
        
        if numero is not None:
            updates.append("numero=?")
            values.append(numero)
        if oggetto is not None:
            updates.append("oggetto=?")
            values.append(oggetto)
        if esito is not None:
            valid_esiti = {'APPROVATA', 'RESPINTA', 'RINVIATA'}
            if esito not in valid_esiti:
                logger.error("Invalid esito: %s", esito)
                return False
            updates.append("esito=?")
            values.append(esito)
        if data_votazione is not None:
            updates.append("data_votazione=?")
            values.append(data_votazione)
        if favorevoli is not None:
            updates.append("favorevoli=?")
            values.append(favorevoli)
        if contrari is not None:
            updates.append("contrari=?")
            values.append(contrari)
        if astenuti is not None:
            updates.append("astenuti=?")
            values.append(astenuti)
        if allegato_path is not None:
            allegato_path = _maybe_archive_delibera_attachment(int(delibera_id), allegato_path)
            updates.append("allegato_path=?")
            values.append(allegato_path)
        if note is not None:
            updates.append("note=?")
            values.append(note)
        
        if not updates:
            logger.warning("No fields to update for delibera %s", delibera_id)
            return False
        
        values.append(delibera_id)
        sql = f"UPDATE cd_delibere SET {', '.join(updates)} WHERE id=?"
        exec_query(sql, values)
        
        logger.info(f"Updated delibera {delibera_id}")
        return True
    except Exception as e:
        logger.error("Failed to update delibera %s: %s", delibera_id, e)
        return False

def delete_delibera(delibera_id: int, delete_attachment: bool = False) -> bool:
    """
    Delete a delibera.
    
    Args:
        delibera_id: Delibera ID
        delete_attachment: If True, delete the attached file
    
    Returns:
        True if successful, False otherwise
    """
    from database import exec_query
    
    try:
        if delete_attachment:
            delibera = get_delibera_by_id(delibera_id)
            if delibera and delibera.get('allegato_path'):
                allegato_path = delibera['allegato_path']
                try:
                    if os.path.exists(allegato_path):
                        os.remove(allegato_path)
                        logger.info(f"Deleted attachment: {allegato_path}")
                except Exception as e:
                    logger.warning(f"Could not delete attachment: {e}")
        
        exec_query("DELETE FROM cd_delibere WHERE id=?", (delibera_id,))
        logger.info(f"Deleted delibera {delibera_id}")
        return True
    except Exception as e:
        logger.error("Failed to delete delibera %s: %s", delibera_id, e)
        return False

def get_esiti_summary(meeting_id: int) -> Dict[str, int]:
    """
    Get summary of delibere outcomes for a meeting.
    
    Args:
        meeting_id: CD meeting ID
    
    Returns:
        Dictionary with counts: {'APPROVATA': n, 'RESPINTA': n, 'RINVIATA': n}
    """
    from database import fetch_all
    
    try:
        sql = "SELECT esito, COUNT(*) as count FROM cd_delibere WHERE cd_id=? GROUP BY esito"
        rows = fetch_all(sql, (meeting_id,))
        summary = {'APPROVATA': 0, 'RESPINTA': 0, 'RINVIATA': 0}
        for row in rows:
            summary[row['esito']] = row['count']
        return summary
    except Exception as e:
        logger.error("Failed to get esiti summary: %s", e)
        return {'APPROVATA': 0, 'RESPINTA': 0, 'RINVIATA': 0}
