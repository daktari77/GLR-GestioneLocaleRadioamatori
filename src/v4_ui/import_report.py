# -*- coding: utf-8 -*-
"""Shared helpers for import UX."""

from __future__ import annotations


def build_import_summary(imported: int, failed: int, details: list[str] | None = None) -> str:
    """Build the user-facing summary string for a bulk import result."""
    summary = f"Importati: {imported}\nErrori: {failed}"
    if details:
        tail = "\n".join(details[:10])
        if len(details) > 10:
            tail += f"\n... (+{len(details) - 10})"
        summary = summary + "\n\nDettagli:\n" + tail
    return summary
