"""Document categories shared across the Libro Soci UI."""
from __future__ import annotations

from typing import Iterable, Tuple

# Categories exposed in combo-boxes across the UI. The order matters because the
# first element becomes the default selection when widgets are instantiated.
DOCUMENT_CATEGORIES: Tuple[str, ...] = (
    "Privacy",
    "Documenti Identità",
    "Deleghe",
    "Certificazioni",
    "Ricevute",
    "Altro",
)

DEFAULT_DOCUMENT_CATEGORY: str = DOCUMENT_CATEGORIES[0]


def normalize_category(value: str | None) -> str:
    """Return a catalog-safe category name, falling back to the default."""
    if not value:
        return DEFAULT_DOCUMENT_CATEGORY

    candidate = value.strip()
    if not candidate:
        return DEFAULT_DOCUMENT_CATEGORY

    lower_map = {cat.lower(): cat for cat in DOCUMENT_CATEGORIES}
    return lower_map.get(candidate.lower(), DEFAULT_DOCUMENT_CATEGORY)


def ensure_category(value: str | None, extra_allowed: Iterable[str] | None = None) -> str:
    """Validate or expand the categories list at runtime.

    Widgets may provide custom entries (e.g., via config). To avoid breaking the
    catalog we optionally accept `extra_allowed`; if `value` matches one of those
    additional entries (case insensitive) we return it untouched, otherwise we
    fall back to the normalized catalog category.
    """
    if extra_allowed:
        extra_map = {c.lower(): c for c in extra_allowed if c}
        if value and value.strip().lower() in extra_map:
            return extra_map[value.strip().lower()]
    return normalize_category(value)
