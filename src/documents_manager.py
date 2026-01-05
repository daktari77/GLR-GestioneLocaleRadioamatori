# -*- coding: utf-8 -*-
"""
Document management for members
"""

import os
import re
import shutil
import logging
import secrets
from pathlib import Path
from datetime import datetime

from documents_catalog import ensure_category
from file_archiver import unique_hex_filename

logger = logging.getLogger("librosoci")

DOCS_BASE_DIR = "data/documents"
_SAFE_TOKEN_RE = re.compile(r"[^A-Z0-9]+")
_member_token_cache: dict[int, str] = {}
_HEX_DIGITS = {"0","1","2","3","4","5","6","7","8","9","a","b","c","d","e","f","A","B","C","D","E","F"}
DOCUMENT_INDEX_FILENAME = "elenco_documenti.txt"


def _get_custom_member_categories() -> list[str]:
    try:
        from config_manager import load_config

        cfg = load_config()
        custom = cfg.get("custom_document_categories") if isinstance(cfg, dict) else None
        if not isinstance(custom, list):
            return []
        return [str(c).strip() for c in custom if str(c).strip()]
    except Exception:
        return []

def ensure_docs_dir():
    """Ensure documents directory exists."""
    Path(DOCS_BASE_DIR).mkdir(parents=True, exist_ok=True)

def get_member_docs_dir(socio_id: int) -> str:
    """Get or create the documents directory for a member named after their nominativo."""
    ensure_docs_dir()
    token = _resolve_member_token(socio_id)
    member_dir = os.path.join(DOCS_BASE_DIR, token)
    Path(member_dir).mkdir(parents=True, exist_ok=True)
    return member_dir

def upload_document(
    socio_id: int,
    file_path: str,
    doc_type: str = "documento",
    categoria: str | None = None,
    descrizione: str | None = None,
) -> tuple[bool, str]:
    """Upload a document for a member (with optional descrizione metadata)."""
    ensure_docs_dir()
    
    if not os.path.exists(file_path):
        return False, "File non trovato"
    
    member_dir = get_member_docs_dir(socio_id)
    categoria_value = ensure_category(categoria, extra_allowed=_get_custom_member_categories())

    description_value = (descrizione or "").strip() or None

    try:
        # Create subdirectory by type
        type_dir = os.path.join(member_dir, doc_type)
        Path(type_dir).mkdir(parents=True, exist_ok=True)
        
        # Generate destination path using a 10-char hex token plus original extension
        ext = os.path.splitext(file_path)[1].lower()
        dest_filename = _unique_hex_filename(type_dir, ext)
        dest_path = os.path.join(type_dir, dest_filename)
        
        # Copy file
        shutil.copy2(file_path, dest_path)
        
        # Store in database
        from database import add_documento
        doc_id = add_documento(socio_id, dest_filename, dest_path, doc_type, categoria_value, description_value)
        
        logger.info("Document uploaded: %s (ID: %d)", dest_path, doc_id)
        _refresh_member_document_indexes(socio_id)
        return True, f"Documento caricato: {dest_filename}"
        
    except Exception as e:
        logger.error("Failed to upload document: %s", e)
        return False, f"Errore: {str(e)}"


def bulk_import_member_documents(
    socio_id: int,
    source_dir: str,
    categoria: str | None,
    *,
    move: bool = False,
) -> tuple[int, int, list[str]]:
    """Bulk import all files inside a folder for a member.

    Imports are performed per-category as requested by the UI.

    Notes:
    - Non-recursive: only files directly inside `source_dir` are processed.
    - If `move=True`, the source file is deleted only after a successful upload.

    Returns:
        (imported_count, failed_count, details)
    """

    src_root = (source_dir or "").strip()
    if not src_root or not os.path.isdir(src_root):
        raise ValueError("Cartella sorgente non valida")

    normalized_category = ensure_category(categoria, extra_allowed=_get_custom_member_categories())
    doc_type = "privacy" if normalized_category.lower() == "privacy" else "documento"

    imported = 0
    failed = 0
    details: list[str] = []

    try:
        filenames = sorted(os.listdir(src_root))
    except OSError as exc:
        raise RuntimeError(f"Impossibile leggere la cartella: {exc}")

    for name in filenames:
        src_path = os.path.join(src_root, name)
        if not os.path.isfile(src_path):
            continue

        success, msg = upload_document(
            socio_id,
            src_path,
            doc_type,
            normalized_category,
            None,
        )
        if success:
            imported += 1
            if move:
                try:
                    os.remove(src_path)
                except OSError as exc:
                    details.append(f"{name}: importato ma non spostato ({exc})")
        else:
            failed += 1
            details.append(f"{name}: {msg}")

    return imported, failed, details

