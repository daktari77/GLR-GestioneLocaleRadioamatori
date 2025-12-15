# -*- coding: utf-8 -*-
"""
CD Verbali (Minutes) management for GLR Gestione Locale Radioamatori v4.2a
Handles registration of CD meeting minutes with detailed tracking
"""

import sqlite3
import logging
import os
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger("librosoci")

def get_all_verbali(meeting_id: int = None) -> List[Dict]:
    """
    Get all verbali, optionally filtered by meeting.
    
    Args:
        meeting_id: Optional meeting ID to filter by
    
    Returns:
        List of verbali dictionaries
    """
    from database import fetch_all, get_conn
    try:
        # Check if table exists
        try:
            with get_conn() as conn:
                conn.execute("SELECT 1 FROM cd_verbali LIMIT 1")
        except sqlite3.OperationalError:
            # Table doesn't exist, return empty list
            logger.warning("Table cd_verbali doesn't exist yet")
            return []
        
        if meeting_id:
            sql = """
                SELECT v.id, v.cd_id, v.data_redazione, v.segretario, v.presidente, v.odg, 
                       v.documento_path, v.note, v.created_at
                FROM cd_verbali v
                WHERE v.cd_id = ?
                ORDER BY v.data_redazione DESC
            """
            rows = fetch_all(sql, (meeting_id,))
        else:
            sql = """
                SELECT v.id, v.cd_id, v.data_redazione, v.segretario, v.presidente, v.odg, 
                       v.documento_path, v.note, v.created_at
                FROM cd_verbali v
                ORDER BY v.cd_id DESC, v.data_redazione DESC
            """
            rows = fetch_all(sql)
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error("Failed to get verbali: %s", e)
        return []

def get_verbale_by_id(verbale_id: int) -> Optional[Dict]:
    """
    Get a specific verbale by ID.
    
    Args:
        verbale_id: Verbale ID
    
    Returns:
        Verbale dictionary or None if not found
    """
    from database import fetch_one
    try:
        sql = """
            SELECT id, cd_id, data_redazione, segretario, presidente, odg, 
                   documento_path, note, created_at
            FROM cd_verbali WHERE id = ?
        """
        row = fetch_one(sql, (verbale_id,))
        return dict(row) if row else None
    except Exception as e:
        logger.error("Failed to get verbale %s: %s", verbale_id, e)
        return None

def add_verbale(cd_id: int, data_redazione: str, segretario: str = None, presidente: str = None,
                odg: str = None, documento_path: str = None, note: str = None) -> int:
    """
    Add a new verbale to a CD meeting.
    
    Args:
        cd_id: CD meeting ID
        data_redazione: Minutes date (YYYY-MM-DD)
        segretario: Secretary name
        presidente: President/Chair name
        odg: Agenda (Ordine del Giorno)
        documento_path: Optional path to minutes document (.doc/.pdf)
        note: Optional notes
    
    Returns:
        ID of inserted verbale or -1 on error
    """
    from database import exec_query, fetch_one
    from utils import now_iso
    
    try:
        sql = """
            INSERT INTO cd_verbali 
            (cd_id, data_redazione, segretario, presidente, odg, documento_path, note, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        exec_query(sql, (cd_id, data_redazione, segretario, presidente, odg, documento_path, note, now_iso()))
        
        result = fetch_one("SELECT last_insert_rowid() as id")
        verbale_id = result['id'] if result else -1
        
        logger.info(f"Added verbale to meeting {cd_id} (ID: {verbale_id})")
        return verbale_id
    except Exception as e:
        logger.error("Failed to add verbale: %s", e)
        return -1

def update_verbale(verbale_id: int, data_redazione: str = None, segretario: str = None,
                   presidente: str = None, odg: str = None, documento_path: str = None,
                   note: str = None) -> bool:
    """
    Update an existing verbale.
    
    Args:
        verbale_id: Verbale ID
        data_redazione: New minutes date (optional)
        segretario: New secretary name (optional)
        presidente: New president name (optional)
        odg: New agenda (optional)
        documento_path: New document path (optional)
        note: New notes (optional)
    
    Returns:
        True if successful, False otherwise
    """
    from database import exec_query
    
    try:
        updates = []
        values = []
        
        if data_redazione is not None:
            updates.append("data_redazione=?")
            values.append(data_redazione)
        if segretario is not None:
            updates.append("segretario=?")
            values.append(segretario)
        if presidente is not None:
            updates.append("presidente=?")
            values.append(presidente)
        if odg is not None:
            updates.append("odg=?")
            values.append(odg)
        if documento_path is not None:
            updates.append("documento_path=?")
            values.append(documento_path)
        if note is not None:
            updates.append("note=?")
            values.append(note)
        
        if not updates:
            logger.warning("No fields to update for verbale %s", verbale_id)
            return False
        
        values.append(verbale_id)
        sql = f"UPDATE cd_verbali SET {', '.join(updates)} WHERE id=?"
        exec_query(sql, values)
        
        logger.info(f"Updated verbale {verbale_id}")
        return True
    except Exception as e:
        logger.error("Failed to update verbale %s: %s", verbale_id, e)
        return False

def delete_verbale(verbale_id: int, delete_documento: bool = False) -> bool:
    """
    Delete a verbale.
    
    Args:
        verbale_id: Verbale ID
        delete_documento: If True, delete the document file
    
    Returns:
        True if successful, False otherwise
    """
    from database import exec_query
    
    try:
        if delete_documento:
            verbale = get_verbale_by_id(verbale_id)
            if verbale and verbale.get('documento_path'):
                documento_path = verbale['documento_path']
                try:
                    if os.path.exists(documento_path):
                        os.remove(documento_path)
                        logger.info(f"Deleted document: {documento_path}")
                except Exception as e:
                    logger.warning(f"Could not delete document: {e}")
        
        exec_query("DELETE FROM cd_verbali WHERE id=?", (verbale_id,))
        logger.info(f"Deleted verbale {verbale_id}")
        return True
    except Exception as e:
        logger.error("Failed to delete verbale %s: %s", verbale_id, e)
        return False

def validate_documento(file_path: str) -> tuple:
    """
    Validate that a file is a supported document format.
    
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

def get_documento_info(verbale_id: int) -> Optional[Dict]:
    """
    Get information about a verbale's document.
    
    Args:
        verbale_id: Verbale ID
    
    Returns:
        Dictionary with document info or None if no document
    """
    verbale = get_verbale_by_id(verbale_id)
    if not verbale or not verbale.get('documento_path'):
        return None
    
    documento_path = verbale['documento_path']
    try:
        if os.path.exists(documento_path):
            size = os.path.getsize(documento_path)
            mtime = os.path.getmtime(documento_path)
            return {
                'path': documento_path,
                'name': os.path.basename(documento_path),
                'size': size,
                'size_formatted': f"{size / 1024:.1f} KB" if size < 1024*1024 else f"{size / (1024*1024):.1f} MB",
                'modified': datetime.fromtimestamp(mtime).isoformat()
            }
        else:
            logger.warning(f"Document file not found: {documento_path}")
            return None
    except Exception as e:
        logger.error(f"Error getting document info for verbale {verbale_id}: {e}")
        return None
