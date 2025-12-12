# -*- coding: utf-8 -*-
"""
Database operations for Libro Soci v4.2a
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

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_soci_attivo ON soci(attivo)",
    "CREATE INDEX IF NOT EXISTS idx_soci_deleted ON soci(deleted_at)",
    "CREATE INDEX IF NOT EXISTS idx_documenti_socio ON documenti(socio_id)",
    "CREATE INDEX IF NOT EXISTS idx_eventi_socio ON eventi_libro_soci(socio_id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_soci_matricola ON soci(matricola) WHERE matricola IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_cd_delibere_cd ON cd_delibere(cd_id)",
    "CREATE INDEX IF NOT EXISTS idx_cd_verbali_cd ON cd_verbali(cd_id)",
    "CREATE INDEX IF NOT EXISTS idx_cd_riunioni_data ON cd_riunioni(data)",
    "CREATE INDEX IF NOT EXISTS idx_ponti_stato ON ponti(stato_corrente)",
    "CREATE INDEX IF NOT EXISTS idx_ponti_auth_scadenza ON ponti_authorizations(data_scadenza)",
    "CREATE INDEX IF NOT EXISTS idx_ponti_interventi_data ON ponti_interventi(data)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_soci_ruoli_unique ON soci_ruoli(socio_id, ruolo)"
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
        conn.execute(CREATE_CD_DELIBERE)
        conn.execute(CREATE_CD_VERBALI)
        conn.execute(CREATE_CALENDAR_EVENTS)
        conn.execute(CREATE_PONTI)
        conn.execute(CREATE_PONTI_STATUS_HISTORY)
        conn.execute(CREATE_PONTI_AUTHORIZATIONS)
        _ensure_column(conn, "ponti_authorizations", "calendar_event_id", "INTEGER")
        conn.execute(CREATE_PONTI_INTERVENTI)
        conn.execute(CREATE_PONTI_DOCUMENTS)
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
            init_templates_table()
        except Exception as e:
            logger.warning("Templates table initialization failed: %s", e)
        
        # Calendar indexes
        try:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_calendar_start ON calendar_events(start_ts)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_calendar_type ON calendar_events(tipo)")
        except sqlite3.OperationalError as e:
            logger.warning("Impossibile creare indici calendario: %s", e)

        logger.info("Database initialized successfully")

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
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (socio_id, nome_file, percorso, tipo, categoria, descrizione, now_iso()))
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