def delete_document(socio_id: int, doc_id: int) -> tuple[bool, str]:
    """Delete a document and remove file."""
    try:
        from database import get_documenti, delete_documento
        
        docs = get_documenti(socio_id)
        doc = next((d for d in docs if d['id'] == doc_id), None)
        
        if not doc:
            return False, "Documento non trovato"
        
        # Delete file
        if os.path.exists(doc['percorso']):
            os.remove(doc['percorso'])
        
        # Delete from database
        if delete_documento(doc_id):
            logger.info("Document deleted: %s", doc['percorso'])
            _refresh_member_document_indexes(socio_id)
            return True, "Documento eliminato"
        else:
            return False, "Errore nell'eliminazione del documento"
            
    except Exception as e:
        logger.error("Failed to delete document: %s", e)
        return False, f"Errore: {str(e)}"

def get_document_size_mb(percorso: str) -> float:
    """Get document size in MB."""
    if os.path.exists(percorso):
        return os.path.getsize(percorso) / (1024 * 1024)
    return 0

def format_file_info(percorso: str) -> str:
    """Format file information string."""
    if not os.path.exists(percorso):
        return "File mancante"
    
    size_mb = get_document_size_mb(percorso)
    mtime = os.path.getmtime(percorso)
    mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
    
    return f"{size_mb:.2f} MB ({mtime_str})"

def update_document_category(doc_id: int, categoria: str | None) -> tuple[bool, str]:
    """Update the catalog category stored for a document without renaming the file."""
    try:
        normalized = ensure_category(categoria, extra_allowed=_get_custom_member_categories())
        from database import get_documento_with_member, update_documento_categoria

        doc = get_documento_with_member(doc_id)
        if not doc:
            return False, "Documento non trovato"

        update_documento_categoria(doc_id, normalized)
        logger.info("Document %s category updated to %s", doc_id, normalized)
        owner_id = doc.get("socio_id")
        if owner_id is not None:
            _refresh_member_document_indexes(int(owner_id))
        return True, "Categoria aggiornata"
    except Exception as exc:
        logger.error("Failed to update document category %s: %s", doc_id, exc)
        return False, f"Errore: {exc}"

def update_document_description(doc_id: int, descrizione: str | None) -> tuple[bool, str]:
    """Update only the description metadata stored for a document."""
    try:
        from database import update_documento_descrizione, get_documento_with_member

        doc = get_documento_with_member(doc_id)
        if not doc:
            return False, "Documento non trovato"
        normalized = (descrizione or "").strip()
        update_documento_descrizione(doc_id, normalized)
        logger.info("Document %s description updated", doc_id)
        owner_id = doc.get("socio_id")
        if owner_id is not None:
            _refresh_member_document_indexes(int(owner_id))
        return True, "Descrizione aggiornata"
    except Exception as exc:
        logger.error("Failed to update document description %s: %s", doc_id, exc)
        return False, f"Errore: {exc}"


