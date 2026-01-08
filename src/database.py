# -*- coding: utf-8 -*-
"""
Database operations for GLR Gestione Locale Radioamatori
"""

import sqlite3
import json
import logging
from typing import List, Tuple, Optional, Any, Dict, Sequence
from contextlib import contextmanager
from documents_catalog import DEFAULT_DOCUMENT_CATEGORY
from exceptions import (
    DatabaseError,
    DatabaseConnectionError,
    DatabaseIntegrityError,
    DatabaseLockError,
    map_sqlite_exception
)

logger = logging.getLogger("librosoci")

# Database configuration will be injected
_db_name = None

def set_db_path(db_name: str):
    """Set the database file path."""
    global _db_name
    _db_name = db_name


def get_db_path() -> str:
    """Return the currently configured database file path."""
    if _db_name is None:
        raise RuntimeError("Database path not set. Call set_db_path() first.")
    return _db_name

def get_conn() -> sqlite3.Connection:
    """Get a database connection with row factory."""
    if _db_name is None:
        raise RuntimeError("Database path not set. Call set_db_path() first.")
    conn = sqlite3.connect(_db_name, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

@contextmanager
def get_connection():
    """
    Context manager for database connections.
    Ensures connection is properly closed and committed/rolled back.
    
    Usage:
        with get_connection() as conn:
            conn.execute("INSERT INTO ...")
            # Automatically commits on success, rollback on error
    """
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def fetch_all(sql: str, params=()):
    """
    Execute query and return all results.
    Properly closes connection after execution.
    
    Raises:
        DatabaseError: If query execution fails
    """
    conn = get_conn()
    try:
        result = conn.execute(sql, params).fetchall()
        conn.commit()
        return result
    except sqlite3.Error as e:
        conn.rollback()
        raise map_sqlite_exception(e)
    except Exception as e:
        conn.rollback()
        raise DatabaseError(f"Query execution failed: {str(e)}", original_error=e)
    finally:
        conn.close()

def fetch_one(sql: str, params=()):
    """
    Execute query and return first result.
    Properly closes connection after execution.
    
    Raises:
        DatabaseError: If query execution fails
    """
    conn = get_conn()
    try:
        result = conn.execute(sql, params).fetchone()
        conn.commit()
        return result
    except sqlite3.Error as e:
        conn.rollback()
        raise map_sqlite_exception(e)
    except Exception as e:
        conn.rollback()
        raise DatabaseError(f"Query execution failed: {str(e)}", original_error=e)
    finally:
        conn.close()

def exec_query(sql: str, params=()):
    """
    Execute query without returning results.
    Properly closes connection and commits transaction.
    
    Raises:
        DatabaseError: If query execution fails
    """
    conn = get_conn()
    try:
        conn.execute(sql, params)
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        raise map_sqlite_exception(e)
    except Exception as e:
        conn.rollback()
        raise DatabaseError(f"Query execution failed: {str(e)}", original_error=e)
    finally:
        conn.close()

# --------------------------
# Database schema
# --------------------------
REQUIRED_COLUMNS_SOCI = [
    ("matricola", "TEXT"),
    ("nominativo", "TEXT"),
    ("nominativo2", "TEXT"),
    ("nome", "TEXT"),
    ("cognome", "TEXT"),
    ("data_nascita", "TEXT"),
    ("luogo_nascita", "TEXT"),
    ("indirizzo", "TEXT"),
    ("cap", "TEXT"),
    ("citta", "TEXT"),
    ("provincia", "TEXT"),
    ("codicefiscale", "TEXT"),
    ("email", "TEXT"),
    ("telefono", "TEXT"),
    ("attivo", "INTEGER DEFAULT 1"),
    ("data_iscrizione", "TEXT"),
    ("delibera_numero", "TEXT"),
    ("delibera_data", "TEXT"),
    ("data_dimissioni", "TEXT"),
    ("motivo_uscita", "TEXT"),
    ("note", "TEXT"),
    ("deleted_at", "TEXT"),
    ("voto", "INTEGER DEFAULT 0"),
    ("familiare", "TEXT"),
    ("socio", "TEXT"),
    ("cd_ruolo", "TEXT"),
    ("privacy_ok", "INTEGER DEFAULT 0"),
    ("privacy_data", "TEXT"),
    ("privacy_scadenza", "TEXT"),
    ("privacy_signed", "INTEGER DEFAULT 0"),
    ("q0", "TEXT"),
    ("q1", "TEXT"),
    ("q2", "TEXT"),
]
REQUIRED_COLUMNS_DOCS = [
    ("categoria", "TEXT"),
    ("descrizione", "TEXT")
]

CREATE_SOCI_MIN = "CREATE TABLE IF NOT EXISTS soci (id INTEGER PRIMARY KEY AUTOINCREMENT)"

CREATE_DOCS = """
CREATE TABLE IF NOT EXISTS documenti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    socio_id INTEGER NOT NULL,
    nome_file TEXT,
    percorso TEXT,
    tipo TEXT,
    categoria TEXT,
    descrizione TEXT,
    data_caricamento TEXT,
    FOREIGN KEY (socio_id) REFERENCES soci(id) ON DELETE CASCADE
)
"""

CREATE_SOCI_ROLES = """
CREATE TABLE IF NOT EXISTS soci_ruoli (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    socio_id INTEGER NOT NULL,
    ruolo TEXT NOT NULL,
    assegnato_il TEXT,
    note TEXT,
    FOREIGN KEY (socio_id) REFERENCES soci(id) ON DELETE CASCADE
)
"""

CREATE_EVENTI = """
CREATE TABLE IF NOT EXISTS eventi_libro_soci (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    socio_id INTEGER NOT NULL,
    tipo_evento TEXT NOT NULL,
    dettagli_json TEXT NOT NULL,
    ts TEXT NOT NULL,
    FOREIGN KEY (socio_id) REFERENCES soci(id) ON DELETE CASCADE
)
"""

CREATE_CD_RIUNIONI = """
CREATE TABLE IF NOT EXISTS cd_riunioni (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_cd TEXT,
    data TEXT NOT NULL,
    titolo TEXT,
    note TEXT,
    tipo_riunione TEXT,
    meta_json TEXT,
    odg_json TEXT,
    presenze_json TEXT,
    verbale_path TEXT,
    created_at TEXT NOT NULL
)
"""

CREATE_CD_DELIBERE = """
CREATE TABLE IF NOT EXISTS cd_delibere (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cd_id INTEGER NOT NULL,
    numero TEXT NOT NULL,
    oggetto TEXT NOT NULL,
    esito TEXT CHECK (esito in ('APPROVATA','RESPINTA','RINVIATA')) DEFAULT 'APPROVATA',
    data_votazione TEXT,
    favorevoli INTEGER,
    contrari INTEGER,
    astenuti INTEGER,
    allegato_path TEXT,
    note TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (cd_id) REFERENCES cd_riunioni(id) ON DELETE CASCADE
)
"""

CREATE_CD_VERBALI = """
CREATE TABLE IF NOT EXISTS cd_verbali (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cd_id INTEGER NOT NULL,
    data_redazione TEXT NOT NULL,
    presidente TEXT,
    segretario TEXT,
    odg TEXT,
    documento_path TEXT,
    note TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (cd_id) REFERENCES cd_riunioni(id) ON DELETE CASCADE
)
"""

CREATE_CD_MANDATI = """
CREATE TABLE IF NOT EXISTS cd_mandati (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    composizione_json TEXT,
    note TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT,
    updated_at TEXT
)
"""

CREATE_CALENDAR_EVENTS = """
CREATE TABLE IF NOT EXISTS calendar_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL,
    titolo TEXT NOT NULL,
    descrizione TEXT,
    luogo TEXT,
    start_ts TEXT NOT NULL,
    reminder_days INTEGER DEFAULT 7,
    origin TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

CREATE_PONTI = """
CREATE TABLE IF NOT EXISTS ponti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    nominativo TEXT,
    banda TEXT,
    freq_tx REAL,
    freq_rx REAL,
    shift REAL,
    tono TEXT,
    modo TEXT,
    tipologia TEXT,
    qth TEXT,
    locatore TEXT,
    altitudine INTEGER,
    stato_corrente TEXT DEFAULT 'ATTIVO',
    note_tecniche TEXT,
    documento_principale_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

CREATE_PONTI_STATUS_HISTORY = """
CREATE TABLE IF NOT EXISTS ponti_status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ponte_id INTEGER NOT NULL,
    stato TEXT NOT NULL,
    note TEXT,
    ts TEXT NOT NULL,
    autore TEXT,
    FOREIGN KEY (ponte_id) REFERENCES ponti(id) ON DELETE CASCADE
)
"""

CREATE_PONTI_AUTHORIZATIONS = """
CREATE TABLE IF NOT EXISTS ponti_authorizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ponte_id INTEGER NOT NULL,
    tipo TEXT NOT NULL,
    ente TEXT,
    numero TEXT,
    data_rilascio TEXT,
    data_scadenza TEXT,
    documento_path TEXT,
    note TEXT,
    calendar_event_id INTEGER,
    FOREIGN KEY (ponte_id) REFERENCES ponti(id) ON DELETE CASCADE,
    FOREIGN KEY (calendar_event_id) REFERENCES calendar_events(id) ON DELETE SET NULL
)
"""

CREATE_PONTI_INTERVENTI = """
CREATE TABLE IF NOT EXISTS ponti_interventi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ponte_id INTEGER NOT NULL,
    data TEXT NOT NULL,
    categoria TEXT NOT NULL,
    descrizione TEXT,
    responsabile TEXT,
    materiali TEXT,
    calendar_event_id INTEGER,
    allegato_path TEXT,
    note TEXT,
    FOREIGN KEY (ponte_id) REFERENCES ponti(id) ON DELETE CASCADE,
    FOREIGN KEY (calendar_event_id) REFERENCES calendar_events(id) ON DELETE SET NULL
)
"""

CREATE_PONTI_DOCUMENTS = """
CREATE TABLE IF NOT EXISTS ponti_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ponte_id INTEGER NOT NULL,
    document_path TEXT NOT NULL,
    tipo TEXT,
    note TEXT,
    FOREIGN KEY (ponte_id) REFERENCES ponti(id) ON DELETE CASCADE
)
"""

CREATE_SECTION_DOCUMENTS = """
CREATE TABLE IF NOT EXISTS section_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    -- Allineamento con `documenti` (soci): stesso campo socio_id (qui NULL)
    socio_id INTEGER,
    hash_id TEXT NOT NULL UNIQUE,
    -- Campi uniformati a `documenti` (soci)
    nome_file TEXT,
    percorso TEXT,
    tipo TEXT,
    categoria TEXT,
    descrizione TEXT,
    data_caricamento TEXT,
    -- Campi aggiuntivi (documenti ufficiali / verbali)
    protocollo TEXT,
    verbale_numero TEXT,
    -- Campi legacy / compatibilita'
    stored_name TEXT,
    relative_path TEXT NOT NULL,
    uploaded_at TEXT,
    deleted_at TEXT
)
"""

CREATE_MAGAZZINO_ITEMS = """
CREATE TABLE IF NOT EXISTS magazzino_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_inventario TEXT NOT NULL UNIQUE,
    marca TEXT NOT NULL,
    modello TEXT,
    descrizione TEXT,
    note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

CREATE_MAGAZZINO_LOANS = """
CREATE TABLE IF NOT EXISTS magazzino_loans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    socio_id INTEGER,
    data_prestito TEXT NOT NULL,
    data_reso TEXT,
    note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (item_id) REFERENCES magazzino_items(id) ON DELETE CASCADE,
    FOREIGN KEY (socio_id) REFERENCES soci(id) ON DELETE SET NULL
)
"""

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_soci_attivo ON soci(attivo)",
    "CREATE INDEX IF NOT EXISTS idx_soci_deleted ON soci(deleted_at)",
    "CREATE INDEX IF NOT EXISTS idx_documenti_socio ON documenti(socio_id)",
    "CREATE INDEX IF NOT EXISTS idx_eventi_socio ON eventi_libro_soci(socio_id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_soci_matricola ON soci(matricola) WHERE matricola IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_cd_delibere_cd ON cd_delibere(cd_id)",
    "CREATE INDEX IF NOT EXISTS idx_cd_verbali_cd ON cd_verbali(cd_id)",
    "CREATE INDEX IF NOT EXISTS idx_cd_riunioni_data ON cd_riunioni(data)",
    "CREATE INDEX IF NOT EXISTS idx_cd_mandati_active ON cd_mandati(is_active)",
    "CREATE INDEX IF NOT EXISTS idx_cd_mandati_periodo ON cd_mandati(start_date, end_date)",
    "CREATE INDEX IF NOT EXISTS idx_ponti_stato ON ponti(stato_corrente)",
    "CREATE INDEX IF NOT EXISTS idx_ponti_auth_scadenza ON ponti_authorizations(data_scadenza)",
    "CREATE INDEX IF NOT EXISTS idx_ponti_interventi_data ON ponti_interventi(data)",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_section_documents_relative_path ON section_documents(relative_path) WHERE deleted_at IS NULL",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_section_documents_percorso ON section_documents(percorso) WHERE deleted_at IS NULL",
    "CREATE INDEX IF NOT EXISTS idx_section_documents_categoria ON section_documents(categoria)",
    "CREATE INDEX IF NOT EXISTS idx_section_documents_data ON section_documents(data_caricamento)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_soci_ruoli_unique ON soci_ruoli(socio_id, ruolo)",
    "CREATE INDEX IF NOT EXISTS idx_magazzino_loans_item ON magazzino_loans(item_id)",
    "CREATE INDEX IF NOT EXISTS idx_magazzino_loans_active ON magazzino_loans(item_id, data_reso)"
]

# --------------------------
# Database initialization
# --------------------------
def _has_column(conn: sqlite3.Connection, table: str, col: str) -> bool:
    """Check if a column exists in a table."""
    return any(r["name"] == col for r in conn.execute(f"PRAGMA table_info({table})"))

def _ensure_column(conn: sqlite3.Connection, table: str, col: str, decl: str):
    """Add a column to a table if it doesn't exist."""
    if not _has_column(conn, table, col):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")

