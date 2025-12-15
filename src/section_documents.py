"""Helpers for managing section-wide documents stored on disk."""
from __future__ import annotations

import json
import logging
import os
import secrets
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List

from config import SEC_DOCS

SECTION_DOCUMENT_ROOT = Path(SEC_DOCS)
SECTION_METADATA_FILE = SECTION_DOCUMENT_ROOT / "metadata.json"
SECTION_DOCUMENT_CATEGORIES: tuple[str, ...] = (
    "Verbali CD",
    "Bilanci",
    "Regolamenti",
    "Modulistica",
    "Documenti ARI",
    "Quote ARI",
    "Altro",
)
DEFAULT_SECTION_CATEGORY = SECTION_DOCUMENT_CATEGORIES[0]
SECTION_DOCUMENT_INDEX_FILENAME = "elenco_documenti.txt"
METADATA_SCHEMA_VERSION = 1

logger = logging.getLogger("librosoci")


def _load_metadata() -> dict[str, dict]:
    ensure_section_structure()
    if not SECTION_METADATA_FILE.exists():
        return {}
    try:
        with SECTION_METADATA_FILE.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Impossibile leggere metadata documenti sezione: %s", exc)
        return {}
    if isinstance(raw, dict) and "documents" in raw and isinstance(raw["documents"], dict):
        raw = raw["documents"]
    if not isinstance(raw, dict):
        return {}
    normalized: dict[str, dict] = {}
    for key, value in raw.items():
        if isinstance(value, dict):
            normalized[str(key)] = dict(value)
    return normalized


def _save_metadata(metadata: dict[str, dict]):
    ensure_section_structure()
    payload = {"schema_version": METADATA_SCHEMA_VERSION, "documents": metadata}
    tmp_path = SECTION_METADATA_FILE.with_suffix(".tmp")
    try:
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(tmp_path, SECTION_METADATA_FILE)
    except OSError as exc:
        logger.error("Impossibile salvare metadata documenti sezione: %s", exc)
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def _relative_to_root(path: Path) -> str | None:
    try:
        rel = path.resolve().relative_to(SECTION_DOCUMENT_ROOT.resolve())
        return rel.as_posix()
    except ValueError:
        return None


