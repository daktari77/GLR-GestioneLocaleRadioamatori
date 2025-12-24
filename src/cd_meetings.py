# -*- coding: utf-8 -*-
"""
CD Meetings management for GLR Gestione Locale Radioamatori
Handles registration of CD meetings and related documents (verbali in .doc/.pdf format)
"""

import sqlite3
import logging
import os
from typing import List, Tuple, Optional, Dict
from datetime import datetime

logger = logging.getLogger("librosoci")

def get_all_meetings() -> List[Dict]:
    """
    Get all CD meetings ordered by date (most recent first).
    
    Returns:
        List of meeting dictionaries with keys: id, numero_cd, data, titolo, verbale_path, created_at
    """
    from database import fetch_all
    try:
        sql = "SELECT id, numero_cd, data, titolo, verbale_path, created_at FROM cd_riunioni ORDER BY data DESC"
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
        sql = "SELECT id, numero_cd, data, titolo, note as odg, verbale_path, created_at FROM cd_riunioni WHERE id=?"
        row = fetch_one(sql, (meeting_id,))
        return dict(row) if row else None
    except Exception as e:
        logger.error("Failed to get meeting %s: %s", meeting_id, e)
        return None

def add_meeting(data: str, numero_cd: str | None = None, titolo: str | None = None, odg: str | None = None, verbale_path: str | None = None) -> int:
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
    from database import get_conn
    from utils import now_iso
    
    try:
        with get_conn() as conn:
            cursor = conn.cursor()
            sql = """
                INSERT INTO cd_riunioni (numero_cd, data, titolo, note, verbale_path, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """
            cursor.execute(sql, (numero_cd, data, titolo, odg, verbale_path, now_iso()))
            meeting_id = cursor.lastrowid
            conn.commit()
        
        if meeting_id is None:
            logger.error("Failed to get meeting ID after insert")
            return -1
        
        logger.info(f"Added meeting on {data} (ID: {meeting_id})")
        return meeting_id
    except Exception as e:
        logger.error("Failed to add meeting: %s", e)
        return -1

def update_meeting(meeting_id: int, numero_cd: str | None = None, data: str | None = None, titolo: str | None = None, odg: str | None = None, verbale_path: str | None = None) -> bool:
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
    from database import get_conn
    
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
        if odg is not None:
            updates.append("note=?")
            values.append(odg)
        if verbale_path is not None:
            updates.append("verbale_path=?")
            values.append(verbale_path)
        
        if not updates:
            logger.warning("No fields to update for meeting %s", meeting_id)
            return False
        
        values.append(meeting_id)
        sql = f"UPDATE cd_riunioni SET {', '.join(updates)} WHERE id=?"
        
        with get_conn() as conn:
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
        # Get verbale path before deletion
        if delete_verbale:
            meeting = get_meeting_by_id(meeting_id)
            if meeting and meeting.get('verbale_path'):
                verbale_path = meeting['verbale_path']
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
    if not meeting or not meeting.get('verbale_path'):
        return None
    
    verbale_path = meeting['verbale_path']
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
