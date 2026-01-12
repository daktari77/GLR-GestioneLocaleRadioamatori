# -*- coding: utf-8 -*-

from __future__ import annotations

import zlib
from collections.abc import Iterable
from tkinter import ttk


MEMBER_CATEGORY_PALETTE: tuple[str, ...] = (
    "#FFE5E0",
    "#FFEFD2",
    "#FFF8C2",
    "#E3F2FD",
    "#E8F5E9",
    "#F3E5F5",
    "#E0F7FA",
    "#FFF0F5",
    "#EDE7F6",
    "#F1F8E9",
)

SECTION_CATEGORY_PALETTE: tuple[str, ...] = (
    "#E3F2FD",
    "#E0F7FA",
    "#FFF4E6",
    "#F3E5F5",
    "#E8F5E9",
    "#FFF8E1",
    "#EDE7F6",
    "#FCE4EC",
)


def _hex_to_rgb_components(value: str) -> tuple[int, int, int]:
    color = (value or "").lstrip("#")
    if len(color) != 6:
        return (255, 255, 255)
    try:
        r = int(color[0:2], 16)
        g = int(color[2:4], 16)
        b = int(color[4:6], 16)
        return (r, g, b)
    except ValueError:
        return (255, 255, 255)


def ideal_foreground_for(bg_hex: str) -> str:
    r, g, b = _hex_to_rgb_components(bg_hex)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#202124" if luminance > 0.6 else "#ffffff"


class CategoryTagStyler:
    """Assign deterministic Treeview tag colors per category/type label."""

    def __init__(
        self,
        tree: ttk.Treeview,
        *,
        default_label: str,
        palette: tuple[str, ...],
        tag_prefix: str = "cat::",
    ):
        self.tree = tree
        self.default_label = (default_label or "Altro").strip() or "Altro"
        self.palette = palette or ("#E8EAED",)
        self.tag_prefix = tag_prefix or "cat::"
        self._tag_cache: dict[str, str] = {}

    def _normalized_label(self, label: str | None) -> str:
        candidate = (label or self.default_label).strip()
        return candidate or self.default_label

    def _color_for_key(self, key: str) -> str:
        index = zlib.crc32(key.encode("utf-8")) % len(self.palette)
        return self.palette[index]

    def tag_for(self, label: str | None) -> str:
        normalized = self._normalized_label(label)
        cache_key = normalized.lower()
        if cache_key in self._tag_cache:
            return self._tag_cache[cache_key]

        tag_name = f"{self.tag_prefix}{cache_key}"
        color = self._color_for_key(cache_key)
        self.tree.tag_configure(tag_name, background=color, foreground=ideal_foreground_for(color))
        self._tag_cache[cache_key] = tag_name
        return tag_name

    def prime(self, labels: Iterable[str] | None):
        if not labels:
            return
        for label in labels:
            self.tag_for(label)
