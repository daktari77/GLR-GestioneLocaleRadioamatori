"""Catalogs for document 'Tipo' (member + section).

This module is the single source of truth for the default type lists used by:
- Member documents (tab Documenti Soci)
- Section documents (tab Documenti Sezione)

Custom user-defined types are handled by config (see preferences.py).
"""

from __future__ import annotations

from typing import Iterable, Sequence, Tuple


def _normalize_from_catalog(value: str | None, *, catalog: Sequence[str], default: str) -> str:
    if not value:
        return default

    candidate = value.strip()
    if not candidate:
        return default

    lower_map = {item.lower(): item for item in catalog if item}
    return lower_map.get(candidate.lower(), default)


def _ensure_from_catalog(
    value: str | None,
    *,
    catalog: Sequence[str],
    default: str,
    extra_allowed: Iterable[str] | None = None,
) -> str:
    """Return a catalog-safe value.

    If `extra_allowed` is provided, accept values contained there (case-insensitive)
    in addition to the base catalog.
    """

    if extra_allowed:
        extra_map = {c.lower(): c for c in extra_allowed if c}
        if value and value.strip().lower() in extra_map:
            return extra_map[value.strip().lower()]

    return _normalize_from_catalog(value, catalog=catalog, default=default)


# --- Member documents (Soci)

# Order matters: first element becomes the default selection in the UI.
DOCUMENT_CATEGORIES: Tuple[str, ...] = (
    "Privacy",
    "Documenti Identità",
    "Deleghe",
    "Certificazioni",
    "Ricevute",
    "Altro",
)

DEFAULT_DOCUMENT_CATEGORY: str = DOCUMENT_CATEGORIES[0]


def normalize_member_document_type(value: str | None) -> str:
    return _normalize_from_catalog(value, catalog=DOCUMENT_CATEGORIES, default=DEFAULT_DOCUMENT_CATEGORY)


def ensure_member_document_type(value: str | None, extra_allowed: Iterable[str] | None = None) -> str:
    return _ensure_from_catalog(
        value,
        catalog=DOCUMENT_CATEGORIES,
        default=DEFAULT_DOCUMENT_CATEGORY,
        extra_allowed=extra_allowed,
    )


# --- Section documents (Sezione)

SECTION_DOCUMENT_CATEGORIES: Tuple[str, ...] = (
    "Verbali CD",
    "Bilanci",
    "Regolamenti",
    "Modulistica",
    "Documenti ARI",
    "Quote ARI",
    "Log",
    "Altro",
)

DEFAULT_SECTION_CATEGORY: str = SECTION_DOCUMENT_CATEGORIES[0]


def normalize_section_document_type(value: str | None) -> str:
    return _normalize_from_catalog(value, catalog=SECTION_DOCUMENT_CATEGORIES, default=DEFAULT_SECTION_CATEGORY)


def ensure_section_document_type(value: str | None, extra_allowed: Iterable[str] | None = None) -> str:
    return _ensure_from_catalog(
        value,
        catalog=SECTION_DOCUMENT_CATEGORIES,
        default=DEFAULT_SECTION_CATEGORY,
        extra_allowed=extra_allowed,
    )
