# -*- coding: utf-8 -*-
"""Gestione mandati del Consiglio Direttivo.

Obiettivo:
- Tenere traccia del periodo di carica (es. 2023-2025)
- Salvare composizione/ruoli del CD
- Permettere alla UI di filtrare automaticamente verbali e viste correlate

Nota: composizione salvata come JSON (lista di dict) per rimanere leggeri e
non introdurre troppe tabelle.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from utils import now_iso

logger = logging.getLogger("librosoci")


def get_all_cd_mandati() -> list[dict[str, Any]]:
    """Return all CD mandates (active and historical)."""
    from database import fetch_all

    try:
        rows = fetch_all(
            """
            SELECT id, label, start_date, end_date, composizione_json, note, is_active, created_at, updated_at
            FROM cd_mandati
            ORDER BY is_active DESC, start_date DESC, id DESC
            """
        )
        out: list[dict[str, Any]] = []
        for row in rows or []:
            d = dict(row)
            comp_raw = d.get("composizione_json")
            try:
                d["composizione"] = json.loads(comp_raw) if comp_raw else []
            except Exception:
                d["composizione"] = []
            out.append(d)
        return out
    except Exception as exc:
        logger.warning("Impossibile leggere elenco mandati CD: %s", exc)
        return []


def get_cd_mandato_by_id(mandato_id: int) -> Optional[dict[str, Any]]:
    """Return a mandate by ID, if found."""
    from database import fetch_one

    try:
        row = fetch_one(
            """
            SELECT id, label, start_date, end_date, composizione_json, note, is_active, created_at, updated_at
            FROM cd_mandati
            WHERE id = ?
            """,
            (int(mandato_id),),
        )
        if not row:
            return None
        d = dict(row)
        comp_raw = d.get("composizione_json")
        try:
            d["composizione"] = json.loads(comp_raw) if comp_raw else []
        except Exception:
            d["composizione"] = []
        return d
    except Exception as exc:
        logger.warning("Impossibile leggere mandato CD id=%s: %s", mandato_id, exc)
        return None


def get_active_cd_mandato() -> Optional[dict[str, Any]]:
    """Return the active mandate record, if any."""
    from database import fetch_one

    try:
        row = fetch_one(
            """
            SELECT id, label, start_date, end_date, composizione_json, note, is_active, created_at, updated_at
            FROM cd_mandati
            WHERE is_active = 1
            ORDER BY start_date DESC, id DESC
            LIMIT 1
            """
        )
        if not row:
            return None
        d = dict(row)
        comp_raw = d.get("composizione_json")
        try:
            d["composizione"] = json.loads(comp_raw) if comp_raw else []
        except Exception:
            d["composizione"] = []
        return d
    except Exception as exc:
        logger.warning("Impossibile leggere mandato CD attivo: %s", exc)
        return None


def save_cd_mandato(
    *,
    mandato_id: int | None = None,
    label: str,
    start_date: str,
    end_date: str,
    composizione: list[dict[str, Any]] | None = None,
    note: str | None = None,
    is_active: bool = True,
    deactivate_previous_active: bool = True,
) -> int:
    """Create or update a mandate.

        Behavior:
        - If mandato_id is provided, updates that record.
        - Otherwise:
                - If an active mandate exists and has the same (start_date, end_date) and is_active=True,
                    update it (backward compatible behavior).
                - Else inserts a new record (active if is_active=True, otherwise historical).
        - If is_active=True and deactivate_previous_active=True: deactivates other mandates.

    Returns:
        mandato_id (>=1) on success, -1 on failure.
    """

    from database import get_connection

    label = (label or "").strip()
    start_date = (start_date or "").strip()
    end_date = (end_date or "").strip()
    note_value = (note or "").strip() or None

    if not label:
        label = f"Mandato {start_date[:4]}-{end_date[:4]}" if start_date and end_date else "Mandato CD"

    comp_json = json.dumps(composizione or [], ensure_ascii=False)
    ts = now_iso()

    try:
        with get_connection() as conn:
            cur = conn.cursor()

            # Update an explicit mandate by ID.
            if mandato_id is not None:
                if is_active and deactivate_previous_active:
                    cur.execute("UPDATE cd_mandati SET is_active = 0, updated_at = ? WHERE is_active = 1", (ts,))
                cur.execute(
                    """
                    UPDATE cd_mandati
                    SET label = ?, start_date = ?, end_date = ?, composizione_json = ?, note = ?, is_active = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (label, start_date, end_date, comp_json, note_value, 1 if is_active else 0, ts, int(mandato_id)),
                )
                return int(mandato_id)

            cur.execute(
                """
                SELECT id, start_date, end_date
                FROM cd_mandati
                WHERE is_active = 1
                ORDER BY start_date DESC, id DESC
                LIMIT 1
                """
            )
            active = cur.fetchone()

            if (
                is_active
                and active
                and (str(active[1] or "") == start_date)
                and (str(active[2] or "") == end_date)
            ):
                mandato_id = int(active[0])
                cur.execute(
                    """
                    UPDATE cd_mandati
                    SET label = ?, composizione_json = ?, note = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (label, comp_json, note_value, ts, mandato_id),
                )
                return mandato_id

            # New mandate: optionally deactivate old active ones, then insert.
            if is_active and deactivate_previous_active:
                cur.execute("UPDATE cd_mandati SET is_active = 0, updated_at = ? WHERE is_active = 1", (ts,))
            cur.execute(
                """
                INSERT INTO cd_mandati (label, start_date, end_date, composizione_json, note, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (label, start_date, end_date, comp_json, note_value, 1 if is_active else 0, ts, ts),
            )
            mandato_id = cur.lastrowid
            return int(mandato_id) if mandato_id else -1
    except Exception as exc:
        logger.error("Impossibile salvare mandato CD: %s", exc)
        return -1
