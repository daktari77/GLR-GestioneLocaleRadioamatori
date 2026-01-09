"""Helpers for managing section-wide documents stored on disk.

Versione v0.4.2+: i documenti di sezione sono tracciati in SQLite (tabella
`section_documents`) con campi uniformati a `documenti` (soci):
`nome_file`, `percorso`, `tipo`, `categoria`, `descrizione`, `data_caricamento`.

Per compatibilita' con installazioni precedenti, resta un'import best-effort da
`metadata.json` e dall'albero su disco.
"""
from __future__ import annotations

import json
import logging
import os
import secrets
import shutil
import time
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List

from config import SEC_DOCS
from document_types_catalog import DEFAULT_SECTION_CATEGORY, SECTION_DOCUMENT_CATEGORIES

SECTION_DOCUMENT_ROOT = Path(SEC_DOCS)
SECTION_METADATA_FILE = SECTION_DOCUMENT_ROOT / "metadata.json"
SECTION_DOCUMENT_INDEX_FILENAME = "elenco_documenti.txt"
METADATA_SCHEMA_VERSION = 1

logger = logging.getLogger("librosoci")


# Naming convention aligned with member docs: <hex token> + extension.
# Use a different length to distinguish section docs from member docs.
SECTION_DOC_TOKEN_LENGTH = 15


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _safe_sha256_file(path: Path) -> str | None:
    try:
        return _sha256_file(path)
    except Exception:
        return None


def _iter_files_in_dir(directory: Path) -> Iterable[Path]:
    try:
        for p in directory.iterdir():
            if p.is_file():
                yield p
    except Exception:
        return


def _build_hash_index(directory: Path) -> dict[str, Path]:
    """Build a best-effort SHA256 -> Path map for files in directory."""
    index: dict[str, Path] = {}
    for p in _iter_files_in_dir(directory):
        # Skip non-doc helper files
        if p.name.lower() == SECTION_DOCUMENT_INDEX_FILENAME.lower():
            continue
        digest = _safe_sha256_file(p)
        if not digest:
            continue
        index.setdefault(digest, p)
    return index


def _preferred_token_for_content(digest_hex: str) -> str | None:
    d = (digest_hex or "").strip().lower()
    if len(d) < SECTION_DOC_TOKEN_LENGTH:
        return None
    prefix = d[:SECTION_DOC_TOKEN_LENGTH]
    return prefix if _is_hex_token(prefix, length=SECTION_DOC_TOKEN_LENGTH) else None


def _is_hex_token(value: str, *, length: int) -> bool:
    text = (value or "").strip()
    if len(text) != length:
        return False
    for ch in text:
        if ch not in "0123456789abcdefABCDEF":
            return False
    return True


def _is_abs_path(value: str | None) -> bool:
    if not value:
        return False
    try:
        return Path(value).is_absolute()
    except Exception:
        return False


def _resolve_to_absolute(
    percorso_or_rel: str | None,
    *,
    fallback_rel: str | None = None,
    root_dir: Path | None = None,
) -> Path | None:
    """Resolve a DB path to an absolute Path (preferably within root_dir).

    Some installations may contain stale absolute paths in the DB (e.g. dev paths).
    When both an absolute path and a relative path exist, prefer the one that is
    under the configured root_dir.
    """

    root = (root_dir or SECTION_DOCUMENT_ROOT).resolve()
    candidate = (percorso_or_rel or "").strip()
    fallback = (fallback_rel or "").strip()

    def _is_under_root(p: Path) -> bool:
        try:
            p.resolve().relative_to(root)
            return True
        except Exception:
            return False

    def _resolve_rel(rel: str) -> Path:
        p = Path(rel)
        if p.is_absolute():
            return p
        return (root / rel).resolve()

    resolved_fallback: Path | None = None
    if fallback:
        resolved_fallback = _resolve_rel(fallback)

    if candidate:
        p = Path(candidate)
        if p.is_absolute():
            # Prefer a valid fallback under root if the absolute path is outside root.
            if resolved_fallback and _is_under_root(resolved_fallback) and resolved_fallback.exists():
                return resolved_fallback
            return p
        return _resolve_rel(candidate)

    if resolved_fallback:
        return resolved_fallback
    return None


def _db_backfill_registry() -> None:
    """Ensure section documents are tracked in DB (best effort).

    This keeps backward compatibility with metadata.json while fulfilling
    the requirement that section docs are also tracked in SQLite.
    """

    try:
        from database import (
            add_section_document_record,
            get_section_document_by_relative_path,
        )
    except Exception:
        return

    ensure_section_structure()

    def _safe_insert(
        *,
        hash_id: str,
        categoria: str,
        descrizione: str,
        protocollo: str,
        verbale_numero: str,
        original_name: str,
        stored_name: str,
        relative_path: str,
        uploaded_at: str,
        absolute_path: str,
    ):
        # Best-effort: tolerate transient locks (e.g. antivirus/backup or concurrent instance)
        for attempt in range(3):
            try:
                if get_section_document_by_relative_path(relative_path):
                    return
                add_section_document_record(
                    hash_id=hash_id,
                    nome_file=stored_name,
                    percorso=absolute_path,
                    tipo="documento",
                    data_caricamento=uploaded_at,
                    categoria=categoria,
                    descrizione=descrizione,
                    protocollo=protocollo,
                    verbale_numero=verbale_numero,
                    original_name=original_name,
                    stored_name=stored_name,
                    relative_path=relative_path,
                    uploaded_at=uploaded_at,
                )
                return
            except Exception as exc:
                try:
                    from exceptions import DatabaseLockError

                    is_lock = isinstance(exc, DatabaseLockError)
                except Exception:
                    is_lock = False

                if is_lock and attempt < 2:
                    time.sleep(0.25 * (attempt + 1))
                    continue
                return

    # 1) Import existing metadata.json entries
    metadata = _load_metadata()
    for hash_id, payload in metadata.items():
        rel_path = payload.get("relative_path")
        if not rel_path:
            continue
        abs_path = (SECTION_DOCUMENT_ROOT / str(rel_path)).resolve()
        if not abs_path.exists() or not abs_path.is_file():
            continue
        try:
            stat = abs_path.stat()
        except OSError:
            continue
        _safe_insert(
            hash_id=str(hash_id),
            categoria=payload.get("categoria") or _category_from_directory(abs_path.parent),
            descrizione=(payload.get("description") or "") or "",
            protocollo=(payload.get("protocollo") or "") or "",
            verbale_numero=(payload.get("verbale_numero") or "") or "",
            original_name=(payload.get("original_name") or abs_path.name) or abs_path.name,
            stored_name=(payload.get("stored_name") or abs_path.name) or abs_path.name,
            relative_path=str(rel_path),
            uploaded_at=(payload.get("uploaded_at") or datetime.fromtimestamp(stat.st_mtime).isoformat()),
            absolute_path=str(abs_path),
        )

    # 2) Import orphan files found on disk
    for category in SECTION_DOCUMENT_CATEGORIES:
        directory = _category_dir(category)
        for path in directory.glob("*"):
            if not path.is_file() or path.name == SECTION_DOCUMENT_INDEX_FILENAME:
                continue
            rel = _relative_to_root(path)
            if not rel:
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            if len(path.stem) >= SECTION_DOC_TOKEN_LENGTH:
                guessed_hash = path.stem[:SECTION_DOC_TOKEN_LENGTH]
            elif len(path.stem) >= 10:
                guessed_hash = path.stem[:10]
            else:
                guessed_hash = secrets.token_hex(8)[:SECTION_DOC_TOKEN_LENGTH]
            _safe_insert(
                hash_id=guessed_hash,
                categoria=_category_from_directory(path.parent),
                descrizione="",
                protocollo="",
                verbale_numero="",
                original_name=path.name,
                stored_name=path.name,
                relative_path=rel,
                uploaded_at=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                absolute_path=str(path.resolve()),
            )


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


