# -*- coding: utf-8 -*-
"""
Utility functions for GLR Gestione Locale Radioamatori
"""

import os
import sys
import subprocess
import re
from datetime import datetime, date
from typing import Optional, Callable

# Lazy imports to avoid circular dependencies
_DOCS_BASE = None

def set_docs_base(docs_base: str):
    """Set the documents base directory."""
    global _DOCS_BASE
    _DOCS_BASE = docs_base

# --------------------------
# Date utilities
# --------------------------
def now_iso() -> str:
    """Return current datetime in ISO format (seconds precision)."""
    return datetime.now().isoformat(timespec="seconds")

def today_iso() -> str:
    """Return today's date in ISO format."""
    return date.today().isoformat()

def iso_to_ddmmyyyy(iso_str: Optional[str]) -> str:
    """
    Convert ISO date (YYYY-MM-DD) to DD/MM/YYYY format.
    Returns empty string if iso_str is None or empty.
    """
    if not iso_str:
        return ""
    try:
        y, m, d = map(int, iso_str.split("-"))
        return f"{d:02d}/{m:02d}/{y:04d}"
    except Exception:
        return ""

def ddmmyyyy_to_iso(s: str) -> Optional[str]:
    """
    Convert date from DD/MM/YYYY format to ISO (YYYY-MM-DD).
    Also accepts YYYY-MM-DD format and auto-converts.
    Returns None if empty, raises ValueError if invalid.
    """
    s = s.strip()
    if not s:
        return None
    
    # Try DD/MM/YYYY format first
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", s)
    if m:
        gg, mm, aa = map(int, m.groups())
        try:
            d = date(aa, mm, gg)
            return d.isoformat()
        except ValueError:
            raise ValueError("La data inserita non esiste.")
    
    # Try YYYY-MM-DD format (ISO)
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", s)
    if m:
        aa, mm, gg = map(int, m.groups())
        try:
            d = date(aa, mm, gg)
            return d.isoformat()
        except ValueError:
            raise ValueError("La data inserita non esiste.")
    
    raise ValueError("Formato data non valido. Usa DD/MM/YYYY o YYYY-MM-DD.")

def calc_privacy_scadenza(privacy_data_iso: Optional[str], anni: int) -> Optional[str]:
    """
    Calculate expiry date N years from privacy_data_iso (YYYY-MM-DD).
    Returns ISO format string (YYYY-MM-DD) or None if privacy_data_iso is empty/invalid.
    """
    if not privacy_data_iso:
        return None
    try:
        y, m, d = map(int, privacy_data_iso.split("-"))
        base = date(y, m, d)
        try:
            return date(base.year + anni, base.month, base.day).isoformat()
        except ValueError:
            # Handle Feb 29 → Feb 28
            return date(base.year + anni, base.month, 28).isoformat()
    except Exception:
        return None

# --------------------------
# Value utilities
# --------------------------
def isempty(v) -> bool:
    """Check if a value is empty (None or blank string)."""
    return v is None or (isinstance(v, str) and v.strip() == "")

def to_bool01(val) -> Optional[int]:
    """
    Convert value to 0/1 (False/True).
    Returns None if empty.
    """
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return 1 if int(val) != 0 else 0
    s = str(val).strip().lower()
    if s == "":
        return None
    truth = {"si", "sì", "yes", "y", "true", "vero", "on", "x", "s", "ok", "v", "t", "1"}
    falsy = {"no", "n", "false", "falso", "off", "0"}
    if s in truth:
        return 1
    if s in falsy:
        return 0
    try:
        return 1 if int(float(s)) != 0 else 0
    except Exception:
        return 0

# --------------------------
# File system utilities
# --------------------------
def open_path(
    path: str,
    *,
    select_target: str | None = None,
    on_error: Callable[[str], None] | None = None,
) -> bool:
    """Open a file or directory with the default system application.

    Args:
        path: Folder/file to open.
        select_target: Optional file to highlight (Windows Explorer / macOS Finder).
        on_error: Optional callback invoked with a user-friendly error message.

    Returns:
        True if a launcher command was invoked, False otherwise.
    """

    def _emit_error(message: str) -> None:
        if on_error is not None:
            on_error(message)

    normalized = os.path.normpath(str(path or "").strip())
    if not normalized:
        _emit_error("Percorso non valido")
        return False

    if sys.platform.startswith("win"):
        if select_target:
            try:
                if os.path.exists(select_target):
                    subprocess.run(["explorer", f"/select,{os.path.normpath(select_target)}"], check=False)
                    return True
            except Exception:
                pass

        try:
            if os.path.isdir(normalized) or os.path.exists(normalized):
                os.startfile(normalized)  # type: ignore[attr-defined]
                return True
        except Exception as exc:
            _emit_error(f"Impossibile aprire il percorso: {exc}")
            return False

        _emit_error("Percorso non disponibile")
        return False

    if sys.platform == "darwin":
        target = select_target if select_target and os.path.exists(select_target) else normalized
        try:
            if os.path.isdir(target):
                subprocess.run(["open", target], check=False)
            else:
                subprocess.run(["open", "-R", target], check=False)
            return True
        except Exception as exc:
            _emit_error(f"Impossibile aprire il percorso: {exc}")
            return False

    target = os.path.dirname(select_target) if select_target else normalized
    try:
        subprocess.run(["xdg-open", target], check=False)
        return True
    except Exception as exc:
        _emit_error(f"Impossibile aprire il percorso: {exc}")
        return False

def docs_dir_for_matricola(matricola: Optional[str]) -> str:
    """Get or create the documents directory for a given matricola."""
    if _DOCS_BASE is None:
        raise RuntimeError("Documents base directory not set. Call set_docs_base() first.")
    m = (matricola or "").strip() or "SENZA_MATRICOLA"
    p = os.path.join(_DOCS_BASE, m)
    os.makedirs(p, exist_ok=True)
    return p

# --------------------------
# Quotas (Q0/Q1/Q2) utilities
# --------------------------
CAUSALI_CODE_RE = re.compile(r"^[A-Z0-9]{2,3}$")

def normalize_q(value: Optional[str]) -> Optional[str]:
    """Normalize quota code: uppercase, validate pattern, return None if empty."""
    if value is None:
        return None
    s = value.strip().upper()
    if s == "":
        return None
    if not CAUSALI_CODE_RE.match(s):
        return None
    return s