def init_db():
    """
    Initialize the database with all required tables and columns.
    Ensures all schema elements are created and migrated properly.
    """
    with get_connection() as conn:
        conn.execute(CREATE_SOCI_MIN)
        for col, decl in REQUIRED_COLUMNS_SOCI:
            _ensure_column(conn, "soci", col, decl)
        conn.execute(CREATE_DOCS)
        for col, decl in REQUIRED_COLUMNS_DOCS:
            _ensure_column(conn, "documenti", col, decl)
        conn.execute(
            "UPDATE documenti SET categoria = ? WHERE categoria IS NULL OR TRIM(categoria) = ''",
            (DEFAULT_DOCUMENT_CATEGORY,)
        )
        conn.execute(CREATE_EVENTI)
        conn.execute(CREATE_CD_RIUNIONI)
        # Ensure numero_cd column exists in cd_riunioni
        _ensure_column(conn, "cd_riunioni", "numero_cd", "TEXT")
        # Tipo riunione: futura/passata (per riabilitare invio email in modifica)
        _ensure_column(conn, "cd_riunioni", "tipo_riunione", "TEXT")
        # MVP Riunione CD (v0.4.3+): JSON structured fields
        _ensure_column(conn, "cd_riunioni", "meta_json", "TEXT")
        _ensure_column(conn, "cd_riunioni", "odg_json", "TEXT")
        _ensure_column(conn, "cd_riunioni", "presenze_json", "TEXT")
        conn.execute(CREATE_CD_DELIBERE)
        # Best-effort migration for older DBs created before some CD columns existed
        _ensure_column(conn, "cd_delibere", "data_votazione", "TEXT")
        _ensure_column(conn, "cd_delibere", "favorevoli", "INTEGER")
        _ensure_column(conn, "cd_delibere", "contrari", "INTEGER")
        _ensure_column(conn, "cd_delibere", "astenuti", "INTEGER")
        _ensure_column(conn, "cd_delibere", "allegato_path", "TEXT")
        _ensure_column(conn, "cd_delibere", "note", "TEXT")
        _ensure_column(conn, "cd_delibere", "created_at", "TEXT")

        # If a legacy "data" column exists, backfill data_votazione when empty.
        try:
            if _has_column(conn, "cd_delibere", "data") and _has_column(conn, "cd_delibere", "data_votazione"):
                conn.execute(
                    """
                    UPDATE cd_delibere
                    SET data_votazione = NULLIF(TRIM(data), '')
                    WHERE (data_votazione IS NULL OR TRIM(data_votazione) = '')
                    """
                )
        except sqlite3.OperationalError as exc:
            logger.warning("Impossibile eseguire backfill cd_delibere: %s", exc)
        conn.execute(CREATE_CD_VERBALI)
        conn.execute(CREATE_CD_MANDATI)
        _ensure_column(conn, "cd_mandati", "label", "TEXT")
        _ensure_column(conn, "cd_mandati", "start_date", "TEXT")
        _ensure_column(conn, "cd_mandati", "end_date", "TEXT")
        _ensure_column(conn, "cd_mandati", "composizione_json", "TEXT")
        _ensure_column(conn, "cd_mandati", "note", "TEXT")
        _ensure_column(conn, "cd_mandati", "is_active", "INTEGER DEFAULT 1")
        _ensure_column(conn, "cd_mandati", "created_at", "TEXT")
        _ensure_column(conn, "cd_mandati", "updated_at", "TEXT")
        conn.execute(CREATE_CALENDAR_EVENTS)
        conn.execute(CREATE_PONTI)
        conn.execute(CREATE_PONTI_STATUS_HISTORY)
        conn.execute(CREATE_PONTI_AUTHORIZATIONS)
        _ensure_column(conn, "ponti_authorizations", "calendar_event_id", "INTEGER")
        conn.execute(CREATE_PONTI_INTERVENTI)
        conn.execute(CREATE_PONTI_DOCUMENTS)
        conn.execute(CREATE_SECTION_DOCUMENTS)
        # Uniforma schema section_documents a quello dei documenti soci (best effort su DB esistenti)
        _ensure_column(conn, "section_documents", "socio_id", "INTEGER")
        _ensure_column(conn, "section_documents", "nome_file", "TEXT")
        _ensure_column(conn, "section_documents", "percorso", "TEXT")
        _ensure_column(conn, "section_documents", "tipo", "TEXT")
        _ensure_column(conn, "section_documents", "categoria", "TEXT")
        _ensure_column(conn, "section_documents", "descrizione", "TEXT")
        _ensure_column(conn, "section_documents", "data_caricamento", "TEXT")
        _ensure_column(conn, "section_documents", "protocollo", "TEXT")
        _ensure_column(conn, "section_documents", "verbale_numero", "TEXT")

        # Backfill campi uniformati (solo se vuoti)
        try:
            conn.execute(
                """
                UPDATE section_documents
                SET categoria = COALESCE(NULLIF(TRIM(categoria), ''), 'Altro')
                WHERE categoria IS NULL OR TRIM(categoria) = ''
                """
            )
            conn.execute(
                """
                UPDATE section_documents
                SET descrizione = COALESCE(descrizione, '')
                WHERE descrizione IS NULL
                """
            )
            conn.execute(
                """
                UPDATE section_documents
                SET nome_file = COALESCE(nome_file, NULLIF(TRIM(stored_name), ''))
                WHERE nome_file IS NULL OR TRIM(nome_file) = ''
                """
            )
            conn.execute(
                """
                UPDATE section_documents
                SET percorso = COALESCE(percorso, NULLIF(TRIM(relative_path), ''))
                WHERE percorso IS NULL OR TRIM(percorso) = ''
                """
            )
            conn.execute(
                """
                UPDATE section_documents
                SET data_caricamento = COALESCE(data_caricamento, NULLIF(TRIM(uploaded_at), ''))
                WHERE data_caricamento IS NULL OR TRIM(data_caricamento) = ''
                """
            )
            conn.execute(
                """
                UPDATE section_documents
                SET tipo = COALESCE(NULLIF(TRIM(tipo), ''), 'documento')
                WHERE tipo IS NULL OR TRIM(tipo) = ''
                """
            )
        except sqlite3.OperationalError as exc:
            logger.warning("Impossibile eseguire backfill section_documents: %s", exc)
        conn.execute(CREATE_MAGAZZINO_ITEMS)
        conn.execute(CREATE_MAGAZZINO_LOANS)
        conn.execute(CREATE_SOCI_ROLES)
        for idx in CREATE_INDEXES:
            try:
                conn.execute(idx)
            except sqlite3.OperationalError as e:
                logger.warning("Indice non creato (%s): %s", idx, e)

        # Backfill historical single-role data into soci_ruoli
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO soci_ruoli (socio_id, ruolo)
                SELECT id, cd_ruolo FROM soci
                WHERE cd_ruolo IS NOT NULL AND TRIM(cd_ruolo) != ''
                """
            )
        except sqlite3.OperationalError as exc:
            logger.warning("Impossibile eseguire la migrazione ruoli: %s", exc)
        
        # Initialize templates table
        try:
            from templates_manager import init_templates_table
            init_templates_table(conn)
        except Exception as e:
            logger.warning("Templates table initialization failed: %s", e)
        
        # Calendar indexes
        try:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_calendar_start ON calendar_events(start_ts)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_calendar_type ON calendar_events(tipo)")
        except sqlite3.OperationalError as e:
            logger.warning("Impossibile creare indici calendario: %s", e)

        logger.info("Database initialized successfully")


# --------------------------
# Section documents (filesystem + DB registry)
# --------------------------

def add_section_document_record(
    *,
    hash_id: str,
    categoria: str | None,
    descrizione: str | None,
    # Campi uniformati a `documenti` (soci)
    nome_file: str | None = None,
    percorso: str | None = None,
    tipo: str | None = None,
    data_caricamento: str | None = None,
    # Campi aggiuntivi
    protocollo: str | None = None,
    verbale_numero: str | None = None,
    # Legacy
    original_name: str | None = None,
    stored_name: str | None = None,
    relative_path: str | None = None,
    uploaded_at: str | None = None,
) -> int | None:
    """Insert a new section document registry record (soft-delete aware)."""
    percorso_value = (percorso or "").strip()
    relative_path_value = (relative_path or "").strip()

    # Keep semantics aligned with member docs:
    # - percorso: absolute path when available
    # - relative_path: relative to section root when available
    # For legacy callers that only provide one field, fall back best-effort.
    if not relative_path_value:
        relative_path_value = percorso_value
    if not percorso_value:
        percorso_value = relative_path_value

        # Removed os.path check for normalization
    # `original_name` is kept in the function signature for backward compatibility,
    # but it is no longer persisted in DB (replaced by `descrizione`).
    nome_file_value = (nome_file or stored_name or "").strip() or None
    tipo_value = (tipo or "documento").strip() or "documento"
    data_value = (data_caricamento or uploaded_at or None)

    # If no description provided, use the passed original_name as a best-effort replacement.
    descrizione_value = (descrizione or "").strip()
    if not descrizione_value and original_name:
        descrizione_value = str(original_name).strip()

    sql = """
    INSERT INTO section_documents
        (
            hash_id,
            nome_file,
            percorso,
            tipo,
            categoria,
            descrizione,
            data_caricamento,
            protocollo,
            verbale_numero,
            stored_name,
            relative_path,
            uploaded_at,
            deleted_at
        )
    VALUES
        (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
    """
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                sql,
                (
                    hash_id,
                    nome_file_value,
                    percorso_value,
                    tipo_value,
                    categoria,
                    descrizione_value,
                    data_value,
                    (protocollo or None),
                    (verbale_numero or None),
                    stored_name,
                    relative_path_value,
                    uploaded_at or data_value,
                ),
            )
            return cur.lastrowid
    except sqlite3.Error as e:
        raise map_sqlite_exception(e)


def list_section_document_records(*, include_deleted: bool = False) -> list[dict]:
    where = "" if include_deleted else "WHERE deleted_at IS NULL"
    rows = fetch_all(
        f"""
        SELECT
            id,
            hash_id,
            nome_file,
            percorso,
            tipo,
            categoria,
            descrizione,
            data_caricamento,
            protocollo,
            verbale_numero,
            stored_name,
            relative_path,
            uploaded_at,
            deleted_at
        FROM section_documents
        {where}
        ORDER BY categoria COLLATE NOCASE, COALESCE(data_caricamento, uploaded_at, '') DESC, id DESC
        """
    )
    return [dict(r) for r in rows]


def get_section_document_by_relative_path(relative_path: str) -> dict | None:
    row = fetch_one(
        """
        SELECT
            id,
            hash_id,
            nome_file,
            percorso,
            tipo,
            categoria,
            descrizione,
            data_caricamento,
            protocollo,
            verbale_numero,
            stored_name,
            relative_path,
            uploaded_at,
            deleted_at
        FROM section_documents
        WHERE relative_path = ? OR percorso = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (relative_path, relative_path),
    )
    return dict(row) if row else None