def _get_custom_section_categories() -> list[str]:
    try:
        from config_manager import load_config

        cfg = load_config()
        custom = cfg.get("custom_section_document_categories") if isinstance(cfg, dict) else None
        if not isinstance(custom, list):
            return []
        return [str(c).strip() for c in custom if str(c).strip()]
    except Exception:
        return []


def _normalize_category(value: str | None) -> str:
    if not value:
        return DEFAULT_SECTION_CATEGORY
    candidate = value.strip()
    if not candidate:
        return DEFAULT_SECTION_CATEGORY
    for category in SECTION_DOCUMENT_CATEGORIES:
        if category.lower() == candidate.lower():
            return category
    for category in _get_custom_section_categories():
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
    for category in _get_custom_section_categories():
        if _slugify(category) == slug:
            return category
    return DEFAULT_SECTION_CATEGORY


def ensure_section_index_file(category: str) -> Path:
    """Ensure the TXT listing for a given section category exists (regenerated when invoked)."""
    ensure_section_structure()
    normalized = _normalize_category(category)
    directory = _category_dir(normalized)
    index_path = directory / SECTION_DOCUMENT_INDEX_FILENAME

    # Prefer DB records; fall back to metadata.json when DB is unavailable.
    db_rows: list[dict] = []
    try:
        from database import list_section_document_records

        _db_backfill_registry()
        db_rows = list_section_document_records(include_deleted=False)
    except Exception:
        db_rows = []

    metadata = _load_metadata() if not db_rows else {}
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
        if db_rows:
            for row in db_rows:
                categoria = str(row.get("categoria") or "")
                if categoria != normalized:
                    continue
                abs_path = _resolve_to_absolute(
                    str(row.get("percorso") or ""),
                    fallback_rel=str(row.get("relative_path") or ""),
                )
                if not abs_path or not abs_path.exists() or not abs_path.is_file():
                    continue
                rel = _relative_to_root(abs_path) or abs_path.name
                originale = (row.get("nome_file") or row.get("stored_name") or abs_path.name) or abs_path.name
                descrizione = (row.get("descrizione") or "") or ""
                lines.append(f"{originale}\t{descrizione}\t{categoria}\t{rel}")
        else:
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


def list_section_documents(*, include_missing: bool = False) -> List[Dict[str, object]]:
    ensure_section_structure()
    _db_backfill_registry()

    # Best-effort: recover original filenames from metadata.json.
    try:
        metadata_by_hash = _load_metadata()
    except Exception:
        metadata_by_hash = {}

    try:
        from database import list_section_document_records

        rows = list_section_document_records(include_deleted=False)
    except Exception:
        rows = []

    docs: List[Dict[str, object]] = []

    # DB-first: produce the structure expected by the UI panel.
    for row in rows:
        hash_id = str(row.get("hash_id") or "").strip()
        payload = metadata_by_hash.get(hash_id) if hash_id else None

        abs_path = _resolve_to_absolute(
            str(row.get("percorso") or ""),
            fallback_rel=str(row.get("relative_path") or ""),
        )
        if not abs_path:
            continue
        if not abs_path.exists() or not abs_path.is_file():
            # By default hide missing documents (prevents confusing size=0 entries and avoids
            # apparent duplicates after a manual disk cleanup + re-import).
            if not include_missing:
                continue
            size = 0
            mtime = None
        else:
            try:
                stat = abs_path.stat()
                size = stat.st_size
                mtime = stat.st_mtime
            except OSError:
                size = 0
                mtime = None

        rel_display = _relative_to_root(abs_path) or str(row.get("relative_path") or "") or abs_path.name
        stored_name = (row.get("stored_name") or row.get("nome_file") or abs_path.name) or abs_path.name
        # DB does not persist original filenames; prefer metadata.json when available.
        original_name = (
            (payload.get("original_name") if isinstance(payload, dict) else None)
            or abs_path.name
        )
        docs.append(
            {
                "id": row.get("id"),
                # Show original filename when available (better UX than hashed stored name).
                "nome_file": original_name,
                "categoria": row.get("categoria"),
                "percorso": rel_display,
                "relative_path": rel_display,
                "absolute_path": str(abs_path),
                "size": size,
                "mtime": mtime,
                "hash_id": row.get("hash_id"),
                "stored_name": stored_name,
                "descrizione": row.get("descrizione") or "",
                "protocollo": row.get("protocollo") or "",
                "verbale_numero": row.get("verbale_numero") or "",
                "original_name": original_name,
                "uploaded_at": row.get("data_caricamento") or row.get("uploaded_at"),
            }
        )

    docs.sort(
        key=lambda item: (
            str(item.get("categoria", "")),
            str(item.get("nome_file", "")).lower(),
        )
    )
    return docs


