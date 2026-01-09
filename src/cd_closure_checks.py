# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("librosoci")


@dataclass(frozen=True)
class CdClosureIssue:
    kind: str
    ref: str
    detail: str


def _path_exists(path: str | None) -> bool:
    raw = str(path or "").strip()
    if not raw:
        return False

    try:
        if os.path.exists(raw):
            return True
    except Exception:
        return False

    # Best-effort fallback for legacy relative paths
    try:
        if not os.path.isabs(raw):
            from config import BASE_DIR

            candidate = os.path.normpath(os.path.join(str(BASE_DIR), raw))
            return os.path.exists(candidate)
    except Exception:
        return False

    return False


def _date_in_range(value: str | None, start_date: str | None, end_date: str | None) -> bool:
    v = str(value or "").strip()
    if not v:
        return False
    if start_date and v < start_date:
        return False
    if end_date and v > end_date:
        return False
    return True


def _get_cd_delibere_date_expr(conn) -> str:
    """Return SQL expression for delibera date column as `data_votazione`.

    Older DBs may have `data` instead of `data_votazione`.
    """
    try:
        cols = {str(r["name"]).lower() for r in conn.execute("PRAGMA table_info(cd_delibere)")}
    except Exception:
        cols = set()

    if "data_votazione" in cols:
        return "d.data_votazione"
    if "data" in cols:
        return "d.data"
    return "NULL"


def run_cd_mandato_closure_checks(*, start_date: str | None, end_date: str | None) -> dict[str, Any]:
    """Run end-of-mandate checks for CD verbali and delibere.

    The checks are best-effort and never raise: they return a structured report.

    Returns:
        dict with keys:
            - ok (bool)
            - errors (list[CdClosureIssue-as-dict])
            - warnings (list[CdClosureIssue-as-dict])
            - stats (dict)
    """

    start_iso = (start_date or "").strip() or None
    end_iso = (end_date or "").strip() or None

    errors: list[CdClosureIssue] = []
    warnings: list[CdClosureIssue] = []

    stats: dict[str, Any] = {
        "meetings_in_period": 0,
        "delibere_in_period": 0,
        "verbali_docs_in_period": 0,
    }

    # 1) Meetings verbali (cd_riunioni)
    try:
        from database import fetch_all

        rows = fetch_all(
            """
            SELECT id, numero_cd, data, titolo, verbale_path, tipo_riunione
            FROM cd_riunioni
            WHERE (? IS NULL OR data >= ?)
              AND (? IS NULL OR data <= ?)
              AND LOWER(COALESCE(tipo_riunione, 'passata')) <> 'futura'
            ORDER BY data ASC, id ASC
            """,
            (start_iso, start_iso, end_iso, end_iso),
        )
        meetings = [dict(r) for r in rows]
        stats["meetings_in_period"] = len(meetings)
        for m in meetings:
            meeting_id = str(m.get("id") or "")
            mdate = str(m.get("data") or "")
            num = str(m.get("numero_cd") or "")
            title = str(m.get("titolo") or "").strip()
            ref = f"Riunione #{meeting_id} {num} {mdate} {title}".strip()

            verbale_path = str(m.get("verbale_path") or "").strip()
            if not verbale_path:
                errors.append(CdClosureIssue("missing_meeting_verbale", ref, "Verbale non associato (campo verbale_path vuoto)."))
                continue
            if not _path_exists(verbale_path):
                errors.append(CdClosureIssue("missing_meeting_verbale_file", ref, f"File verbale non trovato: {verbale_path}"))
    except Exception as exc:
        logger.warning("Chiusura CD: check riunioni fallito: %s", exc)
        warnings.append(CdClosureIssue("meetings_check_failed", "cd_riunioni", f"Impossibile verificare le riunioni: {exc}"))

    # 2) Verbali in documenti di sezione
    try:
        from section_documents import list_cd_verbali_documents

        docs = list_cd_verbali_documents(start_date=start_iso, end_date=end_iso, include_missing=True)
        stats["verbali_docs_in_period"] = len(docs)

        for d in docs:
            did = str(d.get("id") or "")
            uploaded_at = str(d.get("uploaded_at") or "")
            dv = uploaded_at[:10] if len(uploaded_at) >= 10 else uploaded_at
            verbale_numero = str(d.get("verbale_numero") or "").strip()
            desc = str(d.get("descrizione") or "").strip()
            abs_path = str(d.get("absolute_path") or "").strip()

            ref = f"Verbale sezione #{did} ({dv}) {verbale_numero} {desc}".strip()

            if not abs_path:
                errors.append(CdClosureIssue("missing_section_doc_path", ref, "Percorso assoluto non disponibile."))
            elif not _path_exists(abs_path):
                errors.append(CdClosureIssue("missing_section_doc_file", ref, f"File non trovato: {abs_path}"))

            # These are quality warnings, not hard errors.
            if not verbale_numero:
                warnings.append(CdClosureIssue("verbale_missing_number", ref, "Verbale senza numero CD (verbale_numero vuoto)."))

    except Exception as exc:
        logger.warning("Chiusura CD: check verbali sezione fallito: %s", exc)
        warnings.append(CdClosureIssue("section_verbali_check_failed", "section_documents", f"Impossibile verificare i verbali in documenti di sezione: {exc}"))

    # 3) Libro delibere
    try:
        from database import fetch_all, get_connection

        with get_connection() as conn:
            date_expr = _get_cd_delibere_date_expr(conn)

        # IMPORTANT: filter by meeting date so we still catch delibere with missing/invalid dates
        # inside the mandate period.
        sql = f"""
            SELECT
                d.id,
                d.cd_id,
                d.numero,
                d.oggetto,
                d.esito,
                {date_expr} AS data_votazione,
                r.data AS data_riunione,
                r.tipo_riunione AS tipo_riunione,
                d.allegato_path
            FROM cd_delibere d
            JOIN cd_riunioni r ON r.id = d.cd_id
            WHERE (? IS NULL OR r.data >= ?)
              AND (? IS NULL OR r.data <= ?)
              AND LOWER(COALESCE(r.tipo_riunione, 'passata')) <> 'futura'
            ORDER BY r.data ASC, d.cd_id ASC, d.numero ASC, d.id ASC
        """

        rows = fetch_all(sql, (start_iso, start_iso, end_iso, end_iso))
        delibere = [dict(r) for r in rows]
        stats["delibere_in_period"] = len(delibere)

        for d in delibere:
            did = str(d.get("id") or "")
            cd_id = str(d.get("cd_id") or "")
            numero = str(d.get("numero") or "").strip()
            oggetto = str(d.get("oggetto") or "").strip()
            esito = str(d.get("esito") or "").strip()
            dv = str(d.get("data_votazione") or "").strip()
            allegato = str(d.get("allegato_path") or "").strip()
            data_riunione = str(d.get("data_riunione") or "").strip()

            ref_date = dv or (data_riunione and f"(riunione {data_riunione})") or ""
            ref = f"Delibera #{did} (CD {cd_id}) {numero} {ref_date} {oggetto}".strip()

            # Mandatory fields for “a posto”
            if not dv:
                errors.append(CdClosureIssue("delibera_missing_date", ref, "Data votazione mancante."))
            elif not _date_in_range(dv, start_iso, end_iso):
                errors.append(CdClosureIssue("delibera_invalid_date", ref, "Data votazione fuori periodo mandato."))
            if not numero:
                errors.append(CdClosureIssue("delibera_missing_number", ref, "Numero delibera mancante."))
            if not oggetto:
                errors.append(CdClosureIssue("delibera_missing_subject", ref, "Oggetto delibera mancante."))
            if not esito:
                errors.append(CdClosureIssue("delibera_missing_outcome", ref, "Esito delibera mancante."))

            if allegato and not _path_exists(allegato):
                errors.append(CdClosureIssue("delibera_missing_attachment", ref, f"Allegato non trovato: {allegato}"))

    except Exception as exc:
        logger.warning("Chiusura CD: check delibere fallito: %s", exc)
        warnings.append(CdClosureIssue("delibere_check_failed", "cd_delibere", f"Impossibile verificare le delibere: {exc}"))

    ok = len(errors) == 0

    def _issue_to_dict(issue: CdClosureIssue) -> dict[str, str]:
        return {"kind": issue.kind, "ref": issue.ref, "detail": issue.detail}

    return {
        "ok": ok,
        "errors": [_issue_to_dict(e) for e in errors],
        "warnings": [_issue_to_dict(w) for w in warnings],
        "stats": stats,
        "start_date": start_iso,
        "end_date": end_iso,
    }