def update_section_document_record(
    record_id: int,
    *,
    hash_id: str | None = None,
    categoria: str | None = None,
    descrizione: str | None = None,
    protocollo: str | None = None,
    verbale_numero: str | None = None,
    relative_path: str | None = None,
    percorso: str | None = None,
    stored_name: str | None = None,
    nome_file: str | None = None,
    tipo: str | None = None,
    data_caricamento: str | None = None,
) -> bool:
    updates: list[str] = []
    params: list[object] = []
    if hash_id is not None:
        updates.append("hash_id = ?")
        params.append(hash_id)
    if categoria is not None:
        updates.append("categoria = ?")
        params.append(categoria)
    if descrizione is not None:
        updates.append("descrizione = ?")
        params.append(descrizione)
    if protocollo is not None:
        updates.append("protocollo = ?")
        params.append(protocollo)
    if verbale_numero is not None:
        updates.append("verbale_numero = ?")
        params.append(verbale_numero)
    if relative_path is not None:
        updates.append("relative_path = ?")
        params.append(relative_path)
    if percorso is not None:
        updates.append("percorso = ?")
        params.append(percorso)
    if stored_name is not None:
        updates.append("stored_name = ?")
        params.append(stored_name)
    if nome_file is not None:
        updates.append("nome_file = ?")
        params.append(nome_file)
    if tipo is not None:
        updates.append("tipo = ?")
        params.append(tipo)
    if data_caricamento is not None:
        updates.append("data_caricamento = ?")
        params.append(data_caricamento)
    if not updates:
        return False
    params.append(record_id)
    sql = f"UPDATE section_documents SET {', '.join(updates)} WHERE id = ?"
    exec_query(sql, tuple(params))
    return True