def _generate_hash_token(existing: Iterable[str], length: int = 10) -> str:
    existing_set = set(existing)
    while True:
        token = secrets.token_hex(max(1, (length + 1) // 2))[:length]
        if token not in existing_set:
            return token


def _remove_metadata_for_path(path: Path):
    rel = _relative_to_root(path)
    if not rel:
        return
    metadata = _load_metadata()
    keys_to_delete = [key for key, payload in metadata.items() if payload.get("relative_path") == rel]
    if not keys_to_delete:
        return
    for key in keys_to_delete:
        metadata.pop(key, None)
    _save_metadata(metadata)


def _sanitize_token(value: str, *, fallback: str) -> str:
    normalized = "".join(ch if ch.isalnum() else "_" for ch in value.upper())
    normalized = normalized.strip("_")
    return normalized or fallback


def _ensure_unique_filename(directory: Path, base_name: str, extension: str | None, current_path: Path | None = None) -> str:
    suffix = extension or ""
    candidate = f"{base_name}{suffix}"
    counter = 2
    while True:
        candidate_path = directory / candidate
        if not candidate_path.exists() or (current_path and candidate_path.resolve() == current_path.resolve()):
            return candidate
        candidate = f"{base_name}_{counter}{suffix}"
        counter += 1


def _build_section_basename(category: str, date_token: str) -> str:
    category_token = _sanitize_token(_normalize_category(category), fallback="DOCUMENTO")
    day_token = _sanitize_token(date_token, fallback=datetime.now().strftime("%Y%m%d"))
    return f"SEZIONE_{category_token}_{day_token}"


def _slugify(label: str) -> str:
    return "_".join(label.lower().split()) or "misc"


def _normalize_category(value: str | None) -> str:
    if not value:
        return DEFAULT_SECTION_CATEGORY
    candidate = value.strip()
    if not candidate:
        return DEFAULT_SECTION_CATEGORY
    for category in SECTION_DOCUMENT_CATEGORIES:
        if category.lower() == candidate.lower():
            return category
    return "Altro"


def _category_dir(category: str) -> Path:
    normalized = _normalize_category(category)
    directory = SECTION_DOCUMENT_ROOT / _slugify(normalized)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _category_from_directory(directory: Path) -> str:
    slug = directory.name.lower()
    for category in SECTION_DOCUMENT_CATEGORIES:
        if _slugify(category) == slug:
            return category
    return DEFAULT_SECTION_CATEGORY


def ensure_section_index_file(category: str) -> Path:
    """Ensure the TXT listing for a given section category exists (regenerated when invoked)."""
    ensure_section_structure()
    normalized = _normalize_category(category)
    directory = _category_dir(normalized)
    index_path = directory / SECTION_DOCUMENT_INDEX_FILENAME

    metadata = _load_metadata()
    metadata_by_path: dict[str, dict] = {}
    for payload in metadata.values():
        rel = payload.get("relative_path")
        if not rel:
            continue
        abs_path = (SECTION_DOCUMENT_ROOT / rel).resolve()
        metadata_by_path[str(abs_path)] = payload

    lines = [
        f"Elenco documenti sezione - categoria '{normalized}'",
        "Nome file\tDescrizione\tCategoria\tPercorso relativo",
    ]

    try:
        for path in sorted(directory.iterdir(), key=lambda p: p.name.lower()):
            if not path.is_file() or path.name == SECTION_DOCUMENT_INDEX_FILENAME:
                continue
            resolved = path.resolve()
            payload = metadata_by_path.get(str(resolved))
            descrizione = (payload.get("description") if payload else "") or ""
            categoria = payload.get("categoria") if payload else normalized
            rel = _relative_to_root(resolved) or path.name
            originale = (payload.get("original_name") if payload else None) or path.name
            lines.append(f"{originale}\t{descrizione}\t{categoria}\t{rel}")

        if len(lines) == 2:
            lines.append("(Nessun documento presente)")

        with index_path.open("w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    except OSError as exc:
        logger.warning("Impossibile aggiornare l'indice documenti sezione %s: %s", normalized, exc)

    return index_path


def ensure_section_structure():
    SECTION_DOCUMENT_ROOT.mkdir(parents=True, exist_ok=True)
    for cat in SECTION_DOCUMENT_CATEGORIES:
        _category_dir(cat)


def list_section_documents() -> List[Dict[str, object]]:
    ensure_section_structure()
    docs: List[Dict[str, object]] = []
    metadata = _load_metadata()
    indexed_paths: set[str] = set()

    for hash_id, payload in metadata.items():
        rel_path = payload.get("relative_path")
        if not rel_path:
            continue
        path = (SECTION_DOCUMENT_ROOT / rel_path).resolve()
        if not path.exists() or not path.is_file():
            logger.warning("Documento sezione %s mancante sul disco", rel_path)
            continue
        relative_display = rel_path or _relative_to_root(path) or path.name
        try:
            stat = path.stat()
        except OSError:
            continue
        categoria = payload.get("categoria") or _category_from_directory(path.parent)
        docs.append(
            {
                "nome_file": payload.get("original_name") or path.name,
                "categoria": categoria,
                "percorso": relative_display,
                "relative_path": relative_display,
                "absolute_path": str(path),
                "size": stat.st_size,
                "mtime": stat.st_mtime,
                "hash_id": hash_id,
                "stored_name": payload.get("stored_name") or path.name,
                "descrizione": payload.get("description", ""),
                "original_name": payload.get("original_name") or path.name,
                "uploaded_at": payload.get("uploaded_at"),
            }
        )
        indexed_paths.add(str(path).lower())

    for category in SECTION_DOCUMENT_CATEGORIES:
        current_dir = _category_dir(category)
        for path in current_dir.glob("*"):
            if not path.is_file():
                continue
            resolved = path.resolve()
            resolved_key = str(resolved).lower()
            if resolved_key in indexed_paths:
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            rel = _relative_to_root(resolved)
            relative_display = rel or resolved.name
            docs.append(
                {
                    "nome_file": path.name,
                    "categoria": category,
                    "percorso": relative_display,
                    "relative_path": relative_display,
                    "absolute_path": str(resolved),
                    "size": stat.st_size,
                    "mtime": stat.st_mtime,
                    "hash_id": None,
                    "stored_name": path.name,
                    "descrizione": "",
                    "original_name": path.name,
                    "uploaded_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            )
            indexed_paths.add(resolved_key)
    docs.sort(
        key=lambda item: (
            str(item.get("categoria", "")),
            str(item.get("nome_file", "")).lower(),
        )
    )
    return docs


def add_section_document(source_path: str, categoria: str, descrizione: str | None = None) -> str:
    ensure_section_structure()
    src = Path(source_path)
    if not src.exists() or not src.is_file():
        raise FileNotFoundError(f"File sorgente non trovato: {source_path}")

    normalized_category = _normalize_category(categoria)
    target_dir = _category_dir(normalized_category)

    metadata = _load_metadata()
    description_value = (descrizione or "").strip()
    existing_tokens = set(metadata.keys())
    while True:
        hash_id = _generate_hash_token(existing_tokens)
        candidate_name = f"{hash_id}{src.suffix.lower()}"
        dest = target_dir / candidate_name
        if not dest.exists():
            break
        existing_tokens.add(hash_id)

    shutil.copy2(src, dest)

    relative_path = _relative_to_root(dest)
    if not relative_path:
        raise RuntimeError("Impossibile determinare il percorso relativo del documento di sezione")

    metadata[hash_id] = {
        "hash_id": hash_id,
        "categoria": normalized_category,
        "original_name": src.name,
        "stored_name": dest.name,
        "description": description_value,
        "uploaded_at": datetime.now().isoformat(),
        "relative_path": relative_path,
    }
    _save_metadata(metadata)

    return str(dest.resolve())


def update_section_document_metadata(path: str, categoria: str, descrizione: str | None = None) -> bool:
    """Update category/description metadata for a stored section document."""
    ensure_section_structure()
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Documento non trovato: {path}")

    rel = _relative_to_root(file_path)
    if not rel:
        raise ValueError("Il documento selezionato non appartiene alla cartella della sezione")

    metadata = _load_metadata()
    entry_key = None
    for key, payload in metadata.items():
        if payload.get("relative_path") == rel:
            entry_key = key
            break

    if not entry_key:
        raise ValueError("Documento non indicizzato: ricaricalo per generare i metadata")

    entry = metadata[entry_key]
    normalized_category = _normalize_category(categoria)
    description_value = (descrizione or "").strip()

    destination = file_path
    if normalized_category != entry.get("categoria"):
        target_dir = _category_dir(normalized_category)
        desired_name = entry.get("stored_name") or file_path.name
        candidate = target_dir / desired_name
        if not candidate.exists():
            new_path = candidate
        else:
            base_name = Path(desired_name).stem
            new_filename = _ensure_unique_filename(target_dir, base_name, file_path.suffix, None)
            new_path = target_dir / new_filename
        target_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(file_path), str(new_path))
        destination = new_path

    entry["categoria"] = normalized_category
    entry["description"] = description_value
    new_rel = _relative_to_root(destination)
    if new_rel:
        entry["relative_path"] = new_rel
    entry["stored_name"] = destination.name

    _save_metadata(metadata)
    return True


def delete_section_document(path: str) -> bool:
    try:
        file_path = Path(path)
        file_path.unlink()
        _remove_metadata_for_path(file_path)
        return True
    except FileNotFoundError:
        _remove_metadata_for_path(Path(path))
        return False


def rename_section_documents_to_schema(*, dry_run: bool = False) -> list[tuple[str, str]]:
    """Rename existing section documents to the SEZIONE_CATEGORIA_DATA schema."""
    ensure_section_structure()
    metadata = _load_metadata()
    tracked_paths: set[str] = set()
    for payload in metadata.values():
        rel = payload.get("relative_path")
        if not rel:
            continue
        tracked = (SECTION_DOCUMENT_ROOT / rel).resolve()
        tracked_paths.add(str(tracked).lower())
    changes: list[tuple[str, str]] = []
    for category in SECTION_DOCUMENT_CATEGORIES:
        directory = _category_dir(category)
        for path in directory.glob("*"):
            if not path.is_file():
                continue
            if str(path.resolve()).lower() in tracked_paths:
                continue
            stat = path.stat()
            date_token = datetime.fromtimestamp(stat.st_mtime).strftime("%Y%m%d")
            base_name = _build_section_basename(category, date_token)
            new_name = _ensure_unique_filename(directory, base_name, path.suffix, path)
            if new_name == path.name:
                continue
            new_path = directory / new_name
            changes.append((str(path), str(new_path)))
            if not dry_run:
                path.rename(new_path)
    return changes


def human_readable_size(size_bytes: int) -> str:
    if size_bytes <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(size_bytes)
    unit = 0
    while size >= 1024 and unit < len(units) - 1:
        size /= 1024
        unit += 1
    return f"{size:.1f} {units[unit]}"


def human_readable_mtime(timestamp: float | int | None) -> str:
    if not timestamp:
        return "-"
    try:
        return datetime.fromtimestamp(float(timestamp)).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return "-"