def relink_missing_documents(new_root: str) -> tuple[int, int, list[str]]:
    """Attempt to fix missing document paths when the base directory changes."""
    from database import get_all_documenti_with_member_names, update_documento_fileinfo
    from config import BASE_DIR

    if not new_root:
        raise ValueError("new_root non valido")

    base_dir = Path(BASE_DIR).expanduser().resolve()
    selected_root_path = Path(new_root).expanduser().resolve()
    old_root_path = (base_dir / Path(DOCS_BASE_DIR)).expanduser().resolve()

    def _looks_like_docs_root(p: Path) -> bool:
        """Heuristic: a docs root contains many member folders, each with 'documento'/'privacy' subfolders."""
        try:
            if not p.exists() or not p.is_dir():
                return False
            checked = 0
            for child in p.iterdir():
                if not child.is_dir():
                    continue
                checked += 1
                # Typical structure: <TOKEN>/documento and/or <TOKEN>/privacy
                if (child / "documento").is_dir() or (child / "privacy").is_dir():
                    return True
                if checked >= 40:
                    break
            return False
        except Exception:
            return False

    def _find_docs_root_under(base: Path) -> Path | None:
        """Try to locate a docs root under a base folder (non-recursive, best-effort)."""
        try:
            if not base.exists() or not base.is_dir():
                return None
            candidates: list[Path] = []

            # Common paths if the user selected BASE_DIR or data folder.
            candidates.append(base / "documents")
            candidates.append(base / "documenti")
            candidates.append(base / "data" / "documents")
            candidates.append(base / "data" / "documenti")

            # If renamed, it's often documents* (e.g. documents_old, documents_2026).
            try:
                for child in base.iterdir():
                    if not child.is_dir():
                        continue
                    name = child.name.lower()
                    if "documents" in name or "documenti" in name or name == "documenti":
                        candidates.append(child)
            except Exception:
                pass

            # Also check one level deeper under data/ (common container).
            data_dir = base / "data"
            try:
                if data_dir.exists() and data_dir.is_dir():
                    for child in data_dir.iterdir():
                        if not child.is_dir():
                            continue
                        name = child.name.lower()
                        if "documents" in name or "documenti" in name or name == "documenti":
                            candidates.append(child)
            except Exception:
                pass

            seen: set[Path] = set()
            for cand in candidates:
                try:
                    resolved = cand.expanduser().resolve()
                except Exception:
                    resolved = cand
                if resolved in seen:
                    continue
                seen.add(resolved)
                if _looks_like_docs_root(resolved):
                    return resolved
            return None
        except Exception:
            return None

    # Accept selecting the real docs root or a parent folder (BASE_DIR / data).
    new_root_path = selected_root_path
    if not _looks_like_docs_root(new_root_path):
        detected = _find_docs_root_under(new_root_path)
        if detected is None:
            detected = _find_docs_root_under(base_dir)
        if detected is not None:
            logger.info("Relink: root '%s' doesn't look like docs root; using '%s'", selected_root_path, detected)
            new_root_path = detected

    updated = 0
    unresolved = 0
    unresolved_details: list[str] = []

    if new_root_path != selected_root_path:
        unresolved_details.append(
            f"Nota: cartella selezionata '{selected_root_path}' non sembra la radice documenti; uso '{new_root_path}'."
        )

    def _relpath_under(base: Path, target: Path) -> Path | None:
        """Return target relative to base if target is under base (Windows-case tolerant)."""
        try:
            # Fast path.
            return target.relative_to(base)
        except Exception:
            pass

        try:
            base_s = os.path.normcase(os.path.normpath(str(base)))
            target_s = os.path.normcase(os.path.normpath(str(target)))
            # Ensure both are absolute and on same drive/root.
            common = os.path.commonpath([base_s, target_s])
            if common != base_s:
                return None
            rel_s = os.path.relpath(target_s, base_s)
            return Path(rel_s)
        except Exception:
            return None

    def _extract_structured_relpath(target: Path) -> Path | None:
        """Best-effort extractor for legacy absolute paths.

        Expected layout is:
            <docs_root>/<TOKEN>/(documento|privacy)/<filename>

        When the DB stores an absolute path outside BASE_DIR, computing relpath
        against a fixed old root is unreliable. This extracts the last TOKEN +
        doc_type + filename portion so we can rebuild the candidate under the new root.
        """
        try:
            parts = list(target.parts)
            if len(parts) < 3:
                return None

            # Prefer the last occurrence to handle weird nested paths.
            for marker in ("documento", "privacy"):
                try:
                    idx = len(parts) - 1 - list(reversed([p.lower() for p in parts])).index(marker)
                except ValueError:
                    continue

                # Need at least: TOKEN / marker / filename
                if idx >= 1 and idx + 1 < len(parts):
                    token = parts[idx - 1]
                    if not token or token.lower() in {"documents", "documenti", "data"}:
                        continue
                    return Path(*parts[idx - 1:])
            return None
        except Exception:
            return None

    rows = get_all_documenti_with_member_names()
    for row in rows:
        doc = dict(row)
        current_path = doc.get("percorso") or ""

        def _exists_under_base(p: Path) -> bool:
            try:
                if p.is_absolute():
                    return p.exists()
                return (base_dir / p).exists()
            except Exception:
                return False

        if current_path:
            normalized = Path(os.path.normpath(str(current_path).strip()))
            if _exists_under_base(normalized):
                continue

        socio_id = doc.get("socio_id")
        nominativo = doc.get("nominativo") or f"Socio #{socio_id or '?'}"

        if not current_path:
            unresolved += 1
            unresolved_details.append(f"ID {doc.get('id')} · {nominativo} · percorso non registrato")
            continue

        source_path = Path(os.path.normpath(str(current_path).strip()))
        if source_path.is_absolute():
            source_abs = source_path
        else:
            source_abs = (base_dir / source_path).resolve()

        # Try multiple strategies to compute a stable relative path.
        relative_path: Path | None = None

        # 1) If the stored path contains an explicit 'documents'/'documenti' segment,
        # use that as an old root for best accuracy.
        try:
            lower_parts = [p.lower() for p in source_abs.parts]
            for seg in ("documents", "documenti"):
                if seg in lower_parts:
                    idx = lower_parts.index(seg)
                    guessed_old_root = Path(*source_abs.parts[: idx + 1])
                    relative_path = _relpath_under(guessed_old_root, source_abs)
                    if relative_path is not None:
                        break
        except Exception:
            pass

        # 2) Fall back to the configured old root.
        if relative_path is None:
            relative_path = _relpath_under(old_root_path, source_abs)

        # 3) As a last resort, extract TOKEN/doc_type/filename from the stored path.
        if relative_path is None:
            relative_path = _extract_structured_relpath(source_abs)

        # 4) Final fallback: just the filename.
        if relative_path is None:
            relative_path = Path(doc.get("nome_file") or source_path.name)

        # Ensure we don't accidentally join with an absolute path.
        if relative_path.is_absolute():
            relative_path = Path(relative_path.name)

        candidate = (new_root_path / relative_path).resolve()
        if candidate.exists():
            try:
                stored_name = doc.get("nome_file") or candidate.name
                stored_path: str
                try:
                    stored_path = str(candidate.relative_to(base_dir))
                except Exception:
                    stored_path = str(candidate)
                update_documento_fileinfo(int(doc["id"]), stored_name, stored_path)
                updated += 1
            except Exception as exc:  # pragma: no cover - DB safeguard
                unresolved += 1
                unresolved_details.append(f"ID {doc.get('id')} · errore aggiornamento: {exc}")
        else:
            unresolved += 1
            unresolved_details.append(f"ID {doc.get('id')} · {nominativo} · {candidate} non trovato")

    logger.info("Relink document paths completed: %s updated, %s unresolved", updated, unresolved)
    return updated, unresolved, unresolved_details

