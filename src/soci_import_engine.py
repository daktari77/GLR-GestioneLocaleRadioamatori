# -*- coding: utf-8 -*-
"""Shared import/upsert helpers for the `soci` table.

This module is intentionally UI-agnostic: it contains reusable, tested building
blocks that multiple Tkinter wizards can call.

Design goals:
- Centralize SQL building and execution for insert/update operations.
- Keep existing wizard UX and behaviors unchanged.
- Only parameterize values; f-strings are used solely for column lists.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


def _is_non_empty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    return True


def _build_insert_sql(
    *,
    table: str,
    payload: Mapping[str, Any],
) -> tuple[str, list[Any]] | None:
    cols: list[str] = []
    vals: list[Any] = []

    for key, value in payload.items():
        if not _is_non_empty(value):
            continue
        cols.append(key)
        vals.append(value)

    if not cols:
        return None

    placeholders = ["?" for _ in cols]
    sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(placeholders)})"
    return sql, vals


def _build_update_sql(
    *,
    table: str,
    updates: Mapping[str, Any],
    where_clause: str,
    where_params: Sequence[Any],
    keep_empty_strings: bool = False,
) -> tuple[str, list[Any]] | None:
    set_parts: list[str] = []
    vals: list[Any] = []

    for key, value in updates.items():
        if value is None:
            continue
        if isinstance(value, str) and value.strip() == "" and not keep_empty_strings:
            continue
        set_parts.append(f"{key}=?")
        vals.append(value)

    if not set_parts:
        return None

    sql = f"UPDATE {table} SET {', '.join(set_parts)} WHERE {where_clause}"
    return sql, vals + list(where_params)


@dataclass
class UpsertResult:
    updated: int = 0
    inserted: int = 0
    skipped: int = 0


def fetch_socio_by_matricola(matricola: str):
    """Return the full row for an existing socio by matricola, or None."""
    from database import fetch_one

    matricola_s = (matricola or "").strip()
    if not matricola_s:
        return None
    return fetch_one("SELECT * FROM soci WHERE matricola=?", (matricola_s,))


def fetch_socio_id(*, matricola: str | None = None, nominativo: str | None = None):
    """Return {'id': ...} row for an existing socio by matricola or nominativo, or None."""
    from database import fetch_one

    if matricola is not None:
        m = str(matricola).strip()
        if m:
            row = fetch_one("SELECT id FROM soci WHERE matricola=?", (m,))
            if row:
                return row

    if nominativo is not None:
        n = str(nominativo).strip()
        if n:
            return fetch_one("SELECT id FROM soci WHERE LOWER(nominativo)=LOWER(?)", (n,))

    return None


def insert_socio(payload: Mapping[str, Any], *, write_enabled: bool = True) -> bool:
    """Insert a new record into `soci`. Returns True if executed."""
    from database import exec_query

    built = _build_insert_sql(table="soci", payload=payload)
    if not built:
        return False

    sql, params = built
    if write_enabled:
        exec_query(sql, params)
    return True


def update_socio_by_matricola(
    *,
    matricola: str,
    updates: Mapping[str, Any],
    write_enabled: bool = True,
    keep_empty_strings: bool = False,
) -> bool:
    """Update an existing record in `soci` matched by matricola. Returns True if executed."""
    from database import exec_query

    m = (matricola or "").strip()
    if not m:
        return False

    built = _build_update_sql(
        table="soci",
        updates=updates,
        where_clause="matricola=?",
        where_params=(m,),
        keep_empty_strings=keep_empty_strings,
    )
    if not built:
        return False

    sql, params = built
    if write_enabled:
        exec_query(sql, params)
    return True


def update_socio_by_id(
    *,
    socio_id: int,
    updates: Mapping[str, Any],
    write_enabled: bool = True,
    keep_empty_strings: bool = False,
) -> bool:
    """Update an existing record in `soci` matched by id. Returns True if executed."""
    from database import exec_query

    if socio_id is None:
        return False

    built = _build_update_sql(
        table="soci",
        updates=updates,
        where_clause="id=?",
        where_params=(socio_id,),
        keep_empty_strings=keep_empty_strings,
    )
    if not built:
        return False

    sql, params = built
    if write_enabled:
        exec_query(sql, params)
    return True