def recalc_section_documents_data_caricamento(docs: Iterable[Dict[str, object]]) -> tuple[int, int, list[str]]:
    """Recalculate section document dates using the file modification time.

    This updates the DB field `section_documents.data_caricamento` (used by filters
    like CD verbali by mandate) and also updates `metadata.json`'s `uploaded_at`
    best-effort for backward compatibility.

    Args:
        docs: iterable of doc dicts (must contain `id` and a path like `absolute_path`).

    Returns:
        (updated_count, missing_count, errors)
    """

    try:
        from database import update_section_document_record
    except Exception as exc:  # pragma: no cover
        return 0, 0, [f"DB non disponibile: {exc}"]

    updated = 0
    missing = 0
    errors: list[str] = []

    try:
        metadata = _load_metadata()
    except Exception:
        metadata = {}
    meta_changed = False

    for doc in docs or []:
        try:
            record_id = int(doc.get("id"))
        except Exception:
            continue

        abs_path = str(doc.get("absolute_path") or doc.get("percorso") or "").strip()
        if not abs_path or not os.path.exists(abs_path):
            missing += 1
            continue

        try:
            mtime = os.path.getmtime(abs_path)
            ts = datetime.fromtimestamp(mtime).isoformat(timespec="seconds")
            update_section_document_record(record_id, data_caricamento=ts)
            updated += 1

            hash_id = str(doc.get("hash_id") or "").strip()
            if hash_id and hash_id in metadata and isinstance(metadata.get(hash_id), dict):
                if metadata[hash_id].get("uploaded_at") != ts:
                    metadata[hash_id]["uploaded_at"] = ts
                    meta_changed = True
        except Exception as exc:
            errors.append(f"{record_id}: {exc}")

    if meta_changed:
        try:
            _save_metadata(metadata)
        except Exception:
            pass

    return updated, missing, errors


def list_cd_verbali_documents(
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    include_missing: bool = False,
) -> list[dict]:
    """Return section documents that should be considered CD verbali.

    Heuristic rules:
    - Categoria contains "verbale"/"verbali" (case-insensitive), OR
    - A non-empty `verbale_numero` is present.

    Optionally filters by date range (inclusive) using the ISO date derived
    from `uploaded_at` (or `data_caricamento` backfilled in DB).

    Result is sorted descending by date.
    """

    docs = list_section_documents(include_missing=include_missing)
    verbali: list[dict] = []
    for doc in docs:
        categoria = str(doc.get("categoria") or "").strip().lower()
        verbale_numero = str(doc.get("verbale_numero") or "").strip()
        # Match both "verbale" and "verbali" (and related forms) using the common stem.
        if "verbal" in categoria or bool(verbale_numero):
            verbali.append(doc)

    def _date_value(d: dict) -> str:
        raw = str(d.get("uploaded_at") or "").strip()
        return raw[:10] if len(raw) >= 10 else raw

    def _extract_year_from_verbale_numero(raw: str) -> int | None:
        s = str(raw or "").strip()
        if not s:
            return None
        # Common formats: "12/2025", "12-2025", "2025/12", "2025-12".
        digits = []
        cur = ""
        for ch in s:
            if ch.isdigit():
                cur += ch
            else:
                if cur:
                    digits.append(cur)
                    cur = ""
        if cur:
            digits.append(cur)

        for token in digits:
            if len(token) == 4:
                try:
                    year = int(token)
                except Exception:
                    continue
                if 1900 <= year <= 2200:
                    return year
        return None

    def _extract_iso_date_from_text(text: str | None) -> str | None:
        """Extract an ISO date (YYYY-MM-DD) from a free-form string.

        Supports common patterns:
        - YYYY-MM-DD / YYYY_MM_DD / YYYY.MM.DD / YYYY/MM/DD
        - DD-MM-YYYY / DD_MM_YYYY / DD.MM.YYYY / DD/MM/YYYY
        """

        s = str(text or "")
        if not s:
            return None

        # Normalize separators to '-'
        norm = []
        for ch in s:
            if ch in "_./\\":
                norm.append("-")
            else:
                norm.append(ch)
        s2 = "".join(norm)

        def _is_valid_ymd(y: int, m: int, d: int) -> bool:
            if y < 1900 or y > 2200:
                return False
            if m < 1 or m > 12:
                return False
            if d < 1 or d > 31:
                return False
            return True

        # Scan for YYYY-MM-DD
        for i in range(0, max(0, len(s2) - 9)):
            chunk = s2[i : i + 10]
            if len(chunk) != 10:
                continue
            if chunk[4] != "-" or chunk[7] != "-":
                continue
            y_str, m_str, d_str = chunk[0:4], chunk[5:7], chunk[8:10]
            if not (y_str.isdigit() and m_str.isdigit() and d_str.isdigit()):
                continue
            y, m, d = int(y_str), int(m_str), int(d_str)
            if _is_valid_ymd(y, m, d):
                return f"{y:04d}-{m:02d}-{d:02d}"

        # Scan for DD-MM-YYYY
        for i in range(0, max(0, len(s2) - 9)):
            chunk = s2[i : i + 10]
            if len(chunk) != 10:
                continue
            if chunk[2] != "-" or chunk[5] != "-":
                continue
            d_str, m_str, y_str = chunk[0:2], chunk[3:5], chunk[6:10]
            if not (y_str.isdigit() and m_str.isdigit() and d_str.isdigit()):
                continue
            y, m, d = int(y_str), int(m_str), int(d_str)
            if _is_valid_ymd(y, m, d):
                return f"{y:04d}-{m:02d}-{d:02d}"

        return None

    start_iso = (start_date or "").strip() or None
    end_iso = (end_date or "").strip() or None
    if start_iso or end_iso:
        start_year = None
        end_year = None
        try:
            start_year = int(start_iso[:4]) if start_iso else None
        except Exception:
            start_year = None
        try:
            end_year = int(end_iso[:4]) if end_iso else None
        except Exception:
            end_year = None

        filtered: list[dict] = []
        for d in verbali:
            dv = _date_value(d)
            if dv:
                if start_iso and dv < start_iso:
                    pass
                elif end_iso and dv > end_iso:
                    pass
                else:
                    filtered.append(d)
                    continue

            # Fallback #1: try extracting a date from filename/description/protocollo
            # (useful when importing old verbali after the mandate end).
            extracted = (
                _extract_iso_date_from_text(d.get("original_name"))
                or _extract_iso_date_from_text(d.get("nome_file"))
                or _extract_iso_date_from_text(d.get("descrizione"))
                or _extract_iso_date_from_text(d.get("protocollo"))
            )
            if extracted:
                if start_iso and extracted < start_iso:
                    pass
                elif end_iso and extracted > end_iso:
                    pass
                else:
                    filtered.append(d)
                    continue

            # Fallback: if the document is clearly a CD verbale, and it has a year
            # in `verbale_numero`, include it when the year is within the mandate years.
            year = _extract_year_from_verbale_numero(d.get("verbale_numero"))
            if year is None:
                continue
            if start_year and year < start_year:
                continue
            if end_year and year > end_year:
                continue
            filtered.append(d)
        verbali = filtered

    verbali.sort(
        key=lambda d: (
            _date_value(d),
            str(d.get("verbale_numero") or ""),
            str(d.get("nome_file") or "").lower(),
        ),
        reverse=True,
    )
    return verbali


