# -*- coding: utf-8 -*-
"""Gestione mandati del Consiglio Direttivo.

Evoluzione modello (v0.4.2b+):
- Il mandato resta l'entità centrale (tabella `cd_mandati`).
- La composizione del CD non va salvata manualmente: è derivata da assegnazioni
    carica↔socio↔mandato (tabella `cd_assegnazioni_cariche` + `cd_cariche`).

Compatibilità:
- `composizione_json` su `cd_mandati` viene ancora mantenuto per compatibilità UI,
    ma la fonte autorevole è la tabella relazionale.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from utils import now_iso

logger = logging.getLogger("librosoci")


def _normalize_carica_codice(nome: str) -> str:
    from database import _normalize_cd_carica_codice

    return _normalize_cd_carica_codice(nome)


def get_cd_composizione_for_mandato(mandato_id: int, *, on_date: str | None = None) -> list[dict[str, Any]]:
    """Return derived CD composition for a mandate.

    If `on_date` is provided (ISO YYYY-MM-DD), applies interval filtering to
    support substitutions during the same mandate.
    """

    from database import fetch_all

    where_date = ""
    params: list[Any] = [int(mandato_id)]
    if on_date:
        where_date = " AND (a.data_inizio IS NULL OR a.data_inizio <= ?) AND (a.data_fine IS NULL OR a.data_fine >= ?)"
        params.extend([str(on_date), str(on_date)])

    rows = fetch_all(
        f"""
        SELECT
            c.nome AS carica,
            COALESCE(NULLIF(TRIM(s.nominativo), ''), NULLIF(TRIM(a.nominativo), '')) AS nome,
            a.note AS note,
            a.socio_id AS socio_id,
            a.data_inizio AS data_inizio,
            a.data_fine AS data_fine
        FROM cd_assegnazioni_cariche a
        JOIN cd_cariche c ON c.id = a.carica_id
        LEFT JOIN soci s ON s.id = a.socio_id
        WHERE a.mandato_id = ?
        {where_date}
        ORDER BY c.ordine, c.nome, COALESCE(s.cognome, ''), COALESCE(s.nome, ''), a.nominativo
        """,
        tuple(params),
    )
    out: list[dict[str, Any]] = []
    for r in rows or []:
        d = dict(r)
        out.append(
            {
                "carica": str(d.get("carica") or "").strip(),
                "nome": str(d.get("nome") or "").strip(),
                "note": str(d.get("note") or "").strip(),
                "socio_id": d.get("socio_id"),
                "data_inizio": d.get("data_inizio"),
                "data_fine": d.get("data_fine"),
            }
        )
    return out


def get_cd_composizione_for_meeting(meeting_id: int) -> list[dict[str, Any]]:
    """Return CD composition for a meeting.

    Resolution order:
    1) Explicit `cd_riunioni.mandato_id` (if set)
    2) Date-based inference by `cd_mandati.start_date/end_date` using meeting date
    """

    from database import fetch_one

    row = fetch_one(
        "SELECT id, data, mandato_id FROM cd_riunioni WHERE id = ?",
        (int(meeting_id),),
    )
    if not row:
        return []
    meeting_date = str(row.get("data") or "").strip()
    mid = row.get("mandato_id")
    try:
        if mid is not None:
            return get_cd_composizione_for_mandato(int(mid), on_date=meeting_date or None)
    except Exception:
        pass

    if not meeting_date:
        return []
    mrow = fetch_one(
        """
        SELECT id
        FROM cd_mandati
        WHERE start_date <= ? AND end_date >= ?
        ORDER BY start_date DESC, id DESC
        LIMIT 1
        """,
        (meeting_date, meeting_date),
    )
    if not mrow:
        return []
    try:
        mandato_id = int(mrow.get("id"))
    except Exception:
        return []
    return get_cd_composizione_for_mandato(mandato_id, on_date=meeting_date)


def _has_relational_composizione(mandato_id: int) -> bool:
    from database import fetch_one

    row = fetch_one(
        "SELECT COUNT(1) AS n FROM cd_assegnazioni_cariche WHERE mandato_id = ?",
        (int(mandato_id),),
    )
    try:
        return int(row["n"]) > 0 if row else False
    except Exception:
        return False


def _save_relational_composizione(
    conn,
    *,
    mandato_id: int,
    start_date: str,
    end_date: str,
    composizione: list[dict[str, Any]] | None,
    ts: str,
):
    # Strategie:
    # - Manteniamo la compatibilità con wizard legacy (nome libero), quindi
    #   socio_id resta NULL e valorizziamo `nominativo`.
    # - In futuro la UI potrà scegliere soci e riempire socio_id.
    cur = conn.cursor()
    cur.execute("DELETE FROM cd_assegnazioni_cariche WHERE mandato_id = ?", (int(mandato_id),))
    for item in composizione or []:
        if not isinstance(item, dict):
            continue
        carica_nome = str(item.get("carica") or "").strip() or "Consigliere"
        nominativo = str(item.get("nome") or "").strip() or None
        note = str(item.get("note") or "").strip() or None
        socio_id = item.get("socio_id")
        try:
            socio_id_i = int(socio_id) if socio_id is not None and str(socio_id).strip() else None
        except Exception:
            socio_id_i = None
        if not nominativo and socio_id_i is None:
            continue

        codice = _normalize_carica_codice(carica_nome)
        cur.execute(
            "INSERT OR IGNORE INTO cd_cariche(codice, nome, ordine, is_cd_member) VALUES (?, ?, 0, 1)",
            (codice, carica_nome),
        )
        row = cur.execute("SELECT id FROM cd_cariche WHERE codice = ?", (codice,)).fetchone()
        if not row:
            continue
        carica_id = int(row[0])

        cur.execute(
            """
            INSERT INTO cd_assegnazioni_cariche(
                mandato_id, carica_id, socio_id, nominativo, note,
                data_inizio, data_fine,
                created_at, updated_at
            )
            VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?)
            """,
            (int(mandato_id), carica_id, nominativo, note, start_date, end_date, ts, ts),
        )

        # If socio_id is available, patch the row to set it (keeps SQL simple & compatible)
        if socio_id_i is not None:
            cur.execute(
                """
                UPDATE cd_assegnazioni_cariche
                SET socio_id = ?
                WHERE mandato_id = ? AND carica_id = ? AND COALESCE(nominativo,'') = COALESCE(?, '')
                ORDER BY id DESC
                LIMIT 1
                """,
                (socio_id_i, int(mandato_id), carica_id, nominativo or ""),
            )


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
            try:
                mid = int(d.get("id"))
            except Exception:
                mid = None
            if mid is not None and _has_relational_composizione(mid):
                d["composizione"] = get_cd_composizione_for_mandato(mid)
            else:
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
        if _has_relational_composizione(int(mandato_id)):
            d["composizione"] = get_cd_composizione_for_mandato(int(mandato_id))
        else:
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
        try:
            mid = int(d.get("id"))
        except Exception:
            mid = None
        if mid is not None and _has_relational_composizione(mid):
            d["composizione"] = get_cd_composizione_for_mandato(mid)
        else:
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
                # Source-of-truth: relational composition
                try:
                    _save_relational_composizione(
                        conn,
                        mandato_id=int(mandato_id),
                        start_date=start_date,
                        end_date=end_date,
                        composizione=composizione,
                        ts=ts,
                    )
                except Exception:
                    pass
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
                try:
                    _save_relational_composizione(
                        conn,
                        mandato_id=int(mandato_id),
                        start_date=start_date,
                        end_date=end_date,
                        composizione=composizione,
                        ts=ts,
                    )
                except Exception:
                    pass
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
            try:
                if mandato_id:
                    _save_relational_composizione(
                        conn,
                        mandato_id=int(mandato_id),
                        start_date=start_date,
                        end_date=end_date,
                        composizione=composizione,
                        ts=ts,
                    )
            except Exception:
                pass
            return int(mandato_id) if mandato_id else -1
    except Exception as exc:
        logger.error("Impossibile salvare mandato CD: %s", exc)
        return -1