def soft_delete_section_document_record(record_id: int) -> bool:
    from utils import now_iso

    exec_query("UPDATE section_documents SET deleted_at = ? WHERE id = ?", (now_iso(), record_id))
    return True

def log_evento(socio_id: int, tipo: str, payload: dict):
    """Log an event to the events table."""
    try:
        from utils import now_iso
        exec_query(
            "INSERT INTO eventi_libro_soci (socio_id, tipo_evento, dettagli_json, ts) VALUES (?,?,?,?)",
            (socio_id, tipo, json.dumps(payload, ensure_ascii=False), now_iso()),
        )
    except Exception as e:
        logger.error("log_evento failed: %s", e)

# --------------------------
# Search functions
# --------------------------
def search_soci(keyword: str) -> List[Dict]:
    """Search members by nome, cognome, nominativo, matricola, email."""
    pattern = f"%{keyword}%"
    sql = """
    SELECT id, nominativo, nome, cognome, matricola, email, attivo, privacy_signed
    FROM soci
    WHERE (nome LIKE ? OR cognome LIKE ? OR nominativo LIKE ? OR matricola LIKE ? OR email LIKE ?)
    AND deleted_at IS NULL
    ORDER BY nominativo
    """
    rows = fetch_all(sql, (pattern, pattern, pattern, pattern, pattern))
    return [dict(row) for row in rows]