def list_cd_verbali_linked_documents(
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    include_missing: bool = False,
) -> list[dict]:
    """Return CD verbali that are *canonically* linked to meetings.

    Source of truth is the meeting table (`cd_riunioni.verbale_section_doc_id`) joined
    to `section_documents`.

    Optionally filters by meeting date range (inclusive) using ISO dates.
    """

    try:
        from database import fetch_all, get_conn
    except Exception:
        return []

    # Be tolerant to production DBs that may lag behind the latest schema.
    # (e.g. older `section_documents` without `original_name` column.)
    cols: set[str] = set()
    try:
        conn = get_conn()
        cols = {str(r[1]) for r in conn.execute("PRAGMA table_info(section_documents)").fetchall()}
        try:
            conn.close()
        except Exception:
            pass
    except Exception:
        cols = set()

    where: list[str] = ["r.verbale_section_doc_id IS NOT NULL"]
    if "deleted_at" in cols:
        where.append("(d.deleted_at IS NULL OR TRIM(d.deleted_at) = '')")
    params: list[object] = []
    if (start_date or "").strip():
        where.append("r.data >= ?")
        params.append(str(start_date).strip())
    if (end_date or "").strip():
        where.append("r.data <= ?")
        params.append(str(end_date).strip())

    def _col(name: str, *, alias: str | None = None) -> str:
        a = alias or name
        return f"d.{name} AS {a}" if name in cols else f"NULL AS {a}"

    if "uploaded_at" in cols and "data_caricamento" in cols:
        uploaded_expr = "COALESCE(d.uploaded_at, d.data_caricamento) AS uploaded_at"
    elif "uploaded_at" in cols:
        uploaded_expr = "d.uploaded_at AS uploaded_at"
    elif "data_caricamento" in cols:
        uploaded_expr = "d.data_caricamento AS uploaded_at"
    else:
        uploaded_expr = "NULL AS uploaded_at"

    sql = f"""
        SELECT
            r.id AS meeting_id,
            r.data AS meeting_date,
            r.numero_cd AS meeting_numero_cd,
            d.id,
            {_col('hash_id')},
            {_col('nome_file')},
            {_col('percorso')},
            {_col('tipo')},
            {_col('categoria')},
            {_col('descrizione')},
            {_col('protocollo')},
            {_col('verbale_numero')},
            {_col('original_name')},
            {_col('stored_name')},
            {_col('relative_path')},
            {uploaded_expr}
        FROM cd_riunioni r
        JOIN section_documents d ON d.id = r.verbale_section_doc_id
        WHERE {' AND '.join(where)}
        ORDER BY r.data DESC, r.numero_cd DESC, r.id DESC
    """

    try:
        rows = fetch_all(sql, tuple(params))
    except Exception:
        return []

    out: list[dict] = []
    for row in rows or []:
        d = dict(row)

        # Add an absolute_path key compatible with list_section_documents()
        abs_path = None
        try:
            resolved = _resolve_to_absolute(
                str(d.get("percorso") or "") or None,
                fallback_rel=str(d.get("relative_path") or "") or None,
            )
            abs_path = str(resolved) if resolved is not None else ""
        except Exception:
            abs_path = str(d.get("percorso") or "")

        d["absolute_path"] = abs_path
        if not include_missing:
            if not abs_path:
                continue
            try:
                if not os.path.exists(abs_path):
                    continue
            except Exception:
                continue

        out.append(d)

    return out


def add_section_document(
    source_path: str,
    categoria: str,
    descrizione: str | None = None,
    *,
    protocollo: str | None = None,
    verbale_numero: str | None = None,
) -> str:
    ensure_section_structure()
    src = Path(source_path)
    if not src.exists() or not src.is_file():
        raise FileNotFoundError(f"File sorgente non trovato: {source_path}")

    normalized_category = _normalize_category(categoria)
    target_dir = _category_dir(normalized_category)

    metadata = _load_metadata()
    description_value = (descrizione or "").strip()
    protocollo_value = (protocollo or "").strip()
    verbale_numero_value = (verbale_numero or "").strip()

    # De-duplication by content: if the same file already exists in the target category,
    # reuse it instead of creating a new copy with a different token.
    src_digest = _safe_sha256_file(src)
    existing_hash_index = _build_hash_index(target_dir) if src_digest else {}
    if src_digest and src_digest in existing_hash_index:
        dest = existing_hash_index[src_digest]
        hash_id = dest.stem
    else:
        # Prefer a deterministic token derived from SHA256 to prevent future duplicates.
        preferred = _preferred_token_for_content(src_digest) if src_digest else None

        existing_tokens = set(metadata.keys())
        if preferred:
            existing_tokens.add(preferred)

        # Try preferred token first; fall back to random token on collision.
        candidates: list[str] = []
        if preferred:
            candidates.append(preferred)

        for _ in range(50):
            candidates.append(_generate_hash_token(existing_tokens, length=SECTION_DOC_TOKEN_LENGTH))

        chosen: str | None = None
        for token in candidates:
            candidate_name = f"{token}{src.suffix.lower()}"
            candidate_dest = target_dir / candidate_name
            if not candidate_dest.exists():
                chosen = token
                dest = candidate_dest
                break
        if not chosen:
            raise RuntimeError("Impossibile determinare un nome file univoco per il documento di sezione")
        hash_id = chosen

        shutil.copy2(src, dest)

    relative_path = _relative_to_root(dest)
    if not relative_path:
        raise RuntimeError("Impossibile determinare il percorso relativo del documento di sezione")

    # Use the file modification time as the document date shown in UI.
    # Keep the import timestamp separate.
    import_ts = datetime.now().isoformat(timespec="seconds")
    try:
        st = src.stat()
        doc_ts = datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")
    except OSError:
        doc_ts = import_ts

    # Persist DB tracking (primary). Avoid duplicate registry rows when reusing an existing file.
    try:
        from database import add_section_document_record, get_section_document_by_relative_path

        if not get_section_document_by_relative_path(str(dest.resolve())) and not get_section_document_by_relative_path(relative_path):
            add_section_document_record(
                hash_id=hash_id,
                nome_file=dest.name,
                percorso=str(dest.resolve()),
                tipo="documento",
                data_caricamento=doc_ts,
                categoria=normalized_category,
                descrizione=description_value,
                protocollo=protocollo_value or None,
                verbale_numero=verbale_numero_value or None,
                original_name=src.name,
                stored_name=dest.name,
                relative_path=relative_path,
                uploaded_at=import_ts,
            )
    except Exception as exc:
        logger.warning("Impossibile registrare documento sezione su DB: %s", exc)

    # Mantieni metadata.json solo per compatibilita' (best effort)
    try:
        metadata[hash_id] = {
            "hash_id": hash_id,
            "categoria": normalized_category,
            "original_name": src.name,
            "stored_name": dest.name,
            "description": description_value,
            "protocollo": protocollo_value,
            "verbale_numero": verbale_numero_value,
            "uploaded_at": doc_ts,
            "relative_path": relative_path,
        }
        _save_metadata(metadata)
    except Exception:
        pass

    return str(dest.resolve())