def format_cd_mandato_closure_report(report: dict[str, Any]) -> str:
    """Format a human-readable report suitable for a messagebox."""

    start_iso = str(report.get("start_date") or "")
    end_iso = str(report.get("end_date") or "")
    ok = bool(report.get("ok"))

    stats = report.get("stats") or {}
    meetings = stats.get("meetings_in_period")
    delibere = stats.get("delibere_in_period")
    verbali_docs = stats.get("verbali_docs_in_period")

    errors = report.get("errors") or []
    warnings = report.get("warnings") or []

    lines: list[str] = []
    lines.append("Verifica fine mandato CD")
    lines.append(f"Periodo: {start_iso or '??'} → {end_iso or '??'}")
    lines.append("")
    lines.append(f"Riunioni nel periodo: {meetings}")
    lines.append(f"Delibere nel periodo: {delibere}")
    lines.append(f"Verbali (documenti sezione) nel periodo: {verbali_docs}")
    lines.append("")

    if ok:
        lines.append("ESITO: OK (nessun errore bloccante)")
    else:
        lines.append(f"ESITO: ATTENZIONE ({len(errors)} errori)")

    if errors:
        lines.append("")
        lines.append("ERRORI:")
        for e in errors[:60]:
            lines.append(f"- {e.get('ref')}: {e.get('detail')}")
        if len(errors) > 60:
            lines.append(f"... ({len(errors) - 60} altri errori)")

    if warnings:
        lines.append("")
        lines.append("AVVISI:")
        for w in warnings[:60]:
            lines.append(f"- {w.get('ref')}: {w.get('detail')}")
        if len(warnings) > 60:
            lines.append(f"... ({len(warnings) - 60} altri avvisi)")

    return "\n".join(lines)
