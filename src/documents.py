# -*- coding: utf-8 -*-
"""
Document management for GLR Gestione Locale Radioamatori
"""

import os
import shutil
import logging
from typing import Optional, List

logger = logging.getLogger("librosoci")

def list_documenti_for_socio(socio_id: int):
    """List all documents for a given socio."""
    from database import fetch_all
    return fetch_all("""
        SELECT id, nome_file, tipo, categoria, data_caricamento, percorso
        FROM documenti
        WHERE socio_id = ?
        ORDER BY datetime(data_caricamento) DESC, id DESC
    """, (socio_id,))

def add_documento_record(
    socio_id: int,
    nome_file: str,
    percorso: str,
    tipo: str,
    categoria: str | None = None,
    descrizione: str | None = None,
):
    """Add a document record to the database."""
    from database import exec_query
    from utils import now_iso
    exec_query(
        "INSERT INTO documenti (socio_id, nome_file, percorso, tipo, categoria, descrizione, data_caricamento) VALUES (?,?,?,?,?,?,?)",
        (socio_id, nome_file, percorso, tipo, categoria, descrizione, now_iso())
    )

def delete_documento_record(doc_id: int):
    """Delete a document record from the database."""
    from database import exec_query
    exec_query("DELETE FROM documenti WHERE id=?", (doc_id,))

def copy_in_socio_folder(source_path: str, matricola: Optional[str]) -> str:
    """Copy a file to the socio's documents folder."""
    from utils import docs_dir_for_matricola
    base = os.path.basename(source_path)
    dst_dir = docs_dir_for_matricola(matricola)
    name, ext = os.path.splitext(base)
    dest = os.path.join(dst_dir, base)
    i = 1
    while os.path.exists(dest):
        dest = os.path.join(dst_dir, f"{name}_{i}{ext}")
        i += 1
    shutil.copy2(source_path, dest)
    return dest

def move_file_to_trash(path: str, trash_dir: str):
    """Move a file to the trash directory."""
    try:
        rel = os.path.relpath(path, os.path.dirname(trash_dir))
    except ValueError:
        rel = os.path.basename(path)
    dst = os.path.join(trash_dir, rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    try:
        shutil.move(path, dst)
    except Exception as e:
        logger.warning("Failed to move file to trash: %s", e)
