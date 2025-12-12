# -*- coding: utf-8 -*-
"""Preferences utilities for customizable options."""

from __future__ import annotations

from typing import Iterable, Sequence

from config_manager import load_config, save_config

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