def bulk_import_section_documents(
    source_dir: str,
    categoria: str,
    *,
    move: bool = False,
    descrizione: str | None = None,
    protocollo: str | None = None,
    verbale_numero: str | None = None,
) -> tuple[int, int, list[str]]:
    """Bulk import all files inside a folder for section documents.

    - Non-recursive: only files directly inside `source_dir` are processed.
    - DB-consistent: if DB insert fails, the copied destination file is removed.
    - If `move=True`, the source file is deleted only after a successful DB insert.

    Returns:
        (imported_count, failed_count, details)
    """

    ensure_section_structure()

    src_root = (source_dir or "").strip()
    if not src_root or not os.path.isdir(src_root):
        raise ValueError("Cartella sorgente non valida")

    normalized_category = _normalize_category(categoria)
    target_dir = _category_dir(normalized_category)

    description_value = (descrizione or "").strip()
    protocollo_value = (protocollo or "").strip()
    verbale_numero_value = (verbale_numero or "").strip()

    imported = 0
    failed = 0
    details: list[str] = []

    # Build a hash index once to avoid creating duplicates (same content, different name).
    existing_hash_index = _build_hash_index(target_dir)

    try:
        filenames = sorted(os.listdir(src_root))
    except OSError as exc:
        raise RuntimeError(f"Impossibile leggere la cartella: {exc}")

    for name in filenames:
        src = Path(src_root) / name
        if not src.is_file():
            continue

        metadata = _load_metadata()
        src_digest = _safe_sha256_file(src)
        if src_digest and src_digest in existing_hash_index:
            # Reuse existing file and only ensure DB registry exists.
            dest = existing_hash_index[src_digest]
            hash_id = dest.stem
            reused = True
        else:
            reused = False
            preferred = _preferred_token_for_content(src_digest) if src_digest else None
            existing_tokens = set(metadata.keys())
            if preferred:
                existing_tokens.add(preferred)

            candidates: list[str] = []
            if preferred:
                candidates.append(preferred)
            for _ in range(50):
                candidates.append(_generate_hash_token(existing_tokens, length=SECTION_DOC_TOKEN_LENGTH))

            chosen: str | None = None
            dest = None
            for token in candidates:
                candidate_name = f"{token}{src.suffix.lower()}"
                candidate_dest = target_dir / candidate_name
                if not candidate_dest.exists():
                    chosen = token
                    dest = candidate_dest
                    break

            if not chosen or dest is None:
                failed += 1
                details.append(f"{name}: impossibile determinare nome univoco")
                continue

            hash_id = chosen

        try:
            if not reused:
                shutil.copy2(src, dest)

            relative_path = _relative_to_root(dest)
            if not relative_path:
                raise RuntimeError("Impossibile determinare il percorso relativo del documento di sezione")

            import_ts = datetime.now().isoformat(timespec="seconds")
            try:
                st = src.stat()
                doc_ts = datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")
            except OSError:
                doc_ts = import_ts

            from database import add_section_document_record

            # Ensure we don't create duplicate DB rows when reusing an existing file
            try:
                from database import get_section_document_by_relative_path

                exists_row = get_section_document_by_relative_path(str(dest.resolve())) or get_section_document_by_relative_path(relative_path)
            except Exception:
                exists_row = None

            if exists_row:
                imported += 1
                details.append(f"{name}: duplicato (riusato {dest.name})")
                continue

            inserted = False
            last_exc: Exception | None = None
            for attempt in range(3):
                try:
                    add_section_document_record(
                        hash_id=hash_id,
                        nome_file=dest.name,
                        percorso=str(dest.resolve()),
                        tipo="documento",
                        data_caricamento=doc_ts,
                        categoria=normalized_category,
                        descrizione=description_value,
                        protocollo=protocollo_value or None,
                        verbale_numero=verbale_numero_value or None,
                        original_name=src.name,
                        stored_name=dest.name,
                        relative_path=relative_path,
                        uploaded_at=import_ts,
                    )
                    inserted = True
                    break
                except Exception as exc:
                    last_exc = exc
                    try:
                        from exceptions import DatabaseLockError

                        is_lock = isinstance(exc, DatabaseLockError)
                    except Exception:
                        is_lock = False

                    if is_lock and attempt < 2:
                        time.sleep(0.25 * (attempt + 1))
                        continue
                    break

            if not inserted:
                raise RuntimeError(f"DB insert failed: {last_exc}")

            if src_digest:
                existing_hash_index.setdefault(src_digest, dest)

            # Mantieni metadata.json solo per compatibilita' (best effort)
            try:
                metadata[hash_id] = {
                    "hash_id": hash_id,
                    "categoria": normalized_category,
                    "original_name": src.name,
                    "stored_name": dest.name,
                    "description": description_value,
                    "protocollo": protocollo_value,
                    "verbale_numero": verbale_numero_value,
                    "uploaded_at": doc_ts,
                    "relative_path": relative_path,
                }
                _save_metadata(metadata)
            except Exception:
                pass

            if move:
                try:
                    src.unlink()
                except OSError as exc:
                    details.append(f"{src.name}: importato ma non spostato ({exc})")

            imported += 1
        except Exception as exc:
            failed += 1
            details.append(f"{src.name}: {exc}")
            try:
                if dest.exists():
                    dest.unlink()
            except Exception:
                pass

    return imported, failed, details


