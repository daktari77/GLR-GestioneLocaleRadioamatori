"""Shared dialog to collect document metadata (category + description)."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, simpledialog
from typing import Iterable, Sequence


class DocumentMetadataDialog(simpledialog.Dialog):
    """Modal dialog with category combobox and multiline description."""

    def __init__(
        self,
        parent,
        *,
        title: str,
        categories: Sequence[str],
        default_category: str,
        initial_category: str | None = None,
        initial_description: str | None = None,
    ):
        self._categories = tuple(categories) if categories else (default_category,)
        self._default_category = default_category
        self.result: tuple[str, str] | None = None
        self._initial_category = initial_category or default_category
        self._initial_description = initial_description or ""
        super().__init__(parent, title)

    def body(self, master):  # type: ignore[override]
        ttk.Label(master, text="Categoria:").grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.category_var = tk.StringVar(value=self._initial_category)
        self.category_combo = ttk.Combobox(
            master,
            textvariable=self.category_var,
            values=self._categories,
            state="readonly",
            width=40,
        )
        self.category_combo.grid(row=1, column=0, sticky="ew", pady=(0, 6))

        ttk.Label(master, text="Descrizione (facoltativa):").grid(row=2, column=0, sticky="w")
        self.desc_text = tk.Text(master, width=50, height=4)
        self.desc_text.grid(row=3, column=0, sticky="ew")
        self.desc_text.insert("1.0", self._initial_description)

        master.columnconfigure(0, weight=1)
        return self.category_combo

    def apply(self):  # type: ignore[override]
        category = self.category_var.get().strip() or self._default_category
        if category not in self._categories:
            category = self._default_category
        description = self.desc_text.get("1.0", "end").strip()
        self.result = (category, description)


def ask_document_metadata(
    parent,
    *,
    title: str,
    categories: Sequence[str],
    default_category: str,
    initial_category: str | None = None,
    initial_description: str | None = None,
) -> tuple[str, str] | None:
    """Show the metadata dialog and return (category, description) or None if cancelled."""
    dialog = DocumentMetadataDialog(
        parent,
        title=title,
        categories=categories,
        default_category=default_category,
        initial_category=initial_category,
        initial_description=initial_description,
    )
    return dialog.result