def bulk_rename_documents_to_schema(*, dry_run: bool = False) -> list[tuple[str, str]]:
    """Rename every stored document so that filenames are 10-char hex tokens."""
    from database import (
        get_all_documenti_with_member_names,
        update_documento_fileinfo,
    )

    pending_changes: list[tuple[str, str]] = []
    docs = get_all_documenti_with_member_names()
    for doc in docs:
        current_path = doc.get('percorso') or ''
        if not current_path or not os.path.exists(current_path):
            logger.warning("Percorso non trovato per documento %s", doc.get('id'))
            continue

        directory = os.path.dirname(current_path)
        ext = os.path.splitext(current_path)[1].lower()
        current_name = os.path.basename(current_path)
        if _is_hex_filename(current_name):
            continue

        new_filename = _unique_hex_filename(directory, ext, current_path=current_path)
        if new_filename == current_name:
            continue

        new_path = os.path.join(directory, new_filename)
        pending_changes.append((current_path, new_path))

        if dry_run:
            continue

        try:
            Path(directory).mkdir(parents=True, exist_ok=True)
            os.replace(current_path, new_path)
            update_documento_fileinfo(doc['id'], new_filename, new_path)
            logger.info("Documento %s rinominato in %s", current_path, new_path)
        except Exception as exc:
            logger.error("Impossibile rinominare %s: %s", current_path, exc)
    return pending_changes