def update_section_document_metadata(
    path: str,
    categoria: str,
    descrizione: str | None = None,
    *,
    protocollo: str | None = None,
    verbale_numero: str | None = None,
) -> bool:
    """Update category/description metadata for a stored section document."""
    ensure_section_structure()
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Documento non trovato: {path}")

    rel = _relative_to_root(file_path)
    if not rel:
        raise ValueError("Il documento selezionato non appartiene alla cartella della sezione")

    # Prefer DB lookup; fall back to metadata.json.
    entry_key = None
    entry: dict | None = None
    db_row: dict | None = None
    try:
        from database import get_section_document_by_relative_path

        db_row = get_section_document_by_relative_path(rel)
    except Exception:
        db_row = None

    if db_row is None:
        metadata = _load_metadata()
        for key, payload in metadata.items():
            if payload.get("relative_path") == rel:
                entry_key = key
                entry = payload
                break
        if not entry_key or entry is None:
            raise ValueError("Documento non indicizzato: ricaricalo per generare la registrazione")
    else:
        entry_key = str(db_row.get("hash_id") or "") or None
        entry = db_row
    normalized_category = _normalize_category(categoria)
    description_value = (descrizione or "").strip()
    protocollo_value = (protocollo or "").strip()
    verbale_numero_value = (verbale_numero or "").strip()

    destination = file_path
    if normalized_category != (entry.get("categoria") if entry else None):
        target_dir = _category_dir(normalized_category)
        desired_name = (entry.get("stored_name") if entry else None) or file_path.name
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

    if entry is not None:
        # Keep both DB field (descrizione) and legacy metadata field (description)
        entry["categoria"] = normalized_category
        entry["descrizione"] = description_value
        entry["description"] = description_value
        entry["protocollo"] = protocollo_value
        entry["verbale_numero"] = verbale_numero_value
    new_rel = _relative_to_root(destination)
    if entry is not None and new_rel:
        entry["relative_path"] = new_rel
    if entry is not None:
        entry["stored_name"] = destination.name

    # Update DB tracking (primary)
    try:
        from database import (
            get_section_document_by_relative_path,
            update_section_document_record,
            add_section_document_record,
        )

        new_rel_db = new_rel or rel
        row = get_section_document_by_relative_path(str(rel)) or get_section_document_by_relative_path(str(new_rel_db))
        if row:
            update_section_document_record(
                int(row["id"]),
                categoria=normalized_category,
                descrizione=description_value,
                protocollo=protocollo_value or None,
                verbale_numero=verbale_numero_value or None,
                percorso=str(destination.resolve()),
                stored_name=destination.name,
                nome_file=destination.name,
                tipo="documento",
                relative_path=str(new_rel_db),
            )
        else:
            add_section_document_record(
                hash_id=str(entry_key or secrets.token_hex(5)),
                nome_file=destination.name,
                percorso=str(destination.resolve()),
                tipo="documento",
                data_caricamento=(entry.get("data_caricamento") if entry else None)
                or (entry.get("uploaded_at") if entry else None)
                or datetime.now().isoformat(timespec="seconds"),
                categoria=normalized_category,
                descrizione=description_value,
                protocollo=protocollo_value or None,
                verbale_numero=verbale_numero_value or None,
                original_name=(entry.get("original_name") if entry else None) or destination.name,
                stored_name=destination.name,
                relative_path=str(new_rel_db),
                uploaded_at=(entry.get("uploaded_at") if entry else None) or datetime.now().isoformat(timespec="seconds"),
            )
    except Exception:
        pass

    # Aggiorna metadata.json (best effort)
    try:
        metadata = _load_metadata()
        key_to_update = None
        for key, payload in metadata.items():
            if payload.get("relative_path") == rel or (new_rel and payload.get("relative_path") == new_rel):
                key_to_update = key
                break
        if key_to_update:
            metadata[key_to_update]["categoria"] = normalized_category
            metadata[key_to_update]["description"] = description_value
            metadata[key_to_update]["protocollo"] = protocollo_value
            metadata[key_to_update]["verbale_numero"] = verbale_numero_value
            if new_rel:
                metadata[key_to_update]["relative_path"] = new_rel
            metadata[key_to_update]["stored_name"] = destination.name
            _save_metadata(metadata)
    except Exception:
        pass
    return True


def delete_section_document(path: str) -> bool:
    file_path = Path(path)

    # Soft-delete DB record first (best effort)
    try:
        rel = _relative_to_root(file_path)
        if rel:
            from database import get_section_document_by_relative_path, soft_delete_section_document_record

            row = get_section_document_by_relative_path(rel)
            if row:
                soft_delete_section_document_record(int(row["id"]))
    except Exception:
        pass

    try:
        file_path.unlink()
        _remove_metadata_for_path(file_path)
        return True
    except FileNotFoundError:
        _remove_metadata_for_path(file_path)
        return False


