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


class SectionDocumentMetadataDialog(simpledialog.Dialog):
    """Modal dialog for section documents: category + protocollo + verbale numero + description."""

    def __init__(
        self,
        parent,
        *,
        title: str,
        categories: Sequence[str],
        default_category: str,
        initial_category: str | None = None,
        initial_description: str | None = None,
        initial_protocollo: str | None = None,
        initial_verbale_numero: str | None = None,
    ):
        self._categories = tuple(categories) if categories else (default_category,)
        self._default_category = default_category
        self.result: tuple[str, str, str, str] | None = None
        self._initial_category = initial_category or default_category
        self._initial_description = initial_description or ""
        self._initial_protocollo = initial_protocollo or ""
        self._initial_verbale_numero = initial_verbale_numero or ""
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
        self.category_combo.grid(row=1, column=0, sticky="ew", pady=(0, 8))

        # Either protocollo OR verbale numero (explicit selection to reduce confusion).
        ttk.Label(master, text="Riferimento (opzionale):").grid(row=2, column=0, sticky="w")
        self.ref_kind_var = tk.StringVar(value="none")
        ref_frame = ttk.Frame(master)
        ref_frame.grid(row=3, column=0, sticky="w", pady=(0, 6))
        ttk.Radiobutton(ref_frame, text="Nessuno", value="none", variable=self.ref_kind_var).pack(side=tk.LEFT)
        ttk.Radiobutton(ref_frame, text="Protocollo", value="protocollo", variable=self.ref_kind_var).pack(side=tk.LEFT, padx=(10, 0))
        ttk.Radiobutton(ref_frame, text="Verbale n.", value="verbale", variable=self.ref_kind_var).pack(side=tk.LEFT, padx=(10, 0))

        ttk.Label(master, text="Protocollo:").grid(row=4, column=0, sticky="w")
        self.protocollo_var = tk.StringVar(value=self._initial_protocollo)
        self.protocollo_entry = ttk.Entry(master, textvariable=self.protocollo_var, width=44)
        self.protocollo_entry.grid(row=5, column=0, sticky="ew", pady=(0, 8))

        ttk.Label(master, text="Verbale numero:").grid(row=6, column=0, sticky="w")
        self.verbale_var = tk.StringVar(value=self._initial_verbale_numero)
        self.verbale_entry = ttk.Entry(master, textvariable=self.verbale_var, width=44)
        self.verbale_entry.grid(row=7, column=0, sticky="ew", pady=(0, 8))

        ttk.Label(master, text="Descrizione (facoltativa):").grid(row=8, column=0, sticky="w")
        self.desc_text = tk.Text(master, width=50, height=4)
        self.desc_text.grid(row=9, column=0, sticky="ew")
        self.desc_text.insert("1.0", self._initial_description)

        def _apply_ref_kind_state(*_args):
            kind = (self.ref_kind_var.get() or "none").strip()
            if kind == "protocollo":
                self.protocollo_entry.state(["!disabled"])
                self.verbale_entry.state(["disabled"])
            elif kind == "verbale":
                self.protocollo_entry.state(["disabled"])
                self.verbale_entry.state(["!disabled"])
            else:
                self.protocollo_entry.state(["disabled"])
                self.verbale_entry.state(["disabled"])

        # Pick initial kind from existing values.
        if (self._initial_protocollo or "").strip() and not (self._initial_verbale_numero or "").strip():
            self.ref_kind_var.set("protocollo")
        elif (self._initial_verbale_numero or "").strip() and not (self._initial_protocollo or "").strip():
            self.ref_kind_var.set("verbale")
        elif (self._initial_protocollo or "").strip() or (self._initial_verbale_numero or "").strip():
            # Both filled (legacy): keep both enabled to let user choose and fix.
            self.ref_kind_var.set("protocollo")

        self.ref_kind_var.trace_add("write", _apply_ref_kind_state)
        _apply_ref_kind_state()

        master.columnconfigure(0, weight=1)
        return self.category_combo

    def apply(self):  # type: ignore[override]
        category = self.category_var.get().strip() or self._default_category
        if category not in self._categories:
            category = self._default_category

        kind = (self.ref_kind_var.get() or "none").strip()
        protocollo = self.protocollo_var.get().strip()
        verbale_numero = self.verbale_var.get().strip()
        if kind == "protocollo":
            verbale_numero = ""
        elif kind == "verbale":
            protocollo = ""
        else:
            protocollo = ""
            verbale_numero = ""

        description = self.desc_text.get("1.0", "end").strip()
        self.result = (category, description, protocollo, verbale_numero)


def ask_section_document_metadata(
    parent,
    *,
    title: str,
    categories: Sequence[str],
    default_category: str,
    initial_category: str | None = None,
    initial_description: str | None = None,
    initial_protocollo: str | None = None,
    initial_verbale_numero: str | None = None,
) -> tuple[str, str, str, str] | None:
    """Return (category, description, protocollo, verbale_numero) or None if cancelled."""
    dialog = SectionDocumentMetadataDialog(
        parent,
        title=title,
        categories=categories,
        default_category=default_category,
        initial_category=initial_category,
        initial_description=initial_description,
        initial_protocollo=initial_protocollo,
        initial_verbale_numero=initial_verbale_numero,
    )
    return dialog.result