def _unique_hex_filename(directory: str, extension: str, *, current_path: str | None = None) -> str:
    """Compatibility wrapper (historical local helper).

    Uses the shared file_archiver.unique_hex_filename() implementation.
    """
    while True:
        candidate = unique_hex_filename(Path(directory), extension)
        candidate_path = os.path.join(directory, candidate)
        if current_path and _paths_equal(candidate_path, current_path):
            return candidate
        if not os.path.exists(candidate_path):
            return candidate

def _is_hex_filename(filename: str, length: int = 10) -> bool:
    stem, _ext = os.path.splitext(filename)
    if len(stem) != length:
        return False
    return all(ch in _HEX_DIGITS for ch in stem)


def _refresh_member_document_indexes(socio_id: int):
    """Write/update TXT indexes in each member document folder."""
    from database import get_documenti

    docs = get_documenti(socio_id)
    grouped: dict[str, list[dict]] = {}
    for doc in docs:
        doc_type = (doc.get("tipo") or "documento").strip() or "documento"
        grouped.setdefault(doc_type, []).append(doc)

    base_dir = Path(get_member_docs_dir(socio_id))
    existing_dirs = {p.name for p in base_dir.iterdir() if p.is_dir()}
    target_types = set(grouped.keys()) | existing_dirs
    for doc_type in sorted(target_types):
        type_dir = base_dir / doc_type
        type_dir.mkdir(parents=True, exist_ok=True)
        entries = grouped.get(doc_type, [])
        _write_index_file(type_dir, entries, socio_id, doc_type)


def _write_index_file(directory: Path, entries: list[dict], socio_id: int, doc_type: str):
    lines = [
        f"Elenco documenti socio {socio_id} - cartella '{doc_type}'",
        "Nome file\tDescrizione\tTipo\tCategoria",
    ]
    if entries:
        entries = sorted(entries, key=lambda item: str(item.get("nome_file", "")))
        for doc in entries:
            name = str(doc.get("nome_file") or "")
            descr = (doc.get("descrizione") or "").replace("\t", " ").replace("\n", " ")
            tipo = str(doc.get("tipo") or "")
            categoria = str(doc.get("categoria") or "")
            lines.append(f"{name}\t{descr}\t{tipo}\t{categoria}")
    else:
        lines.append("(Nessun documento presente)")

    index_path = directory / DOCUMENT_INDEX_FILENAME
    with index_path.open("w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")

def _paths_equal(path_a: str, path_b: str) -> bool:
    try:
        return Path(path_a).resolve() == Path(path_b).resolve()
    except FileNotFoundError:
        return os.path.normcase(os.path.normpath(path_a)) == os.path.normcase(os.path.normpath(path_b))

def _resolve_member_token(socio_id: int, prefetched_name: str | None = None) -> str:
    if socio_id in _member_token_cache:
        return _member_token_cache[socio_id]

    display_name = prefetched_name
    if not display_name:
        from database import fetch_one
        row = fetch_one("SELECT nominativo, nome, cognome FROM soci WHERE id = ?", (socio_id,))
        if row:
            row_dict = dict(row)
            display_name = row_dict.get('nominativo') or f"{row_dict.get('nome', '')} {row_dict.get('cognome', '')}".strip()

    if not display_name:
        display_name = f"SOCIO_{socio_id}"

    token = _sanitize_token(display_name, fallback=f"SOCIO_{socio_id}")
    _member_token_cache[socio_id] = token
    return token

def _sanitize_token(value: str | None, fallback: str) -> str:
    text = (value or "").strip().upper()
    text = _SAFE_TOKEN_RE.sub("_", text)
    text = text.strip("_")
    return text or fallback