def bulk_rename_section_documents_to_hex_tokens(
    *,
    token_length: int = SECTION_DOC_TOKEN_LENGTH,
    dry_run: bool = False,
    root_dir: str | Path | None = None,
) -> list[tuple[str, str]]:
    """Rename tracked section documents to <hex token><extension>.

    - Operates DB-first: only renames files that have a DB record (deleted excluded).
    - Updates DB record (hash_id, stored_name, nome_file, percorso/relative_path).
    - Updates metadata.json best-effort.

    Returns:
        List of (old_abs_path, new_abs_path) changes.
    """
    ensure_section_structure()
    _db_backfill_registry()

    try:
        from database import list_section_document_records, update_section_document_record
    except Exception as exc:
        raise RuntimeError(f"DB non disponibile per rinomina documenti sezione: {exc}")

    rows = list_section_document_records(include_deleted=False)
    existing_tokens: set[str] = set()
    for row in rows:
        tok = str(row.get("hash_id") or "").strip()
        if tok:
            existing_tokens.add(tok)

    changes: list[tuple[str, str]] = []

    root = Path(root_dir).resolve() if root_dir else SECTION_DOCUMENT_ROOT.resolve()

    def _is_under_root(p: Path) -> bool:
        try:
            p.resolve().relative_to(root)
            return True
        except Exception:
            return False

    # Work per-record, keeping category folder unchanged.
    for row in rows:
        abs_path = _resolve_to_absolute(
            str(row.get("percorso") or ""),
            fallback_rel=str(row.get("relative_path") or ""),
            root_dir=root,
        )
        if not abs_path:
            continue
        if not _is_under_root(abs_path):
            # Safety: never touch files outside the configured section-docs root.
            continue
        if not abs_path.exists() or not abs_path.is_file():
            continue

        current_name = abs_path.name
        current_stem = abs_path.stem
        current_suffix = abs_path.suffix.lower()

        # Already compliant?
        if _is_hex_token(current_stem, length=token_length):
            continue

        # Generate new token and filename in the same folder.
        new_token = _generate_hash_token(existing_tokens, length=token_length)
        existing_tokens.add(new_token)
        new_name = f"{new_token}{current_suffix}"
        target = abs_path.with_name(new_name)
        if target.exists():
            # Extremely unlikely due to token uniqueness; still keep it safe.
            new_name = _ensure_unique_filename(abs_path.parent, new_token, current_suffix, abs_path)
            target = abs_path.with_name(new_name)

        changes.append((str(abs_path), str(target)))
        if dry_run:
            continue

        # 1) Rename on disk
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(str(abs_path), str(target))

        # 2) Update DB
        new_rel = _relative_to_root(target) or str(row.get("relative_path") or "")
        update_section_document_record(
            int(row["id"]),
            hash_id=new_token,
            stored_name=target.name,
            nome_file=target.name,
            percorso=str(target.resolve()),
            relative_path=str(new_rel),
        )

        # 3) Update metadata.json best-effort
        try:
            metadata = _load_metadata()
            key_to_update = None
            payload_to_update: dict | None = None
            old_rel = _relative_to_root(abs_path) or str(row.get("relative_path") or "")

            # Prefer match by relative path (more stable than key).
            for key, payload in metadata.items():
                if payload.get("relative_path") == old_rel:
                    key_to_update = key
                    payload_to_update = payload
                    break
            if key_to_update is None:
                # Fallback: key might match old hash
                old_key = str(row.get("hash_id") or "")
                if old_key and old_key in metadata:
                    key_to_update = old_key
                    payload_to_update = metadata.get(old_key)

            if key_to_update and isinstance(payload_to_update, dict):
                payload_to_update["hash_id"] = new_token
                payload_to_update["stored_name"] = target.name
                payload_to_update["relative_path"] = new_rel
                # Move dict key to new token when key was the old hash
                if key_to_update == str(row.get("hash_id") or "") and key_to_update != new_token:
                    metadata.pop(key_to_update, None)
                    metadata[new_token] = payload_to_update
                else:
                    metadata[key_to_update] = payload_to_update
                _save_metadata(metadata)
        except Exception:
            pass

    return changes


