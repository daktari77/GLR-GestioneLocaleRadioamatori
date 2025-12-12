# -*- coding: utf-8 -*-
"""Utility checks executed when the application starts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence
import logging
import os

logger = logging.getLogger("librosoci")


@dataclass
class StartupIssue:
    """Represents a problem detected during startup validation."""

    title: str
    details: List[str]


def collect_startup_issues() -> List[StartupIssue]:
    """Run all startup checks and return the resulting issues."""
    issues: List[StartupIssue] = []

    missing_docs = _check_missing_documents()
    if missing_docs:
        issues.append(missing_docs)

    return issues


def _check_missing_documents() -> StartupIssue | None:
    """Ensure every document stored in DB exists on disk."""
    from database import get_all_documenti_with_member_names

    try:
        rows = get_all_documenti_with_member_names()
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.error("Impossibile recuperare l'elenco documenti: %s", exc)
        return StartupIssue(
            title="Controllo documenti non riuscito",
            details=[f"Errore durante la lettura del database: {exc}"],
        )

    missing: List[str] = []
    for doc in rows:
        path = (doc.get("percorso") or "").strip()
        if path and os.path.exists(path):
            continue

        nominativo = (doc.get("nominativo") or "").strip()
        if not nominativo:
            nominativo = f"{(doc.get('nome') or '').strip()} {(doc.get('cognome') or '').strip()}".strip()
        if not nominativo:
            nominativo = f"Socio #{doc.get('socio_id') or '?'}"

        file_name = doc.get("nome_file") or "(nome file non registrato)"
        descriptor = path or "percorso mancante"
        missing.append(f"ID {doc.get('id')} · {nominativo} · {file_name} · {descriptor}")

    if missing:
        return StartupIssue(
            title=f"Documenti mancanti ({len(missing)})",
            details=missing,
        )
    return None


def format_startup_issues(issues: Sequence[StartupIssue]) -> str:
    """Return a human readable message summarizing startup issues."""
    if not issues:
        return ""

    lines: List[str] = [
        "Sono stati rilevati alcuni problemi che richiedono attenzione:",
        "",
    ]
    for issue in issues:
        lines.append(f"• {issue.title}")
        for detail in issue.details:
            lines.append(f"   - {detail}")
        lines.append("")
    return "\n".join(lines).strip()
