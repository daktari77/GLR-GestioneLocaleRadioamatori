# -*- coding: utf-8 -*-
"""v4_ui package.

Keep this module intentionally lightweight.

Importing heavy UI modules at package import time can easily create circular
imports (e.g. when `v4_ui.main_window` indirectly imports `v4_ui`).

We expose the historical symbols via lazy imports to preserve compatibility
without triggering those cycles.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

try:
    from config import APP_VERSION as __version__
except Exception:  # pragma: no cover
    __version__ = "0.0.0"


_EXPORTS: dict[str, tuple[str, str]] = {
    "App": ("v4_ui.main_window", "App"),
    "MemberForm": ("v4_ui.forms", "MemberForm"),
    "QuotePanel": ("v4_ui.forms", "QuotePanel"),
    "CDRuoloPanel": ("v4_ui.forms", "CDRuoloPanel"),
    "DocumentPanel": ("v4_ui.panels", "DocumentPanel"),
    "SectionDocumentPanel": ("v4_ui.panels", "SectionDocumentPanel"),
    "SectionInfoPanel": ("v4_ui.panels", "SectionInfoPanel"),
    "EventLogPanel": ("v4_ui.panels", "EventLogPanel"),
    "MagazzinoPanel": ("v4_ui.magazzino_panel", "MagazzinoPanel"),
    "Theme": ("v4_ui.styles", "Theme"),
    "DarkTheme": ("v4_ui.styles", "DarkTheme"),
    "configure_styles": ("v4_ui.styles", "configure_styles"),
    "get_theme": ("v4_ui.styles", "get_theme"),
    "get_fonts": ("v4_ui.styles", "get_fonts"),
}


def __getattr__(name: str) -> Any:  # pragma: no cover
    target = _EXPORTS.get(name)
    if not target:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = target
    module = import_module(module_name)
    return getattr(module, attr_name)


def __dir__() -> list[str]:  # pragma: no cover
    return sorted(list(globals().keys()) + list(_EXPORTS.keys()))


__all__ = list(_EXPORTS.keys())