# --------------------------
# Document management
# --------------------------
def add_documento(
    socio_id: int,
    nome_file: str,
    percorso: str,
    tipo: str = "documento",
    categoria: str | None = None,
    descrizione: str | None = None,
    data_caricamento: str | None = None,
) -> int | None:
    """
    Add a document for a member.
    
    Args:
        socio_id: Member ID
        nome_file: File name
        percorso: File path
        tipo: Document type (default: "documento")
    
    Returns:
        Document ID or None if failed
    """
    from utils import now_iso
    sql = """
    INSERT INTO documenti (socio_id, nome_file, percorso, tipo, categoria, descrizione, data_caricamento)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    try:
        ts = (data_caricamento or "").strip() or now_iso()
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (socio_id, nome_file, percorso, tipo, categoria, descrizione, ts))
            return cursor.lastrowid
    except sqlite3.Error as e:
        raise map_sqlite_exception(e)

def get_documenti(socio_id: int) -> List[Dict]:
    """Get all documents for a member."""
    sql = """
    SELECT id, nome_file, percorso, tipo, categoria, descrizione, data_caricamento
    FROM documenti
    WHERE socio_id = ?
    ORDER BY data_caricamento DESC
    """
    rows = fetch_all(sql, (socio_id,))
    return [dict(row) for row in rows]

def delete_documento(doc_id: int) -> bool:
    """Delete a document."""
    try:
        exec_query("DELETE FROM documenti WHERE id = ?", (doc_id,))
        return True
    except Exception as e:
        logger.error("Failed to delete document %d: %s", doc_id, e)
        return False

def update_documento_fileinfo(doc_id: int, nome_file: str, percorso: str) -> bool:
    """Update filename and path metadata for a stored document."""
    sql = "UPDATE documenti SET nome_file = ?, percorso = ? WHERE id = ?"
    exec_query(sql, (nome_file, percorso, doc_id))
    return True

def get_all_documenti_with_member_names() -> List[Dict]:
    """Return every document joined with the owning member nominativo data."""
    sql = """
    SELECT d.id, d.socio_id, d.nome_file, d.percorso, d.tipo, d.categoria, d.descrizione, d.data_caricamento,
           s.nominativo, s.nome, s.cognome
    FROM documenti d
    LEFT JOIN soci s ON s.id = d.socio_id
    ORDER BY d.socio_id, d.data_caricamento
    """
    rows = fetch_all(sql)
    return [dict(row) for row in rows]

def get_documento_with_member(doc_id: int) -> Dict | None:
    """Fetch a document row (joined with member nominativo fields)."""
    sql = """
    SELECT d.id, d.socio_id, d.nome_file, d.percorso, d.tipo, d.categoria, d.descrizione, d.data_caricamento,
        s.nominativo, s.nome, s.cognome
    FROM documenti d
    LEFT JOIN soci s ON s.id = d.socio_id
    WHERE d.id = ?
    """
    row = fetch_one(sql, (doc_id,))
    return dict(row) if row else None


# --------------------------
# Ruoli multipli soci
# --------------------------
def _sanitize_roles(roles: Sequence[str]) -> list[str]:
    """Normalize role list by trimming strings and removing duplicates."""
    cleaned: list[str] = []
    seen: set[str] = set()
    for role in roles or []:
        value = (role or "").strip()
        if not value or value in seen:
            continue
        cleaned.append(value)
        seen.add(value)
    return cleaned


def get_member_roles(socio_id: int) -> list[str]:
    """Return all roles assigned to a member ordered alphabetically."""
    if not socio_id:
        return []
    rows = fetch_all(
        "SELECT ruolo FROM soci_ruoli WHERE socio_id = ? ORDER BY ruolo COLLATE NOCASE",
        (socio_id,),
    )
    result: list[str] = []
    for row in rows:
        try:
            result.append(row["ruolo"])
        except Exception:
            result.append(row[0])
    return result


def get_member_roles_summary(socio_id: int, separator: str = " | ") -> str:
    """Return a single string summary of roles."""
    return separator.join(get_member_roles(socio_id))


def set_member_roles(socio_id: int, roles: Sequence[str]) -> list[str]:
    """Replace all roles for a member and keep soci.cd_ruolo in sync."""
    cleaned = _sanitize_roles(roles)
    if not socio_id:
        return cleaned

    with get_connection() as conn:
        conn.execute("DELETE FROM soci_ruoli WHERE socio_id = ?", (socio_id,))
        if cleaned:
            conn.executemany(
                "INSERT INTO soci_ruoli (socio_id, ruolo) VALUES (?, ?)",
                [(socio_id, role) for role in cleaned],
            )
        primary = cleaned[0] if cleaned else None
        conn.execute("UPDATE soci SET cd_ruolo = ? WHERE id = ?", (primary, socio_id))
    return cleaned


def get_roles_map(member_ids: Sequence[int]) -> dict[int, list[str]]:
    """Return all roles keyed by socio_id for the provided members."""
    if not member_ids:
        return {}
    placeholders = ",".join("?" for _ in member_ids)
    sql = (
        "SELECT socio_id, ruolo FROM soci_ruoli WHERE socio_id IN ("
        + placeholders
        + ") ORDER BY ruolo COLLATE NOCASE"
    )
    rows = fetch_all(sql, tuple(member_ids))
    result: dict[int, list[str]] = {}
    for row in rows:
        try:
            socio_id = row["socio_id"]
            ruolo = row["ruolo"]
        except Exception:
            socio_id, ruolo = row
        result.setdefault(socio_id, []).append(ruolo)
    return result

def get_privacy_status(socio_id: int) -> Dict:
    """Get privacy status for a member."""
    sql = "SELECT privacy_signed, privacy_ok, privacy_data FROM soci WHERE id = ?"
    row = fetch_one(sql, (socio_id,))
    if row:
        return dict(row)
    return {"privacy_signed": 0, "privacy_ok": 0, "privacy_data": None}

def set_privacy_signed(socio_id: int, signed: bool = True):
    """Mark privacy form as signed for a member."""
    from utils import now_iso
    sql = "UPDATE soci SET privacy_signed = ?, privacy_data = ? WHERE id = ?"
    exec_query(sql, (1 if signed else 0, now_iso() if signed else None, socio_id))

def update_documento_categoria(doc_id: int, categoria: str) -> bool:
    """Update the category assigned to a document."""
    sql = "UPDATE documenti SET categoria = ? WHERE id = ?"
    exec_query(sql, (categoria, doc_id))
    return True

def update_documento_descrizione(doc_id: int, descrizione: str) -> bool:
    """Update the description stored for a document."""
    sql = "UPDATE documenti SET descrizione = ? WHERE id = ?"
    exec_query(sql, (descrizione, doc_id))
    return True


def update_documento_data_caricamento(doc_id: int, data_caricamento: str) -> bool:
    """Update the stored document date (data_caricamento) for a member document."""
    sql = "UPDATE documenti SET data_caricamento = ? WHERE id = ?"
    exec_query(sql, (data_caricamento, doc_id))
    return True

# --------------------------
# Calendar management
# --------------------------
def add_calendar_event(
    *,
    tipo: str,
    titolo: str,
    start_ts: str,
    descrizione: str | None = None,
    luogo: str | None = None,
    reminder_days: int = 7,
    origin: str | None = None,
) -> int:
    """Create a calendar event and return its ID."""
    from utils import now_iso

    sql = """
    INSERT INTO calendar_events (tipo, titolo, descrizione, luogo, start_ts, reminder_days, origin, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    now = now_iso()
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, (tipo, titolo, descrizione, luogo, start_ts, reminder_days, origin, now, now))
        last_id = cur.lastrowid
        if last_id is None:  # pragma: no cover - sqlite should always return the row id
            raise RuntimeError("Impossibile determinare l'ID del nuovo evento calendario")
        return int(last_id)


