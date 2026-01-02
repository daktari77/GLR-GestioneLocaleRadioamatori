# -*- coding: utf-8 -*-
"""Preferences utilities for customizable options."""

from __future__ import annotations

from typing import Iterable, Sequence

from config_manager import load_config, save_config
from document_types_catalog import DOCUMENT_CATEGORIES, SECTION_DOCUMENT_CATEGORIES

DEFAULT_ROLE_OPTIONS: list[str] = [
    "Socio",
    "Ex Socio",
    "Presidente",
    "Vice Presidente",
    "Segretario",
    "Tesoriere",
    "Sindaco",
    "Consigliere",
    "Bibliotecario",
    "Gestore ponti",
]


def _sanitize_custom_categories(options: Iterable[str], *, defaults: Sequence[str]) -> list[str]:
    """Return clean list of custom categories without duplicates or empty entries."""
    cleaned: list[str] = []
    seen: set[str] = set()
    defaults_lower = {d.lower(): d for d in defaults if d}
    for opt in options:
        value = (opt or "").strip()
        if not value:
            continue
        if value.lower() in defaults_lower:
            continue
        if value.lower() in seen:
            continue
        cleaned.append(value)
        seen.add(value.lower())
    return cleaned


def build_document_categories(custom_categories: Sequence[str] | None = None) -> list[str]:
    """Return member document categories: defaults + custom (unique, non-empty)."""
    categories: list[str] = list(DOCUMENT_CATEGORIES)
    seen = {c.lower() for c in categories if c}
    if custom_categories:
        for value in custom_categories:
            v = (value or "").strip()
            if not v:
                continue
            if v.lower() in seen:
                continue
            categories.append(v)
            seen.add(v.lower())
    return categories


def build_section_document_categories(custom_categories: Sequence[str] | None = None) -> list[str]:
    """Return section document categories: defaults + custom (unique, non-empty)."""
    categories: list[str] = list(SECTION_DOCUMENT_CATEGORIES)
    seen = {c.lower() for c in categories if c}
    if custom_categories:
        for value in custom_categories:
            v = (value or "").strip()
            if not v:
                continue
            if v.lower() in seen:
                continue
            categories.append(v)
            seen.add(v.lower())
    return categories


def sanitize_custom_document_categories(options: Iterable[str]) -> list[str]:
    return _sanitize_custom_categories(options, defaults=DOCUMENT_CATEGORIES)


def sanitize_custom_section_document_categories(options: Iterable[str]) -> list[str]:
    return _sanitize_custom_categories(options, defaults=SECTION_DOCUMENT_CATEGORIES)


def get_document_categories(cfg: dict | None = None) -> list[str]:
    """Return merged member document categories using provided config or reloading it."""
    try:
        data = cfg if cfg is not None else load_config()
    except Exception:
        data = cfg if cfg is not None else {}
    custom = data.get("custom_document_categories") if isinstance(data, dict) else None
    if not isinstance(custom, list):
        custom = []
    return build_document_categories(custom)


def get_section_document_categories(cfg: dict | None = None) -> list[str]:
    """Return merged section document categories using provided config or reloading it."""
    try:
        data = cfg if cfg is not None else load_config()
    except Exception:
        data = cfg if cfg is not None else {}
    custom = data.get("custom_section_document_categories") if isinstance(data, dict) else None
    if not isinstance(custom, list):
        custom = []
    return build_section_document_categories(custom)


def _sanitize_custom_roles(options: Iterable[str]) -> list[str]:
    """Return clean list of custom roles without duplicates or empty entries."""
    cleaned: list[str] = []
    seen: set[str] = set()
    for opt in options:
        value = (opt or "").strip()
        if not value:
            continue
        if value in DEFAULT_ROLE_OPTIONS:
            # Already handled as default option, no need to store.
            continue
        if value in seen:
            continue
        cleaned.append(value)
        seen.add(value)
    return cleaned


def sanitize_custom_role_options(options: Iterable[str]) -> list[str]:
    """Public helper to sanitize user-defined role labels."""
    return _sanitize_custom_roles(options)


def build_role_options(custom_roles: Sequence[str] | None = None) -> list[str]:
    """Return the list of role options starting with an empty choice."""
    options: list[str] = [""]
    seen: set[str] = {""}

    def _append(values: Iterable[str]):
        for value in values:
            normalized = (value or "").strip()
            if not normalized:
                continue
            if normalized in seen:
                continue
            options.append(normalized)
            seen.add(normalized)

    _append(DEFAULT_ROLE_OPTIONS)
    if custom_roles:
        _append(custom_roles)
    return options


def get_role_options(cfg: dict | None = None) -> list[str]:
    """Return combined role options using the provided config or reloading it."""
    data = cfg if cfg is not None else load_config()
    custom = data.get("custom_role_options") if isinstance(data, dict) else None
    if not isinstance(custom, list):
        custom = []
    return build_role_options(custom)


def save_custom_role_options(options: Sequence[str]) -> dict:
    """Persist custom role options and return the updated configuration."""
    cfg = load_config()
    cfg["custom_role_options"] = _sanitize_custom_roles(options)
    save_config(cfg)
    return cfg