def reindex_section_documents(
    *,
    root_dir: str | Path | None = None,
    dry_run: bool = False,
    import_orphans: bool = False,
    backfill_registry: bool = False,
    prune_missing: bool = False,
) -> dict:
    """Reconcile DB registry with files on disk for section documents.

    Typical use cases:
    - DB contains stale absolute paths (e.g. copied from a dev installation).
    - Files were renamed/moved manually.
    - You want to normalize DB fields after bulk operations.

    What it does (best effort):
    - For each non-deleted DB record, locate the file under root_dir.
    - If found, updates DB fields:
        - percorso = absolute path
        - relative_path = path relative to root_dir
        - stored_name/nome_file = filename
        - categoria = inferred from folder (when safe)
        - hash_id = filename stem if it matches expected hex token length
    - Optionally imports orphan files found on disk (import_orphans=True).

    Returns:
        A dict summary with counts and lists of issues.
    """

    ensure_section_structure()
    if backfill_registry:
        _db_backfill_registry()

    try:
        from database import (
            add_section_document_record,
            list_section_document_records,
            soft_delete_section_document_record,
            update_section_document_record,
        )
    except Exception as exc:
        raise RuntimeError(f"DB non disponibile per re-indicizzazione documenti sezione: {exc}")

    root = Path(root_dir).resolve() if root_dir else SECTION_DOCUMENT_ROOT.resolve()

    def _is_under_root(p: Path) -> bool:
        try:
            p.resolve().relative_to(root)
            return True
        except Exception:
            return False

    def _to_rel(p: Path) -> str | None:
        try:
            return p.resolve().relative_to(root).as_posix()
        except Exception:
            return None

    def _find_on_disk(row: dict) -> Path | None:
        # 1) Prefer relative_path when it is actually relative
        rel = str(row.get("relative_path") or "").strip()
        if rel and not _is_abs_path(rel):
            cand = (root / rel).resolve()
            if cand.exists() and cand.is_file() and _is_under_root(cand):
                return cand

        # 2) Use percorso when it points under root
        perc = str(row.get("percorso") or "").strip()
        if perc:
            p = Path(perc)
            if p.is_absolute():
                if p.exists() and p.is_file() and _is_under_root(p):
                    return p
            else:
                cand = (root / perc).resolve()
                if cand.exists() and cand.is_file() and _is_under_root(cand):
                    return cand

        # 3) Reconstruct from categoria + stored_name
        stored = str(row.get("stored_name") or row.get("nome_file") or "").strip()
        cat = str(row.get("categoria") or "").strip()
        if stored and cat:
            try:
                cand = (_category_dir(_normalize_category(cat)).resolve() / stored).resolve()
                if cand.exists() and cand.is_file() and _is_under_root(cand):
                    return cand
            except Exception:
                pass

        # 4) Fallback: search by stored name or hash in the whole tree (best effort)
        targets: list[str] = []
        if stored:
            targets.append(stored.lower())
        tok = str(row.get("hash_id") or "").strip().lower()
        if tok:
            targets.append(tok)
        if not targets:
            return None

        matches: list[Path] = []
        for p in root.rglob("*"):
            if not p.is_file() or p.name == SECTION_DOCUMENT_INDEX_FILENAME or p.name == "metadata.json":
                continue
            name_l = p.name.lower()
            stem_l = p.stem.lower()
            if name_l in targets or stem_l in targets:
                matches.append(p)
                if len(matches) > 1:
                    break
        return matches[0] if len(matches) == 1 else None

    rows = list_section_document_records(include_deleted=False)
    updated: list[dict] = []
    missing: list[dict] = []
    errors: list[str] = []

    existing_hashes: set[str] = set()
    for r in rows:
        h = str(r.get("hash_id") or "").strip()
        if h:
            existing_hashes.add(h.lower())

    for row in rows:
        found = _find_on_disk(row)
        if not found:
            if prune_missing and not dry_run:
                try:
                    p = str(row.get("percorso") or "").strip()
                    rp = str(row.get("relative_path") or "").strip()
                    p_abs = Path(p) if p else None
                    rp_abs = Path(rp) if rp else None
                    outside_root = False
                    if p_abs and p_abs.is_absolute() and not _is_under_root(p_abs):
                        outside_root = True
                    if rp_abs and rp_abs.is_absolute() and not _is_under_root(rp_abs):
                        outside_root = True
                    if outside_root:
                        soft_delete_section_document_record(int(row["id"]))
                except Exception as exc:
                    errors.append(f"prune_missing id={row.get('id')}: {exc}")
            missing.append({"id": row.get("id"), "hash_id": row.get("hash_id"), "stored_name": row.get("stored_name"), "percorso": row.get("percorso"), "relative_path": row.get("relative_path")})
            continue

        rel = _to_rel(found)
        if not rel:
            missing.append({"id": row.get("id"), "hash_id": row.get("hash_id"), "stored_name": row.get("stored_name"), "percorso": row.get("percorso"), "relative_path": row.get("relative_path"), "note": "found outside root"})
            continue

        inferred_category = _category_from_directory(found.parent)
        new_hash: str | None = None
        if _is_hex_token(found.stem, length=SECTION_DOC_TOKEN_LENGTH):
            new_hash = found.stem.lower()
        elif _is_hex_token(found.stem, length=10):
            # keep legacy tokens if present
            new_hash = found.stem.lower()

        needs_update = False
        if str(row.get("stored_name") or "") != found.name:
            needs_update = True
        if str(row.get("nome_file") or "") != found.name:
            needs_update = True
        if str(row.get("relative_path") or "") != rel:
            needs_update = True
        if str(row.get("percorso") or "") != str(found.resolve()):
            needs_update = True
        if inferred_category and str(row.get("categoria") or "") != inferred_category:
            needs_update = True
        if new_hash and str(row.get("hash_id") or "").strip().lower() != new_hash:
            # Avoid collisions
            if new_hash not in existing_hashes or new_hash == str(row.get("hash_id") or "").strip().lower():
                needs_update = True

        if not needs_update:
            continue

        payload: dict = {
            "id": row.get("id"),
            "from": {
                "hash_id": row.get("hash_id"),
                "stored_name": row.get("stored_name"),
                "nome_file": row.get("nome_file"),
                "relative_path": row.get("relative_path"),
                "percorso": row.get("percorso"),
                "categoria": row.get("categoria"),
            },
            "to": {
                "hash_id": new_hash or row.get("hash_id"),
                "stored_name": found.name,
                "nome_file": found.name,
                "relative_path": rel,
                "percorso": str(found.resolve()),
                "categoria": inferred_category or row.get("categoria"),
            },
        }
        updated.append(payload)
        if dry_run:
            continue

        try:
            update_section_document_record(
                int(row["id"]),
                hash_id=(new_hash if new_hash else None),
                stored_name=found.name,
                nome_file=found.name,
                relative_path=rel,
                percorso=str(found.resolve()),
                categoria=(inferred_category if inferred_category else None),
            )
            if new_hash:
                existing_hashes.add(new_hash)
        except Exception as exc:
            errors.append(f"id={row.get('id')}: {exc}")

    imported: list[dict] = []
    if import_orphans:
        try:
            tracked_rel = {str(r.get("relative_path") or "") for r in rows}
            for category in SECTION_DOCUMENT_CATEGORIES:
                directory = _category_dir(category)
                if not directory.exists():
                    continue
                for path in directory.glob("*"):
                    if not path.is_file() or path.name == SECTION_DOCUMENT_INDEX_FILENAME or path.name == "metadata.json":
                        continue
                    rel = _to_rel(path)
                    if not rel or rel in tracked_rel:
                        continue
                    tok = path.stem[:SECTION_DOC_TOKEN_LENGTH]
                    if not _is_hex_token(tok, length=SECTION_DOC_TOKEN_LENGTH):
                        tok = secrets.token_hex(8)[:SECTION_DOC_TOKEN_LENGTH]
                    imported.append({"relative_path": rel, "stored_name": path.name})
                    if dry_run:
                        continue
                    add_section_document_record(
                        hash_id=tok,
                        nome_file=path.name,
                        percorso=str(path.resolve()),
                        tipo="documento",
                        data_caricamento=datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                        categoria=_category_from_directory(path.parent),
                        descrizione="",
                        protocollo=None,
                        verbale_numero=None,
                        original_name=path.name,
                        stored_name=path.name,
                        relative_path=rel,
                        uploaded_at=datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                    )
        except Exception as exc:
            errors.append(f"import_orphans failed: {exc}")

    return {
        "root": str(root),
        "dry_run": bool(dry_run),
        "scanned": len(rows),
        "updated": len(updated),
        "missing": len(missing),
        "imported": len(imported),
        "details": {"updated": updated, "missing": missing, "imported": imported, "errors": errors},
    }


def rename_section_documents_to_schema(*, dry_run: bool = False) -> list[tuple[str, str]]:
    """Rename existing section documents to the SEZIONE_CATEGORIA_DATA schema."""
    ensure_section_structure()
    tracked_paths: set[str] = set()
    try:
        from database import list_section_document_records

        _db_backfill_registry()
        for row in list_section_document_records(include_deleted=False):
            abs_path = _resolve_to_absolute(
                str(row.get("percorso") or ""),
                fallback_rel=str(row.get("relative_path") or ""),
            )
            if abs_path:
                tracked_paths.add(str(abs_path.resolve()).lower())
    except Exception:
        metadata = _load_metadata()
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