def update_calendar_event(event_id: int, **fields) -> bool:
    """Update fields of a calendar event."""
    if not fields:
        return False
    from utils import now_iso

    allowed = {k: v for k, v in fields.items() if k in {
        "tipo", "titolo", "descrizione", "luogo", "start_ts", "reminder_days", "origin"
    }}
    if not allowed:
        return False
    allowed["updated_at"] = now_iso()
    set_clause = ", ".join(f"{k} = ?" for k in allowed.keys())
    params = list(allowed.values()) + [event_id]
    sql = f"UPDATE calendar_events SET {set_clause} WHERE id = ?"
    exec_query(sql, tuple(params))
    return True


def delete_calendar_event(event_id: int) -> bool:
    try:
        exec_query("DELETE FROM calendar_events WHERE id = ?", (event_id,))
        return True
    except Exception as exc:
        logger.error("Failed to delete calendar event %s: %s", event_id, exc)
        return False


def fetch_calendar_event(event_id: int) -> Dict | None:
    row = fetch_one("SELECT * FROM calendar_events WHERE id = ?", (event_id,))
    return dict(row) if row else None


def fetch_calendar_events(
    *,
    start_ts: str | None = None,
    end_ts: str | None = None,
    tipo: str | None = None,
) -> List[Dict]:
    sql = "SELECT * FROM calendar_events WHERE 1=1"
    params: list = []
    if start_ts:
        sql += " AND start_ts >= ?"
        params.append(start_ts)
    if end_ts:
        sql += " AND start_ts <= ?"
        params.append(end_ts)
    if tipo and tipo != "tutti":
        sql += " AND tipo = ?"
        params.append(tipo)
    sql += " ORDER BY start_ts"
    rows = fetch_all(sql, tuple(params))
    return [dict(r) for r in rows]


def fetch_upcoming_calendar_events(within_days: int = 14) -> List[Dict]:
    from utils import now_iso
    from datetime import datetime, timedelta

    now_dt = datetime.now()
    end_dt = now_dt + timedelta(days=within_days)
    start = now_iso()
    end = end_dt.strftime("%Y-%m-%dT%H:%M:%S")
    rows = fetch_all(
        "SELECT * FROM calendar_events WHERE start_ts BETWEEN ? AND ? ORDER BY start_ts",
        (start, end),
    )
    return [dict(r) for r in rows]
